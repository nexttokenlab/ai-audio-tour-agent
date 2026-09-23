"""Modified September 2026: research → plan → story → conversation → replan."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import time
from collections.abc import Callable

from agents import OpenAIProvider, RunConfig, Runner
from openai import AsyncOpenAI

from agent import narrator_agent, planner_agent, question_agent, researcher
from models import Answer, INTERESTS, PlanDraft, Research, Source, STYLES, Story, TourSession, build_plan, safe_url


def citation_sources(result) -> list[Source]:
    """Accept URLs only from provider citation annotations, never model-written URLs."""
    found = {}

    def walk(value):
        if hasattr(value, "model_dump"):
            value = value.model_dump()
        if isinstance(value, dict):
            if value.get("type") == "url_citation" and safe_url(value.get("url", "")):
                url = value["url"]
                source_id = "s-" + hashlib.sha256(url.encode()).hexdigest()[:12]
                found[source_id] = Source(id=source_id, title=value.get("title") or url, url=url)
            for item in value.values():
                walk(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                walk(item)

    for response in result.raw_responses:
        walk(response.output)
    return list(found.values())


def limit_text(text: str, words: int) -> str:
    """Bound audio payloads without cutting a sentence when a reasonable boundary exists."""
    tokens = text.split()
    if len(tokens) <= words:
        return text
    shortened = " ".join(tokens[:words])
    boundary = max(shortened.rfind("."), shortened.rfind("!"), shortened.rfind("?"))
    return shortened[: boundary + 1] if boundary > len(shortened) // 2 else shortened + "…"


class TourManager:
    def __init__(self, api_key: str, progress: Callable[[str], None] | None = None):
        if not api_key.strip():
            raise ValueError("Add an OpenAI API key in Settings, or try the demo.")
        self.api_key = api_key
        self.progress = progress or (lambda _: None)
        self.events: list[dict] = []

    async def _run(self, agent, prompt, config):
        start = time.monotonic()
        result = await Runner.run(agent, prompt, run_config=config, max_turns=6)
        usage = result.context_wrapper.usage
        self.events.append(
            {
                "agent": agent.name,
                "seconds": round(time.monotonic() - start, 2),
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
            }
        )
        return result

    def _config(self, client):
        # No process-global API key or trace upload; credentials remain session-scoped.
        return RunConfig(model_provider=OpenAIProvider(openai_client=client), tracing_disabled=True)

    async def _research(self, location, interests, request, config):
        async def collect(topic):
            self.progress(f"Researching {topic.lower()}…")
            result = await self._run(
                researcher(topic),
                json.dumps(
                    {
                        "location": location,
                        "requested_change": request,
                    }
                ),
                config,
            )
            sources = citation_sources(result)
            if not sources:
                raise ValueError(f"{topic} research returned no source citations. Please retry.")
            return Research(topic=topic, text=str(result.final_output), sources=sources)

        # Independent specialists run concurrently. A failed branch never becomes an empty tour.
        results = await asyncio.gather(*(collect(topic) for topic in interests), return_exceptions=True)
        failures = [r for r in results if isinstance(r, BaseException)]
        if failures:
            raise failures[0]
        return results

    async def create(self, location: str, interests: list[str], minutes: int, style: str) -> TourSession:
        if not location.strip() or not interests or any(i not in INTERESTS for i in interests):
            raise ValueError("Enter a location and select at least one supported interest.")
        if style not in STYLES or not 5 <= minutes <= 120:
            raise ValueError("Choose a supported style and a budget of 5–120 minutes.")
        async with AsyncOpenAI(api_key=self.api_key, timeout=60, max_retries=2) as client:
            config = self._config(client)
            research = await self._research(location.strip(), interests, "", config)
            self.progress("Choosing your stops…")
            result = await self._run(
                planner_agent,
                json.dumps(
                    {
                        "location": location,
                        "interests": interests,
                        "minutes": minutes,
                        "style": STYLES[style],
                        "research": [r.model_dump() for r in research],
                    }
                ),
                config,
            )
            plan = build_plan(
                result.final_output_as(PlanDraft), location.strip(), minutes, [s for r in research for s in r.sources]
            )
        return TourSession(
            plan=plan,
            interests=interests,
            style=style,
            research=research,
            remaining_minutes=minutes,
            events=list(self.events),
        )

    def _context(self, session):
        return {
            "location": session.plan.location,
            "current_stop": session.current.model_dump() if session.current else None,
            "style": STYLES[session.style],
            "visited": session.visited,
            "conversation": session.messages[-12:],
            "earlier_stories": session.told_stories[-8:],
            "research": [r.model_dump() for r in session.research],
        }

    async def story(self, session: TourSession) -> Story:
        stop = session.current
        if stop is None:
            raise ValueError("This tour is complete. Start a new tour to hear another story.")
        if stop.id in session.stories:
            return session.stories[stop.id]
        ceiling = min(180, stop.minutes * 130)
        context = self._context(session)
        context["word_ceiling"] = ceiling
        async with AsyncOpenAI(api_key=self.api_key, timeout=60, max_retries=2) as client:
            result = await self._run(narrator_agent, json.dumps(context), self._config(client))
        story = result.final_output_as(Story)
        story.narration = limit_text(story.narration, ceiling)
        story.followups = story.followups[:3]
        story.source_ids = self._valid_sources(story.source_ids, session)
        if not story.source_ids:
            raise ValueError("The story has no valid references. Please retry this stop.")
        session.stories[stop.id] = story
        session.told_stories.append(story.narration)
        session.told_stories = session.told_stories[-8:]
        session.events.extend(self.events)
        return story

    @staticmethod
    def _valid_sources(ids, session):
        available = {s.id for s in session.sources}
        return list(dict.fromkeys(i for i in ids if i in available))

    async def ask(
        self, session: TourSession, question: str, image: bytes | None = None, image_type: str = "image/jpeg"
    ) -> Answer:
        if not question.strip():
            raise ValueError("Type or record a question first.")
        if image and (len(image) > 5_000_000 or image_type not in {"image/jpeg", "image/png"}):
            raise ValueError("Choose a JPEG or PNG smaller than 5 MB.")
        context = self._context(session)
        context["question"] = question[:2000]
        content = [{"type": "input_text", "text": json.dumps(context)}]
        if image:
            content.append(
                {
                    "type": "input_image",
                    "detail": "auto",
                    "image_url": f"data:{image_type};base64,{base64.b64encode(image).decode()}",
                }
            )
        async with AsyncOpenAI(api_key=self.api_key, timeout=60, max_retries=2) as client:
            result = await self._run(question_agent, [{"role": "user", "content": content}], self._config(client))
        answer = result.final_output_as(Answer)
        answer.text = limit_text(answer.text, 180)
        answer.source_ids = self._valid_sources(answer.source_ids, session)
        session.remember("user", question)
        session.remember("assistant", answer.text, answer.source_ids)
        session.answered(answer.text, answer.source_ids)
        session.events.extend(self.events)
        return answer

    async def replan(self, session: TourSession, minutes: int, request: str) -> None:
        if not 1 <= minutes <= 120 or not request.strip():
            raise ValueError("Enter a change and a remaining budget between 1 and 120 minutes.")
        async with AsyncOpenAI(api_key=self.api_key, timeout=60, max_retries=2) as client:
            config = self._config(client)
            # Add a general local researcher so a request outside initial interests can be addressed.
            research = await self._research(
                session.plan.location, list(dict.fromkeys(session.interests + ["Local places"])), request[:1000], config
            )
            result = await self._run(
                planner_agent,
                json.dumps(
                    {
                        "location": session.plan.location,
                        "interests": session.interests,
                        "remaining_minutes": minutes,
                        "requested_change": request,
                        "visited": session.visited,
                        "skipped": session.skipped,
                        "previous_plan": session.plan.model_dump(),
                        "conversation": session.messages[-12:],
                        "research": [r.model_dump() for r in research],
                    }
                ),
                config,
            )
            plan = build_plan(
                result.final_output_as(PlanDraft),
                session.plan.location,
                minutes,
                [s for r in research for s in r.sources],
                session.visited + session.skipped,
            )
        # Keep earlier citation provenance for messages that survive a replan.
        session.replace_plan(
            plan,
            [
                Research(
                    topic="Earlier references",
                    text="Reference provenance for earlier conversation only.",
                    sources=session.sources,
                )
            ]
            + research,
            request,
        )
        session.events.extend(self.events)
