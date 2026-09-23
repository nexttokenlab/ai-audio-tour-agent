from pathlib import Path

from streamlit.testing.v1 import AppTest


def button(app, label):
    return next(b for b in app.button if b.label == label)


def test_demo_journey_and_memory():
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "ai_audio_tour_agent.py", default_timeout=15).run()
    assert not app.exception
    button(app, "Explore the sample tour").click().run()
    assert not app.exception
    assert app.session_state["tour"].current.name == "Hawa Mahal"
    button(app, "What should I notice?").click().run()
    button(app, "Ask question").click().run()
    assert len(app.session_state["tour"].messages) == 2
    button(app, "Finish this stop").click().run()
    assert app.session_state["tour"].current.name == "Jantar Mantar"
    button(app, "Skip this stop").click().run()
    assert app.session_state["tour"].current.name == "City Palace"
    next(x for x in app.text_input if x.label == "What would you like to change?").set_value("I want coffee")
    app.number_input[0].set_value(10)
    button(app, "Update my remaining tour").click().run()
    assert not app.exception
    assert "café" in app.session_state["tour"].current.name
    assert app.session_state["tour"].remaining_minutes == 10
    button(app, "Reset tour").click().run()
    assert not app.exception
    assert any(b.label == "Explore the sample tour" for b in app.button)


def test_empty_live_form_is_actionable():
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "ai_audio_tour_agent.py").run()
    button(app, "Create my tour").click().run()
    assert not app.exception
    assert any("API key" in e.value for e in app.error)


def test_completed_tour_displays_conclusion():
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "ai_audio_tour_agent.py").run()
    button(app, "Explore the sample tour").click().run()
    for _ in range(3):
        button(app, "Finish this stop").click().run()
    assert not app.exception
    assert any("reached the end" in h.value for h in app.subheader)


def test_answer_does_not_appear_at_next_stop_and_draft_clears():
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "ai_audio_tour_agent.py").run()
    button(app, "Explore the sample tour").click().run()
    next(x for x in app.text_input if x.label == "Ask your guide").set_value("What should I notice?")
    button(app, "Ask question").click().run()
    assert any(h.value == "Your guide" for h in app.subheader)
    assert next(x for x in app.text_input if x.label == "Ask your guide").value == ""
    button(app, "Finish this stop").click().run()
    assert not any(h.value == "Your guide" for h in app.subheader)
    assert len(app.session_state["tour"].messages) == 2
