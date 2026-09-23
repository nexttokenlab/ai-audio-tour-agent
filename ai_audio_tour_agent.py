"""Modified September 2026: interactive, session-scoped Streamlit experience."""

from __future__ import annotations

import asyncio
import os
from io import BytesIO

from dotenv import load_dotenv
import streamlit as st
from PIL import Image, UnidentifiedImageError

load_dotenv()

from audio import audio_key, synthesize, transcribe  # noqa: E402
from demo import demo_answer, demo_story, make_demo, replan_demo  # noqa: E402
from manager import TourManager  # noqa: E402
from models import INTERESTS, STYLES, safe_url  # noqa: E402

st.set_page_config(page_title="AI Audio Tour · Explore at your pace", layout="wide")


def attempt(action, label):
    try:
        with st.spinner(label):
            return action()
    except Exception as exc:
        # Avoid displaying provider error bodies, API keys or uploaded data.
        if isinstance(exc, ValueError):
            st.error(str(exc))
        else:
            st.error(
                "That request did not finish. Your tour is still here. Check your API key, connection and available quota, then retry."
            )
        return None


def references(session, ids):
    selected = [s for s in session.sources if s.id in ids and safe_url(s.url)]
    if selected:
        st.caption("References" if session.demo else "Sources used for this passage")
        for source in selected:
            st.link_button(source.title, source.url)


def play_passage(session, text, key, api_key, voice):
    cache_key = audio_key(text, session.style, voice)
    if session.demo:
        st.caption("Demo shows sample text. Start a live tour to generate AI narration.")
        return
    if st.button("Generate audio", key=f"generate-{key}", disabled=not api_key):
        data = attempt(lambda: synthesize(api_key, text, session.style, voice), "Preparing narration…")
        if data:
            session.audio[cache_key] = data
    if cache_key in session.audio:
        st.audio(session.audio[cache_key], format="audio/mp3")
        st.download_button(
            "Download this audio",
            session.audio[cache_key],
            file_name="tour-passage.mp3",
            mime="audio/mpeg",
            key=f"download-{key}",
        )
    st.caption("AI-generated voice. Playback starts only when you press play.")


with st.sidebar:
    st.header("Settings")
    api_key = st.text_input(
        "OpenAI API key",
        type="password",
        value=os.getenv("OPENAI_API_KEY", ""),
        help="Used for this session. Never saved to a file by the app.",
    )
    voice = st.selectbox("Narration voice", ["nova", "coral", "alloy"])
    st.caption("Live mode sends your location, questions and optional media to OpenAI. Research also uses web search.")
    st.caption("Session memory resets when you reset the tour or lose the browser session.")
    if st.button("Reset tour", use_container_width=True):
        # Clear tour-related widget values as well as conversation and media.
        for name in list(st.session_state):
            if name != "api-key":
                del st.session_state[name]
        st.rerun()

st.title("Explore at your pace.")
st.write("A story at each stop. Room for your questions. A plan that can change.")

session = st.session_state.get("tour")
if session is None:
    live_tab, demo_tab = st.tabs(["Plan a tour", "Try the Jaipur demo"])
    with live_tab:
        with st.form("new-tour"):
            location = st.text_input(
                "Where would you like to explore?", placeholder="A landmark or small neighborhood", max_chars=200
            )
            interests = st.multiselect("Your interests", INTERESTS, default=["History", "Architecture"])
            c1, c2 = st.columns(2)
            minutes = c1.slider("Exploration budget · minutes", 5, 60, 20, 5)
            style = c2.selectbox("Storytelling style", list(STYLES))
            st.caption("Includes listening and time to look around. Walking times and opening hours are not verified.")
            submitted = st.form_submit_button("Create my tour", type="primary")
        if submitted:
            if not api_key or not location.strip() or not interests:
                st.error("Add your API key in Settings, enter a location, and choose at least one interest.")
            else:
                progress = st.empty()
                new = attempt(
                    lambda: asyncio.run(
                        TourManager(api_key, progress.info).create(location, interests, minutes, style)
                    ),
                    "Researching your tour…",
                )
                progress.empty()
                if new:
                    st.session_state.tour = new
                    st.rerun()
    with demo_tab:
        st.subheader("A little Jaipur, one stop at a time.")
        st.write(
            "Try short stories, sample conversations, visited-stop memory and a change of plans. No API key required."
        )
        st.info("Illustrative demo: scripted content and replies, no live search, audio or venue verification.")
        if st.button("Explore the sample tour", type="primary"):
            st.session_state.tour = make_demo()
            st.rerun()
    st.stop()

