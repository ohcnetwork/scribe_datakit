#!/usr/bin/env python3
"""Self-check for hf_export selection + row projection — run: python3 test_hf_export.py"""
from hf_export import select_clips, row

CLIPS = [
    {"id": "ok", "filename": "ok.webm", "duration_sec": 5.0, "status": "verified",
     "transcript": "corrected", "transcript_auto": "auto", "language": "en"},
    {"id": "unver", "filename": "u.webm", "duration_sec": 3.0, "status": "unverified",
     "transcript": None, "transcript_auto": "auto only"},
    {"id": "bad", "filename": "b.webm", "duration_sec": 9.0, "status": "verified",
     "corrupt": True},
    {"id": "zero", "filename": "z.webm", "duration_sec": None, "status": "verified"},
]


def test_select():
    ids = lambda cs: [c["id"] for c in cs]
    # corrupt and duration-less clips are excluded by default
    assert ids(select_clips(CLIPS)) == ["ok", "unver"]
    assert ids(select_clips(CLIPS, verified_only=True)) == ["ok"]
    assert ids(select_clips(CLIPS, include_corrupt=True)) == ["ok", "unver", "bad"]
    # a corrupt clip still never slips through without a duration
    assert "zero" not in ids(select_clips(CLIPS, include_corrupt=True))


def test_row():
    r = row(CLIPS[0])
    assert r["file_name"] == "ok.flac"          # points at the transcoded file, not the webm
    assert r["transcription"] == "corrected"    # human edit wins over the auto transcript
    assert r["status"] == "verified" and r["language"] == "en"
    # falls back to the model output, and never emits null text
    assert row(CLIPS[1])["transcription"] == "auto only"
    assert row(CLIPS[3])["transcription"] == ""


if __name__ == "__main__":
    test_select()
    test_row()
    print("ok")
