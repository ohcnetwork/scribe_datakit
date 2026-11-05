#!/usr/bin/env python3
"""Self-check for the translate-pass selection — run: python3 test_transcribe.py"""
from transcribe import needs_translation, source_language


def clip(**kw):
    return {"generated_transcript": "text", "generated_translation": None,
            "whisper_language": "hi", "spoken_languages": None, **kw}


def test_needs_translation():
    assert needs_translation(clip())
    assert not needs_translation(clip(whisper_language="en"))
    assert not needs_translation(clip(spoken_languages=["en"]))
    assert not needs_translation(clip(generated_translation=""))    # done, even if empty
    assert not needs_translation(clip(generated_transcript=""))     # silent clip
    assert not needs_translation(clip(generated_transcript=None))   # not transcribed yet
    # a human correction beats Whisper's guess, both ways
    assert needs_translation(clip(whisper_language="en", spoken_languages=["ml"]))
    assert not needs_translation(clip(whisper_language="ml", spoken_languages=["en"]))
    assert needs_translation(clip(spoken_languages=["en", "ml"]))   # code-mixed is not English-only


def test_source_language():
    assert source_language(clip()) == "hi"
    assert source_language(clip(spoken_languages=["en", "ml"])) == "ml"


if __name__ == "__main__":
    test_needs_translation()
    test_source_language()
    print("ok")
