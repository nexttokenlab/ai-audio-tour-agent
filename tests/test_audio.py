from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import audio


def test_tts_uses_explicit_key_style_and_in_memory_bytes(monkeypatch):
    client = MagicMock()
    client.__enter__.return_value = client
    client.audio.speech.create.return_value = SimpleNamespace(content=b"audio")
    factory = MagicMock(return_value=client)
    monkeypatch.setattr(audio, "OpenAI", factory)
    assert audio.synthesize("session-key", "A short story", "Historian", "coral") == b"audio"
    assert factory.call_args.kwargs["api_key"] == "session-key"
    call = client.audio.speech.create.call_args.kwargs
    assert call["voice"] == "coral"
    assert "documented facts" in call["instructions"]


def test_audio_cache_varies_with_style_voice_and_content():
    assert (
        len(
            {
                audio.audio_key("a", "Historian", "nova"),
                audio.audio_key("b", "Historian", "nova"),
                audio.audio_key("a", "Local storyteller", "nova"),
                audio.audio_key("a", "Historian", "coral"),
            }
        )
        == 4
    )


@pytest.mark.parametrize("text", ["", "a" * 4001])
def test_long_or_empty_audio_rejected(text):
    with pytest.raises(ValueError):
        audio.synthesize("key", text, "Historian")
