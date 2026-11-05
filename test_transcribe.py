#!/usr/bin/env python3
"""Self-check for the Whisper pass — run: python3 test_transcribe.py"""
import transcribe as t
from segment_audio import blank_segment


def seg(i=0, end=10.0, **kw):
    return {**blank_segment(i, 0.0, end), **kw}


def test_needs_translation():
    c = {"spoken_languages": None}
    assert t.needs_translation(c, seg(generated_transcript="text"))
    assert t.needs_translation({**c, "whisper_language": "en"}, seg(generated_transcript="text"))
    assert t.needs_translation({"spoken_languages": ["ml", "en"]}, seg(generated_transcript="text"))
    assert not t.needs_translation({"spoken_languages": ["en"]}, seg(generated_transcript="text"))
    assert not t.needs_translation(c, seg(generated_transcript=""))              # no speech
    assert not t.needs_translation(c, seg(generated_transcript="t", generated_translation=""))


def test_source_language():
    assert t.source_language({"spoken_languages": None}) is None
    assert t.source_language({"spoken_languages": ["en", "ml"]}) == "ml"


def test_process_runs_both_tasks_and_resumes():
    calls = []

    def fake(chunk, task, language):
        calls.append((task, language, len(chunk)))
        return {"text": f" {task} ", "language": language or "hi",
                "segments": [{"avg_logprob": 0.0, "no_speech_prob": 0.1}]}

    t.load_audio = lambda _id: [0.0] * (t.SR * 20)
    c = {"id": "x", "spoken_languages": None, "category": "uncategorized",
         "segments": [seg(0, 10.0), {**seg(1, 20.0), "start": 10.0}]}
    t.process(c, fake)
    assert [x[0] for x in calls] == ["transcribe", "translate"] * 2
    assert calls[1][1] == "hi"                 # translate reuses the detected language
    assert calls[0][2] == t.SR * 10            # Whisper only hears its own segment
    s = c["segments"][0]
    assert s["generated_transcript"] == "transcribe" and s["generated_translation"] == "translate"
    assert s["final_transcript"] is None and s["confidence"] == 1.0
    assert c["whisper_language"] == "hi" and c["model"] == t.MODEL_NAME
    calls.clear()
    t.process(c, fake)
    assert not calls                            # finished segments are skipped


def test_silence_tagging():
    assert t.is_silent([seg(generated_transcript="", no_speech_prob=0.9)])
    assert not t.is_silent([seg(generated_transcript="hi", no_speech_prob=0.9)])


if __name__ == "__main__":
    test_needs_translation()
    test_source_language()
    test_process_runs_both_tasks_and_resumes()
    test_silence_tagging()
    print("ok")
