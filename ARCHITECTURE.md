# System design

## Ownership

`TourManager` owns model execution, not state transitions. `TourSession` owns the current plan, completed/skipped places, bounded chat history, generated stories, audio bytes and usage events. Streamlit owns a single `TourSession` per browser session. No cached global OpenAI clients or global credentials are used.

`agent.py` defines specialist agents that produce compact source-cited research rather than full-length scripts. Research and structured generation are separate stages. The planner composes grounded stops; a narrator generates one stop at a time; a companion answers questions with the current stop and history.

## State transitions

- **Create:** validate inputs → concurrent expert research → require citation annotations → structured plan → filter unsupported/duplicate stops → allocate integer minutes → create session. A failure creates no partial session.
- **Tell story:** return cached story if available, otherwise generate from current context → bound word count → filter source IDs → cache on success.
- **Ask:** send current stop, research, recent messages and optional image → validate response → append user and assistant messages only on success. An unanswered question can be retried without duplicating history.
- **Finish:** add current place to visited, debit its allocated minutes, advance index.
- **Skip:** add current place to skipped and advance without debiting the budget. Unspent time remains available for a replan.
- **Replan:** research new constraints → propose plan → exclude completed and skipped names → validate budgets and provenance → atomically replace remaining plan. Preserve conversation and earlier reference provenance. Clear old story/audio caches so outdated narration is not reused.
- **Reset:** discard session state and media. Nothing is deleted from a persistent store because there is none.

## Budgets

The planner proposes positive relative weights. A largest-remainder allocator reserves one minute per stop and distributes the remaining minutes proportionally, with a deterministic tie break. Allocations sum exactly to the chosen budget. A plan includes at most five stops and never more stops than available minutes.

Stories target roughly one minute with a hard word ceiling. The remaining stop allocation is time to explore; no walking-time guarantee is implied. Audio is on demand, never generated for an entire 60-minute script in one request.

## Grounding

Source IDs are derived from URLs in provider `url_citation` annotations. Model-authored links cannot populate the source registry. Only HTTP(S) links without embedded credentials are rendered. Plans and stories must reference known IDs; answers can abstain or discuss an image without sources. The UI renders source links adjacent to generated passages.

This validates provenance, not factual entailment. The model can still attach the wrong known source to a claim. Add claim-level evidence spans and an independent evaluation set before describing output as verified. Prompts treat retrieved content as untrusted and prohibit invented orientation, routes and opening hours.

## Failure and resource behavior

API requests have timeouts, SDK retries and an agent-turn ceiling. Independent research tasks finish through `gather(..., return_exceptions=True)`; any failed branch prevents a partially researched plan. Errors leave the existing tour intact. User-visible provider errors are generic to avoid exposing request payloads or credentials.

Audio bytes are stored only in the active session and keyed by content, style and voice. Images are re-encoded before submission to remove metadata. Recorded audio is sent only when the user chooses transcription; the transcript remains editable before asking. Tracing uploads are disabled explicitly.

## Extension points

- A places provider should supply stable place IDs, coordinates, availability and routing. Validate aliases and distance in code before committing a plan.
- A persistent session repository should replace in-memory state behind authenticated per-user access.
- A realtime transport should coordinate playback cancellation and speech turn detection; the current recorded-turn UI does not implement either.
- A usage ledger should include web search, audio and image costs as well as text tokens. Current per-agent events are development diagnostics.

## Evaluation matrix

| Behavior | Automated now | Live acceptance needed |
|---|---|---|
| Budget totals and exclusions | Deterministic unit tests | Place aliases and route feasibility |
| Conversation context | Mock agent and UI tests | Answer quality and factual consistency |
| Sources | Annotation extraction and filtering | Claim-to-source support |
| Audio | Explicit-key, style and payload tests | Voice quality, latency and device playback |
| Photos | Input path and size constraints | Visual understanding on varied landmarks |
| Recovery | Failed research/question/replan tests | Provider quota, refusal and network behavior |
| Demo | Full Streamlit interaction flow | Visual browser inspection |
