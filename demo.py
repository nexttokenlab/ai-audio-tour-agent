"""Deterministic, explicitly illustrative Jaipur demo. No network or API key needed."""

from models import Answer, PlanDraft, Research, Source, StopDraft, Story, TourSession, build_plan

SOURCES = [
    Source(
        id="demo-jaipur",
        title="Rajasthan Tourism · Jaipur (reference, not live-checked)",
        url="https://www.tourism.rajasthan.gov.in/jaipur.html",
    ),
]
PLACES = [
    (
        "Hawa Mahal",
        "Architecture",
        "Look at the relationship between a façade and city life.",
        "Begin by giving yourself a moment to look. At Hawa Mahal, the façade invites a different kind of attention: not just to the building as a whole, but to the repeated openings and the spaces between them. What feels delicate from a distance may feel surprisingly ordered as you look more closely. Think about the relationship between seeing and being seen. A window can connect a person to a busy street, but it can also create a boundary. That tension is a useful starting point for exploring this place. For now, choose one detail that catches your eye. We can use it to begin your next question.",
    ),
    (
        "Jantar Mantar",
        "History",
        "Explore the connection between observation and measurement.",
        "Here is a different way to approach a monument: ask what it was meant to do. Jantar Mantar invites curiosity about observation, measurement and the movement of the sky. Instead of trying to understand every instrument at once, choose one structure and study its shape. Where do you notice a straight edge, a curve or an opening? Imagine how a shadow might change as the day passes. This is a place where a question can be more useful than a quick explanation. If you want exact dates or the function of an individual instrument, switch to a researched tour so the guide can consult sources for that specific detail.",
    ),
    (
        "City Palace",
        "Culture",
        "Consider how a palace can tell several stories at once.",
        "For our final sample stop, think about how a place gathers stories over time. A palace can be a home, a place of work, a setting for ceremony and a place that visitors interpret in different ways. As you explore, choose one detail rather than trying to take everything in at once. It might be a doorway, a pattern or the way an open space frames a building. What does it make you curious about? That is where a personal tour becomes interesting: the next story follows your attention. You can ask a question, revisit an idea from an earlier stop, or simply leave some time to look.",
    ),
]


def make_demo(minutes=20, style="Local storyteller", excluded=None, coffee=False):
    places = list(PLACES)
    if coffee:
        places.insert(
            0,
            (
                "A café pause (choose a venue yourself)",
                "Culinary",
                "An illustrative break; no specific café has been verified.",
                "",
            ),
        )
    draft = PlanDraft(
        introduction="Welcome to a sample Jaipur tour. Explore one place at a time, ask questions, and change the plan as you go.",
        explanation=(
            "Added an illustrative café pause and redistributed your remaining time. Choose and verify a venue yourself."
            if coffee
            else "A sample sequence with extra time for architecture. Stop order is illustrative, not a verified walking route."
        ),
        stops=[
            StopDraft(
                name=name,
                reason=reason,
                category=category,
                weight=2 if category == "Architecture" else 1,
                source_ids=["demo-jaipur"],
            )
            for name, category, reason, _ in places
        ],
        conclusion="That is the end of this sample tour. Save your notes, or start a researched tour for a place of your choice.",
    )
    plan = build_plan(draft, "Jaipur · sample tour", minutes, SOURCES, excluded)
    return TourSession(
        plan=plan,
        interests=["History", "Architecture"],
        style=style,
        research=[Research(topic="Demo", text="Illustrative content; no live research performed.", sources=SOURCES)],
        demo=True,
        remaining_minutes=minutes,
    )


def demo_story(session):
    stop = session.current
    if stop.id in session.stories:
        return session.stories[stop.id]
    narration = next(
        (p[3] for p in PLACES if p[0] == stop.name),
        "Take a pause. This demo has not looked up a café, its opening hours or a route. Choose a venue yourself before setting off. In a live tour, your request would trigger new local research and a revised plan, while preserving the places you have already visited.",
    )
    if session.style == "Family adventure":
        narration = "Here is a little looking challenge. " + narration
    elif session.style == "Historian":
        narration = "Let us separate what we observe from what we need to research. " + narration
    story = Story(
        narration=narration,
        observation="Choose one visible detail. What question would you ask about it?",
        followups=["What should I notice?", "Explain it for a child", "How does this connect to our earlier stop?"],
        source_ids=["demo-jaipur"],
    )
    session.stories[stop.id] = story
    session.told_stories.append(story.narration)
    session.told_stories = session.told_stories[-8:]
    return story


def demo_answer(session, question):
    stop = session.current
    if "child" in question.lower():
        text = "Imagine this place as a giant question. Pick a shape you can see. What do you think it was made for? This sample reply invites observation; a live tour can research your specific question."
    elif "earlier" in question.lower():
        earlier = ", ".join(session.visited) or "no completed stops yet"
        text = f"Your session remembers: {earlier}. A live answer would connect their researched stories to {stop.name if stop else 'your tour'}."
    elif "notice" in question.lower():
        text = "Look for repetition, openings and changes in scale. Choose something you can actually see from a safe place. This is an illustrative observation prompt, not an identification of a specific feature."
    else:
        text = "This no-key demo uses scripted replies. Your question is saved in this session; switch to Live research to get a researched, contextual answer."
    session.remember("user", question)
    session.remember("assistant", text)
    session.answered(text, [])
    return Answer(text=text, source_ids=[])


def replan_demo(session, minutes, request):
    new = make_demo(
        minutes,
        session.style,
        session.visited + session.skipped,
        coffee=any(w in request.lower() for w in ("coffee", "café", "cafe", "tired")),
    )
    session.replace_plan(new.plan, new.research, request)
