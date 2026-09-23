---
name: AI Audio Tour
description: A native Streamlit interface for exploring one stop at a time.
colors:
  primary: "#126553"
  background: "#FAF9F5"
  secondary-background: "#EEEDE6"
  text: "#243831"
typography:
  body:
    fontFamily: "sans-serif"
---

# Design System: AI Audio Tour

## Overview

The interface retains Streamlit's native controls and light theme. It supports an operate-mode experience: create a tour, listen or read at a stop, ask a question, and adjust the remaining plan. Copy is conversational and controls name their actions.

This document records the implementation in `ai_audio_tour_agent.py` and `.streamlit/config.toml`. It is based on source inspection; desktop/mobile rendering, contrast and keyboard behavior have not been visually verified. No new visual identity or custom component library is introduced.

## Colors

The theme uses a deep green primary accent, a warm light page background, a slightly darker secondary surface and dark green text. These roles map directly to Streamlit's `primaryColor`, `backgroundColor`, `secondaryBackgroundColor` and `textColor`. Native components inherit the theme.

## Typography

Streamlit's sans-serif theme setting supplies the font. Native title, header, subheader, body and caption elements establish hierarchy. Captions carry budgets, source context and operational limitations. Font sizes, weights and line heights remain framework defaults; the project defines no custom type scale.

## Layout

The page uses Streamlit's wide layout. Settings, the API key, voice selection and reset action live in the sidebar. The main title introduces the experience without a separate decorative hero.

Before a tour starts, tabs separate live planning from the explicitly illustrative Jaipur demo. An active tour presents its location, remaining budget and introduction above three tabs: **At this stop**, **Change the plan** and **Tour notes**. The first supports sequential exploration; the second exposes the itinerary and replanning form; the third holds history, downloads and sources.

Two-column groups pair related inputs and finish/skip actions. Expanders contain welcome audio, optional media, research sources and run details. Responsive reflow and spacing are delegated to Streamlit; no custom breakpoints are defined.

## Elevation & Depth

The implementation uses native surfaces, expanders and a divider. It adds no custom shadows, textures or layered decorative effects.

## Shapes

Buttons, fields, tabs and media controls retain their Streamlit shapes. No project-specific radius or border scale is defined.

## Components

- Primary buttons submit core actions: create, explore the sample, generate a story, ask and update the tour. Audio generation, downloads and source links use native controls.
- Spinners and progress text explain pending work. Errors offer recovery while the existing tour remains available. Missing credentials disable dependent actions or produce validation guidance.
- Demo notices distinguish scripted content from live research. Audio includes an AI-voice disclosure and requires explicit playback. Optional photos show a preview before submission.
- A successful answer advances the input revision, clearing question and media widgets on rerun. Failed requests retain drafts. Finishing, skipping or replanning also advances the revision and clears the current answer.
- The current answer is associated with a stop ID and appears only at that stop. Conversation history remains separate in Tour notes, subject to the session's bounded memory. Replanning preserves earlier citation provenance.
- Empty conversation and completed-tour states explain what happened and offer relevant next actions. Reset clears tour state.

## Do's and Don'ts

- Keep additions consistent with native Streamlit controls and the configured light theme.
- Keep the current stop, its story and relevant actions easy to identify.
- Preserve explicit demo labeling, source links and manual-budget explanations.
- Keep attachments and displayed answers scoped to the relevant interaction and stop.
- Do not describe suggested stops as verified navigation or invent venue verification.
- Do not invent custom spacing, typography or interaction tokens that the implementation does not define.
- Do not treat source inspection or automated tests as visual verification.