if session.demo:
    st.info("Jaipur demo · illustrative content and scripted replies · no live research or audio")

st.subheader(session.plan.location)
st.caption(
    f"{session.remaining_minutes} min remaining in your budget · {len(session.visited)} completed · {session.style}"
)
st.write(session.plan.introduction)
with st.expander("Listen to the welcome"):
    play_passage(session, session.plan.introduction, "welcome", api_key, voice)
st.caption("Suggested places, not turn-by-turn navigation. Check access and a map before moving.")

story_tab, plan_tab, notes_tab = st.tabs(["At this stop", "Change the plan", "Tour notes"])
with story_tab:
    question_key = f"question-{session.input_revision}"
    if "pending_transcript" in st.session_state:
        st.session_state[question_key] = st.session_state.pop("pending_transcript")
    stop = session.current
    if stop is None:
        st.subheader("You’ve reached the end.")
        st.write(session.plan.conclusion)
        play_passage(session, session.plan.conclusion, "closing", api_key, voice)
        st.write("You can review your notes, change the plan, or reset to explore somewhere new.")
    else:
        st.caption(f"Stop {session.index + 1} of {len(session.plan.stops)} · {stop.minutes} min to listen and explore")
        st.header(stop.name)
        st.write(stop.reason)
        story = session.stories.get(stop.id)
        if session.demo and story is None:
            story = demo_story(session)
        if story is None:
            if st.button("Tell me this story", type="primary", disabled=not api_key):
                story = attempt(lambda: asyncio.run(TourManager(api_key).story(session)), "Finding the story…")
        if story:
            st.write(story.narration)
            references(session, story.source_ids)
            play_passage(session, story.narration, stop.id, api_key, voice)
            st.subheader("Take a closer look")
            st.write(story.observation)
            st.subheader("Follow your curiosity")
            for i, suggestion in enumerate(story.followups):
                if st.button(suggestion, key=f"followup-{stop.id}-{i}"):
                    st.session_state[question_key] = suggestion
        st.text_input(
            "Ask your guide", key=question_key, max_chars=2000, placeholder="What should I notice about this building?"
        )
        image_bytes, image_type = None, "image/jpeg"
        with st.expander("Add a photo or record a question"):
            st.caption(
                "Recorded questions are transcribed before sending. Pause narration before recording; live interruption is not supported."
            )
            recording = st.audio_input(
                "Record a question", key=f"recording-{session.input_revision}", disabled=session.demo
            )
            if recording and st.button("Use this recording", disabled=not api_key):
                transcript = attempt(lambda: transcribe(api_key, recording.getvalue()), "Transcribing…")
                if transcript:
                    st.session_state.pending_transcript = transcript
                    st.rerun()
            photo = st.file_uploader(
                "Photo of a detail (optional)",
                type=["jpg", "jpeg", "png"],
                key=f"photo-{session.input_revision}",
                disabled=session.demo,
            )
            if photo:
                try:
                    raw = photo.getvalue()
                    if len(raw) > 5_000_000:
                        raise ValueError("Choose a photo smaller than 5 MB.")
                    with Image.open(BytesIO(raw)) as picture:
                        if picture.width * picture.height > 20_000_000:
                            raise ValueError("Choose a photo smaller than 20 megapixels.")
                        # Re-encode to remove location metadata and ensure genuine image bytes.
                        picture.thumbnail((1600, 1600))
                        encoded = BytesIO()
                        picture.convert("RGB").save(encoded, format="JPEG")
                        image_bytes = encoded.getvalue()
                    st.image(image_bytes, caption="This photo will be sent with your next question.", width=260)
                except (ValueError, UnidentifiedImageError, OSError, Image.DecompressionBombError):
                    st.error("Could not read that photo. Choose a JPEG or PNG under 5 MB and 20 megapixels.")
        if st.button("Ask question", type="primary", disabled=not session.demo and not api_key):
            question = st.session_state.get(question_key, "").strip()
            if not question:
                st.error("Enter a question first.")
            else:
                answer = attempt(
                    lambda: (
                        demo_answer(session, question)
                        if session.demo
                        else asyncio.run(TourManager(api_key).ask(session, question, image_bytes, image_type))
                    ),
                    "Thinking about your question…",
                )
                if answer:
                    st.rerun()
        if session.current_answer and session.current_answer["stop_id"] == stop.id:
            last = session.current_answer
            st.subheader("Your guide")
            st.write(last["content"])
            references(session, last["source_ids"])
            play_passage(session, last["content"], "answer", api_key, voice)
        st.divider()
        next_col, skip_col = st.columns(2)
        if next_col.button("Finish this stop", use_container_width=True):
            session.advance()
            st.rerun()
        if skip_col.button("Skip this stop", use_container_width=True):
            session.advance(skip=True)
            st.rerun()

