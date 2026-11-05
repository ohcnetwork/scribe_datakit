#!/usr/bin/env python3
"""Self-check for hf_export selection + row projection — run: python3 test_hf_export.py"""
from hf_export import select_clips, row

CLIPS = [
    {"id": "fin", "filename": "ok.webm", "duration_sec": 5.0, "status": "final",
     "final_transcript": "corrected", "generated_transcript": "auto",
     "whisper_language": "en", "collection": "c1"},
    {"id": "rev", "filename": "r.webm", "duration_sec": 4.0, "status": "reviewed",
     "final_translation": "english"},
    {"id": "pend", "filename": "u.webm", "duration_sec": 3.0, "status": "pending",
     "generated_transcript": "auto only"},
    {"id": "flag", "filename": "f.webm", "duration_sec": 3.0, "status": "flagged"},
    {"id": "bad", "filename": "b.webm", "duration_sec": 9.0, "status": "final", "corrupt": True},
    {"id": "zero", "filename": "z.webm", "duration_sec": None, "status": "final"},
]


def test_select():
    ids = lambda cs: [c["id"] for c in cs]
    # corrupt and duration-less clips are excluded by default
    assert ids(select_clips(CLIPS)) == ["fin", "rev", "pend", "flag"]
    assert ids(select_clips(CLIPS, min_status="reviewed")) == ["fin", "rev"]
    assert ids(select_clips(CLIPS, min_status="final")) == ["fin"]
    assert ids(select_clips(CLIPS, include_corrupt=True)) == ["fin", "rev", "pend", "flag", "bad"]
    # a corrupt clip still never slips through without a duration
    assert "zero" not in ids(select_clips(CLIPS, include_corrupt=True))


def test_row():
    r = row(CLIPS[0])
    assert r["file_name"] == "fin.flac"         # points at the transcoded file, not the webm
    assert r["final_transcript"] == "corrected" and r["generated_transcript"] == "auto"
    assert r["status"] == "final" and r["collection"] == "c1"
    # machine text must never fill a human column
    assert row(CLIPS[2])["final_transcript"] is None
    assert row(CLIPS[2])["generated_transcript"] == "auto only"
    assert "transcription" not in r


if __name__ == "__main__":
    test_select()
    test_row()
    print("ok")
