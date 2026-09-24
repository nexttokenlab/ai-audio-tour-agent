import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from demo import make_demo
from manager import TourManager, citation_sources, limit_text
from models import Answer, PlanDraft, StopDraft, Story


def result(output, citations=True):
    annotation = {"type": "url_citation", "url": "https://example.org/place", "title": "Official place"}
    return SimpleNamespace(
        final_output=output,
        final_output_as=lambda _: output,
        raw_responses=[SimpleNamespace(output=[{"content": [{"annotations": [annotation] if citations else []}]}])],
    )


def test_sources_come_from_annotations_only():
    response = result("Invented https://evil.example/ URL")
    assert [s.url for s in citation_sources(response)] == ["https://example.org/place"]
    assert not citation_sources(result("https://fake.example/", citations=False))


def test_new_tour_uses_research_and_planner_weights(monkeypatch):
    manager = TourManager("test-key")
    sid = citation_sources(result("Research"))[0].id
    draft = PlanDraft(
        introduction="Hello",
        explanation="Weighted by interests",
        conclusion="Goodbye",
        stops=[
            StopDraft(name=name, reason="Research-supported", category="History", weight=weight, source_ids=[sid])
            for name, weight in [("Museum", 4), ("Square", 1)]
        ],
    )

    async def fake_run(agent, prompt, config):
        return result(draft if agent.name == "TourPlanner" else "Cited research")

    monkeypatch.setattr(manager, "_run", fake_run)
    session = asyncio.run(manager.create("City", ["History", "Architecture"], 20, "Historian"))
    assert len(session.research) == 2
    assert sum(s.minutes for s in session.plan.stops) == 20
    assert session.plan.stops[0].minutes > session.plan.stops[1].minutes
    assert session.style == "Historian"


def test_missing_research_citations_fail_closed(monkeypatch):
    manager = TourManager("test-key")
    monkeypatch.setattr(manager, "_run", AsyncMock(return_value=result("Uncited research", citations=False)))
    with pytest.raises(ValueError, match="no source citations"):
        asyncio.run(manager.create("City", ["History"], 10, "Historian"))


def test_story_bounded_and_cached(monkeypatch):
    session = make_demo()
    manager = TourManager("test-key")
    story = Story(
        narration="Long story. " * 200,
        observation="Look around",
        followups=["a", "b", "c", "d"],
        source_ids=["demo-jaipur", "invented"],
    )
    runner = AsyncMock(return_value=result(story))
    monkeypatch.setattr(manager, "_run", runner)
    answer = asyncio.run(manager.story(session))
    assert len(answer.narration.split()) <= 180
    assert answer.source_ids == ["demo-jaipur"]
    assert len(answer.followups) == 3
    asyncio.run(manager.story(session))
    assert runner.await_count == 2


def test_question_carries_history_and_photo_and_filters_citations(monkeypatch):
    session = make_demo()
    session.remember("user", "Remember my interest in windows")
    manager = TourManager("test-key")
    runner = AsyncMock(return_value=result(Answer(text="Answer", source_ids=["demo-jaipur", "fake"])))
    monkeypatch.setattr(manager, "_run", runner)
    response = asyncio.run(manager.ask(session, "What is this?", b"image"))
    content = runner.call_args.args[1][0]["content"]
    assert "Remember my interest in windows" in content[0]["text"]
    assert content[1]["type"] == "input_image"
    assert response.source_ids == ["demo-jaipur"]
    assert session.messages[-1]["content"] == "Answer"


def test_failed_question_does_not_modify_memory(monkeypatch):
    session = make_demo()
    manager = TourManager("test-key")
    monkeypatch.setattr(manager, "_run", AsyncMock(side_effect=RuntimeError("API unavailable")))
    with pytest.raises(RuntimeError):
        asyncio.run(manager.ask(session, "Hello"))
    assert session.messages == []


def test_live_replan_keeps_visited_and_previous_citations(monkeypatch):
    session = make_demo()
    session.advance()
    manager = TourManager("test-key")
    sid = citation_sources(result("Research"))[0].id
    draft = PlanDraft(
        introduction="Welcome back",
        explanation="Coffee break",
        conclusion="Bye",
        stops=[
            StopDraft(name=session.visited[0], reason="Repeat", category="History", weight=1, source_ids=[sid]),
            StopDraft(name="A sourced café", reason="Coffee", category="Culinary", weight=1, source_ids=[sid]),
        ],
    )

    async def fake_run(agent, prompt, config):
        return result(draft if agent.name == "TourPlanner" else "Café research")

    monkeypatch.setattr(manager, "_run", fake_run)
    asyncio.run(manager.replan(session, 10, "I want coffee"))
    assert [s.name for s in session.plan.stops] == ["A sourced café"]
    assert session.remaining_minutes == 10
    assert "demo-jaipur" in [s.id for s in session.sources]


def test_text_limiter_retains_sentence_boundary():
    assert limit_text("One sentence. Another sentence. And more here.", 5) == "One sentence. Another sentence."
