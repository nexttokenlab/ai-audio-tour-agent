"""Exercise the real Agents SDK against a fake HTTP transport, without API spending."""

import asyncio
import json

import httpx
from openai import AsyncOpenAI

import manager as manager_module
from manager import TourManager


def test_real_sdk_research_plan_citations_and_usage(monkeypatch):
    requests = []

    def respond(request):
        body = json.loads(request.content)
        requests.append(body)
        assert request.headers["authorization"] == "Bearer test-session-key"
        annotations = []
        if body.get("tools"):
            text = "The museum is a useful history stop."
            annotations = [
                {
                    "type": "url_citation",
                    "url": "https://example.org/museum",
                    "title": "Museum",
                    "start_index": 0,
                    "end_index": len(text),
                }
            ]
        else:
            # Reuse the exact provenance ID generated from the research annotation.
            import hashlib

            source_id = "s-" + hashlib.sha256(b"https://example.org/museum").hexdigest()[:12]
            text = json.dumps(
                {
                    "introduction": "Welcome",
                    "explanation": "A compact visit",
                    "conclusion": "Goodbye",
                    "stops": [
                        {
                            "name": "Museum",
                            "reason": "History",
                            "category": "History",
                            "weight": 1,
                            "source_ids": [source_id],
                        }
                    ],
                }
            )
        return httpx.Response(
            200,
            json={
                "id": "resp_test",
                "object": "response",
                "created_at": 0,
                "status": "completed",
                "model": "gpt-4.1-mini",
                "output": [
                    {
                        "id": "msg_test",
                        "type": "message",
                        "role": "assistant",
                        "status": "completed",
                        "content": [{"type": "output_text", "text": text, "annotations": annotations}],
                    }
                ],
                "usage": {
                    "input_tokens": 10,
                    "output_tokens": 20,
                    "total_tokens": 30,
                    "input_tokens_details": {"cached_tokens": 0},
                    "output_tokens_details": {"reasoning_tokens": 0},
                },
            },
        )

    def client(**kwargs):
        return AsyncOpenAI(
            api_key=kwargs["api_key"], http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond))
        )

    monkeypatch.setattr(manager_module, "AsyncOpenAI", client)
    session = asyncio.run(TourManager("test-session-key").create("City", ["History"], 10, "Historian"))
    assert session.current.name == "Museum"
    assert session.current.minutes == 10
    assert session.sources[0].url == "https://example.org/museum"
    assert len(requests) == 2
    assert requests[0]["tool_choice"] == "required"
    assert requests[1]["text"]["format"]["type"] == "json_schema"
    assert session.events[0]["input_tokens"] == 10
