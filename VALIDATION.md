# Validation record

Validated locally on Python 3.12.14, September 24, 2026.

- `pytest -q`: 44 passed.
- `ruff check .`: passed.
- `pip check`: no broken requirements.
- `git diff --check`: passed.
- Credential-pattern scan of project files: clean (not a comprehensive secret audit).
- The Streamlit app starts successfully on localhost.
- Streamlit AppTest exercises onboarding, the demo journey, questions, completion, skipping, replanning, reset, conclusion and stale-answer/draft regression cases.
- A fake HTTP transport exercises the real Agents SDK's research/planning request format, structured response parsing, citation extraction and usage tracking. Other model, audio and failure tests use mocks. No paid API calls were made.
- A separate code reviewer found and verified fixes for attachment reuse and stale answers across stops.

Not verified: live model availability, factual quality, search results, speech/transcription quality, actual photo interpretation, browser microphone support, visual layout, responsive behavior and focus/contrast. Browser access to localhost was blocked because the browser tool could not verify its admin-enforced security policy. No alternative browser access was attempted.

The included GitHub Actions workflow repeats lint and automated tests on push and pull request. See the repository's Actions tab for its current result.

Optimization regression coverage: provider citation-offset mapping, relevant-context selection, one-shot factual lookup, unresolved-search abstention, transactional lookup failures, story revision/cache behavior, empty-story rejection, extreme finite weights, malformed source URLs, and usage accounting across manager reuse. No measured live latency, cost or factuality improvement is claimed.
