import math

import pytest

from demo import demo_answer, demo_story, make_demo, replan_demo
from models import PlanDraft, Source, StopDraft, allocate_minutes, build_plan, safe_url


@pytest.mark.parametrize("weights,total", [([1, 1, 1], 20), ([8, 1], 7), ([1], 1), ([1, 3, 7], 60)])
def test_allocations_are_positive_exact_and_weighted(weights, total):
    values = allocate_minutes(weights, total)
    assert sum(values) == total
    assert min(values) >= 1
    assert values[weights.index(max(weights))] >= values[weights.index(min(weights))]


@pytest.mark.parametrize("weights,total", [([], 10), ([0, 1], 5), ([math.nan], 3), ([math.inf], 5), ([1, 1], 1)])
def test_invalid_budgets_rejected(weights, total):
    with pytest.raises(ValueError):
        allocate_minutes(weights, total)


def test_sources_duplicates_and_visited_filtered():
    stops = [
        StopDraft(name=name, reason="A reason", category="History", weight=1, source_ids=ids)
        for name, ids in [("Visited Place", ["s"]), ("A place", ["s"]), ("A PLACE!", ["s"]), ("Invented", ["fake"])]
    ]
    draft = PlanDraft(introduction="Welcome", explanation="Plan", stops=stops, conclusion="Bye")
    plan = build_plan(draft, "City", 10, [Source(id="s", title="Source", url="https://example.org")], ["visited place"])
    assert [s.name for s in plan.stops] == ["A place"]
    assert plan.stops[0].minutes == 10
    assert plan.introduction == "Welcome" and plan.conclusion == "Bye"


def test_complete_skip_replan_preserves_memory_and_budget():
    session = make_demo()
    first = session.current
    demo_story(session)
    demo_answer(session, "What should I notice?")
    session.advance()
    assert session.remaining_minutes == 20 - first.minutes
    before = session.remaining_minutes
    skipped = session.current.name
    session.advance(skip=True)
    assert session.remaining_minutes == before
    session.audio["old"] = b"mp3"
    replan_demo(session, 10, "I want coffee")
    assert session.remaining_minutes == sum(s.minutes for s in session.plan.stops) == 10
    assert first.name not in [s.name for s in session.plan.stops]
    assert skipped not in [s.name for s in session.plan.stops]
    assert session.messages[0]["content"] == "What should I notice?"
    assert not session.audio and not session.stories
    assert "café" in session.current.name


def test_session_isolation_and_bounded_memory():
    a, b = make_demo(), make_demo()
    for i in range(30):
        a.remember("user", str(i))
    a.audio["one"] = b"private audio"
    a.advance()
    assert len(a.messages) == 20
    assert not b.messages and not b.audio and not b.visited


def test_failed_replan_leaves_session_unchanged():
    session = make_demo()
    session.visited = [s.name for s in session.plan.stops]
    original = session.plan
    with pytest.raises(ValueError):
        replan_demo(session, 5, "history")
    assert session.plan is original


@pytest.mark.parametrize("url", ["javascript:alert(1)", "file:///etc/passwd", "https://user:password@example.org"])
def test_unsafe_source_links_rejected(url):
    assert not safe_url(url)


def test_answer_and_media_drafts_do_not_follow_visitor_to_next_stop():
    session = make_demo()
    demo_answer(session, "What is this?")
    assert session.current_answer["stop_id"] == session.current.id
    assert session.input_revision == 1
    session.advance()
    assert session.current_answer is None
    assert session.input_revision == 2
    assert len(session.messages) == 2
    demo_answer(session, "What is next?")
    replan_demo(session, 10, "coffee")
    assert session.current_answer is None
    assert session.input_revision == 4
