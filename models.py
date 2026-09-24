"""Validated content contracts and deterministic tour state."""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass, field
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field

INTERESTS = ["History", "Architecture", "Culture", "Culinary"]
STYLES = {
    "Local storyteller": "Warm, conversational and observant. Do not claim to be a real local.",
    "Historian": "Precise, thoughtful and vivid. Distinguish documented facts from legends.",
    "Family adventure": "Playful, clear and age-inclusive. Invite observation, never risky actions.",
}


def place_key(name: str) -> str:
    return re.sub(r"[^\w]", "", name.casefold())


def safe_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return parsed.scheme in {"https", "http"} and bool(parsed.hostname) and not parsed.username
    except (ValueError, TypeError):
        return False


class Source(BaseModel):
    id: str
    title: str
    url: str


class Research(BaseModel):
    topic: str
    text: str
    sources: list[Source]


class StopDraft(BaseModel):
    name: str
    reason: str
    category: Literal["History", "Architecture", "Culture", "Culinary"]
    weight: float
    source_ids: list[str]


class PlanDraft(BaseModel):
    introduction: str
    explanation: str
    stops: list[StopDraft]
    conclusion: str


class Story(BaseModel):
    narration: str
    observation: str
    followups: list[str]
    source_ids: list[str]


class Answer(BaseModel):
    text: str
    source_ids: list[str]
    needs_research: bool = False


class Stop(BaseModel):
    id: str
    name: str
    reason: str
    category: str
    minutes: int = Field(ge=1)
    source_ids: list[str]


class TourPlan(BaseModel):
    location: str
    introduction: str
    explanation: str
    stops: list[Stop]
    conclusion: str
    budget_minutes: int


def allocate_minutes(weights: list[float], total: int) -> list[int]:
    """Largest-remainder allocation: positive integer shares sum exactly to budget."""
    if not weights or total < len(weights):
        raise ValueError("The budget must allow at least one minute per stop.")
    if any(not math.isfinite(w) or w <= 0 for w in weights):
        raise ValueError("Stop weights must be positive finite numbers.")
    spare = total - len(weights)
    normalized = [w / max(weights) for w in weights]
    scaled = [spare * w / sum(normalized) for w in normalized]
    shares = [1 + math.floor(x) for x in scaled]
    order = sorted(range(len(weights)), key=lambda i: scaled[i] % 1, reverse=True)
    for i in order[: total - sum(shares)]:
        shares[i] += 1
    return shares


def build_plan(
    draft: PlanDraft, location: str, minutes: int, sources: list[Source], excluded: list[str] | None = None
) -> TourPlan:
    if not 1 <= minutes <= 120:
        raise ValueError("Choose a budget between 1 and 120 minutes.")
    available = {s.id for s in sources if safe_url(s.url)}
    seen = {place_key(s) for s in excluded or []}
    accepted = []
    for stop in draft.stops:
        key = place_key(stop.name)
        cited = list(dict.fromkeys(s for s in stop.source_ids if s in available))
        if key and key not in seen and cited:
            accepted.append((stop, cited))
            seen.add(key)
        if len(accepted) >= min(5, minutes):
            break
    if not accepted:
        raise ValueError("No new sourced stops were found. Try a nearby area or another interest.")
    allocations = allocate_minutes([s.weight for s, _ in accepted], minutes)
    stops = [
        Stop(
            id=hashlib.sha256(place_key(s.name).encode()).hexdigest()[:12],
            name=s.name,
            reason=s.reason,
            category=s.category,
            minutes=allocated,
            source_ids=cited,
        )
        for (s, cited), allocated in zip(accepted, allocations)
    ]
    return TourPlan(
        location=location,
        introduction=draft.introduction,
        explanation=draft.explanation,
        conclusion=draft.conclusion,
        stops=stops,
        budget_minutes=minutes,
    )


@dataclass
class TourSession:
    plan: TourPlan
    interests: list[str]
    style: str
    research: list[Research]
    demo: bool = False
    index: int = 0
    remaining_minutes: int = 0
    visited: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    messages: list[dict] = field(default_factory=list)
    stories: dict[str, Story] = field(default_factory=dict)
    audio: dict[str, bytes] = field(default_factory=dict)
    events: list[dict] = field(default_factory=list)
    input_revision: int = 0
    current_answer: dict | None = None
    told_stories: list[str] = field(default_factory=list)

    @property
    def current(self) -> Stop | None:
        return self.plan.stops[self.index] if self.index < len(self.plan.stops) else None

    @property
    def sources(self) -> list[Source]:
        return list({s.id: s for r in self.research for s in r.sources}.values())

    def advance(self, skip: bool = False) -> None:
        stop = self.current
        if stop is None:
            return
        (self.skipped if skip else self.visited).append(stop.name)
        if not skip:
            self.remaining_minutes = max(0, self.remaining_minutes - stop.minutes)
        self.index += 1
        self.input_revision += 1
        self.current_answer = None

    def replace_plan(self, plan: TourPlan, research: list[Research], request: str) -> None:
        # Apply only after research and validation succeed; a failed replan leaves state intact.
        self.plan, self.research, self.index = plan, research, 0
        self.remaining_minutes = plan.budget_minutes
        self.input_revision += 1
        self.current_answer = None
        self.stories.clear()
        self.audio.clear()
        self.remember("user", "Tour change: " + request)
        self.remember("assistant", plan.explanation)

    def remember(self, role: str, text: str, source_ids: list[str] | None = None) -> None:
        self.messages.append({"role": role, "content": text, "source_ids": source_ids or []})
        self.messages = self.messages[-20:]

    def answered(self, text: str, source_ids: list[str]) -> None:
        self.current_answer = {
            "content": text,
            "source_ids": source_ids,
            "stop_id": self.current.id if self.current else None,
        }
        self.input_revision += 1
