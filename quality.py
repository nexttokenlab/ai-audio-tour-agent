"""Small deterministic checks and bounded evidence selection for model inputs."""

from __future__ import annotations

import hashlib
import re

from models import Research, Story, safe_url


def source_id(url: str) -> str:
    return "s-" + hashlib.sha256(url.encode()).hexdigest()[:12]


def cited_text(result) -> str:
    """Attach registry IDs at provider citation offsets without deleting claim text."""
    passages = []
    for response in result.raw_responses:
        for item in response.output:
            data = item.model_dump() if hasattr(item, "model_dump") else item
            for part in data.get("content", []):
                text = part.get("text")
                if not isinstance(text, str):
                    continue
                insertions = {}
                for annotation in part.get("annotations", []):
                    end = annotation.get("end_index")
                    url = annotation.get("url", "")
                    if (
                        annotation.get("type") == "url_citation"
                        and safe_url(url)
                        and isinstance(end, int)
                        and 0 <= end <= len(text)
                    ):
                        insertions.setdefault(end, set()).add(source_id(url))
                for end, ids in sorted(insertions.items(), reverse=True):
                    text = text[:end] + " [" + ", ".join(sorted(ids)) + "]" + text[end:]
                passages.append(text)
    return "\n\n".join(passages) or str(result.final_output)


def select_research(
    research: list[Research], query: str, preferred_ids: list[str], max_reports: int = 4
) -> list[Research]:
    """Rank complete reports, keeping citations intact; archive-only IDs are not evidence."""
    terms = set(re.findall(r"\w{3,}", query.casefold()))
    preferred = set(preferred_ids)
    reports = [r for r in research if r.topic != "Earlier references"]

    def score(report):
        words = set(re.findall(r"\w{3,}", report.text.casefold()))
        return len(terms & words) + 5 * len(preferred & {s.id for s in report.sources})

    # Recent evidence wins ties. Preserve whole reports rather than cutting claims off their citations.
    return sorted(reversed(reports), key=score, reverse=True)[:max_reports]


def story_problems(story: Story, allowed_ids: set[str], ceiling: int) -> list[str]:
    problems = []
    if not story.narration.strip():
        problems.append("Write a non-empty narration.")
    if len(story.narration.split()) > ceiling:
        problems.append(f"Rewrite the narration within {ceiling} words, preserving a complete ending.")
    if not any(s in allowed_ids for s in story.source_ids):
        problems.append("Cite source IDs from the supplied evidence for the narration.")
    if len({q.strip().casefold() for q in story.followups if q.strip()}) < 3:
        problems.append("Provide three distinct, non-empty follow-up questions.")
    return problems
