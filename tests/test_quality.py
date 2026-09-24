import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from demo import make_demo
from manager import TourManager
from models import Answer, Research, Source, Story, allocate_minutes, safe_url
from quality import cited_text, select_research, source_id
from test_manager import result


def test_citation_offsets_link_claims_without_erasing_them():
    text = "First claim. Second claim."
    response = SimpleNamespace(
        raw_responses=[
            SimpleNamespace(
                output=[
                    {
                        "content": [
                            {
                                "text": text,
                                "annotations": [
                                    {"type": "url_citation", "url": "https://one.test", "end_index": 12},
                                    {"type": "url_citation", "url": "https://two.test", "end_index": len(text)},
                                    {"type": "url_citation", "url": "javascript:bad", "end_index": 1},
                                    {"type": "url_citation", "url": "https://bad.test", "end_index": 999},
                                ],
                            }
                        ]
                    }
                ]
            )
        ],
        final_output=text,
    )
    mapped = cited_text(response)
    assert mapped == f"First claim. [{source_id('https://one.test')}] Second claim. [{source_id('https://two.test')}]"


def test_context_ranks_relevant_reports_and_omits_archive():
    session = make_demo()
    session.research = [
        Research(
            topic=f"topic-{i}",
            text="A distant park.",
            sources=[Source(id=str(i), title="Source", url=f"https://example.org/{i}")],
        )
        for i in range(8)
    ]
    relevant = Research(
        topic="History",
        text="Hawa Mahal windows and architecture.",
        sources=[Source(id="demo-jaipur", title="Jaipur", url="https://example.org/jaipur")],
    )
    session.research += [relevant, Research(topic="Earlier references", text="old", sources=[])]
    selected = select_research(session.research, "windows", ["demo-jaipur"])
    assert selected[0] == relevant and len(selected) == 4
    context = TourManager("key")._context(session, "windows")
    assert len(context["research"]) == 4
    assert all(r["topic"] != "Earlier references" for r in context["research"])
    assert len(json.dumps(context["research"])) < len(json.dumps([r.model_dump() for r in session.research]))


def test_missing_fact_triggers_one_targeted_search(monkeypatch):
    session = make_demo()
    manager = TourManager("key")
    evidence = Research(
        topic="Follow-up",
        text="New evidence",
        sources=[Source(id="fresh", title="Official", url="https://example.org")],
    )
    run = AsyncMock(
        side_effect=[
            result(Answer(text="Need evidence", source_ids=[], needs_research=True)),
            result(Answer(text="A sourced answer.", source_ids=["fresh"])),
        ]
    )
    research = AsyncMock(return_value=[evidence])
    monkeypatch.setattr(manager, "_run", run)
    monkeypatch.setattr(manager, "_research", research)
    answer = asyncio.run(manager.ask(session, "When was it built?"))
    assert answer.source_ids == ["fresh"]
    assert run.await_count == 2 and research.await_count == 1
    assert "Hawa Mahal" in research.call_args.args[2]
    assert "research_attempted" in run.call_args.args[1][0]["content"][0]["text"]
    assert "fresh" in [s.id for s in session.sources]
    assert len(session.messages) == 2


def test_unresolved_search_abstains_without_loop(monkeypatch):
    session = make_demo()
    manager = TourManager("key")
    monkeypatch.setattr(
        manager,
        "_run",
        AsyncMock(return_value=result(Answer(text="Unsupported guess", source_ids=[], needs_research=True))),
    )
    search = AsyncMock(return_value=session.research)
    monkeypatch.setattr(manager, "_research", search)
    answer = asyncio.run(manager.ask(session, "Is it open right now?"))
    assert "couldn’t establish" in answer.text
    assert search.await_count == 1
    assert not answer.needs_research


def test_failed_followup_search_is_transactional(monkeypatch):
    session = make_demo()
    before = list(session.research)
    manager = TourManager("key")
    monkeypatch.setattr(
        manager,
        "_run",
        AsyncMock(return_value=result(Answer(text="Need evidence", source_ids=[], needs_research=True))),
    )
    monkeypatch.setattr(manager, "_research", AsyncMock(side_effect=RuntimeError("offline")))
    with pytest.raises(RuntimeError):
        asyncio.run(manager.ask(session, "Hours?"))
    assert session.research == before and not session.messages and session.input_revision == 0


def test_story_gets_one_rewrite_before_fallback(monkeypatch):
    session = make_demo()
    manager = TourManager("key")
    bad = Story(narration="Too long. " * 200, observation="Look", followups=["one"], source_ids=[])
    good = Story(
        narration="A complete, sourced story.",
        observation="Look",
        followups=["One?", "Two?", "Three?"],
        source_ids=["demo-jaipur"],
    )
    run = AsyncMock(side_effect=[result(bad), result(good)])
    monkeypatch.setattr(manager, "_run", run)
    answer = asyncio.run(manager.story(session))
    assert answer.narration == good.narration
    assert "revision" in json.loads(run.call_args.args[1])
    asyncio.run(manager.story(session))
    assert run.await_count == 2


def test_empty_story_after_rewrite_is_not_cached(monkeypatch):
    session = make_demo()
    manager = TourManager("key")
    monkeypatch.setattr(
        manager,
        "_run",
        AsyncMock(return_value=result(Story(narration=" ", observation="", followups=[], source_ids=[]))),
    )
    with pytest.raises(ValueError, match="empty"):
        asyncio.run(manager.story(session))
    assert not session.stories


def test_huge_finite_weights_do_not_overflow():
    assert sum(allocate_minutes([1e308, 1e308], 60)) == 60


def test_malformed_source_url_fails_closed():
    assert not safe_url("http://[")


def test_reused_manager_does_not_duplicate_usage_events(monkeypatch):
    session = make_demo()
    manager = TourManager("key")

    async def run(*args):
        manager.events.append({"agent": "Companion", "seconds": 1})
        return result(Answer(text="A reply", source_ids=[]))

    monkeypatch.setattr(manager, "_run", run)
    asyncio.run(manager.ask(session, "Hello"))
    asyncio.run(manager.ask(session, "Explain simply"))
    assert len(session.events) == 2