with plan_tab:
    st.subheader("Make room for a different plan.")
    st.write(session.plan.explanation)
    for i, planned in enumerate(session.plan.stops):
        status = "Completed or skipped" if i < session.index else "Next" if i == session.index else "Later"
        st.write(f"**{planned.name}** · {planned.minutes} min · {status}")
        st.caption(planned.reason)
    with st.form("replan"):
        new_minutes = st.number_input(
            "Time you have now · minutes", min_value=1, max_value=120, value=max(1, session.remaining_minutes)
        )
        change = st.text_input(
            "What would you like to change?",
            max_chars=1000,
            placeholder="I’m tired, I have ten minutes, and I want coffee.",
        )
        new_style = st.selectbox("Storytelling style", list(STYLES), index=list(STYLES).index(session.style))
        update = st.form_submit_button("Update my remaining tour", type="primary")
    if update:
        if not change.strip():
            st.error("Describe the change you want to make.")
        elif not session.demo and not api_key:
            st.error("Add your API key in Settings to update a live tour.")
        else:

            def apply_change():
                if session.demo:
                    replan_demo(session, int(new_minutes), change)
                else:
                    asyncio.run(TourManager(api_key).replan(session, int(new_minutes), change))
                session.style = new_style
                return True

            if attempt(apply_change, "Updating the remaining stops…"):
                st.rerun()
    st.caption("Completed and skipped places stay out of the new plan. Budget is manual, not a GPS timer.")

with notes_tab:
    st.subheader("Your conversation")
    if not session.messages:
        st.write("Questions and answers will appear here as you explore.")
    for message in session.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
            references(session, message["source_ids"])
    st.write("**Visited:** " + (", ".join(session.visited) or "No completed stops yet"))
    st.write("**Skipped:** " + (", ".join(session.skipped) or "None"))
    notes = "\n\n".join(f"{m['role']}: {m['content']}" for m in session.messages)
    st.download_button(
        "Download tour notes",
        session.plan.model_dump_json(indent=2) + "\n\n" + notes,
        file_name="tour-notes.txt",
        mime="text/plain",
    )
    with st.expander("Research sources"):
        references(session, [s.id for s in session.sources])
    with st.expander("Run details"):
        st.caption(
            "Per-agent latency and token usage. This is not a billing estimate; web search and audio have separate charges."
        )
        if session.events:
            st.dataframe(session.events, hide_index=True)
        else:
            st.write("No API calls in this demo.")
