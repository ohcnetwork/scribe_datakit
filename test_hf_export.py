#!/usr/bin/env python3
"""Self-check for hf_export — run: python3 test_hf_export.py"""
import os, tempfile
from hf_export import card, joined, recording_row, segment_row, select_clips, seg_id, write_rows
from segment_audio import blank_segment


def seg(i, **kw):
    return {**blank_segment(i, i * 10.0, i * 10.0 + 10), "generated_transcript": f"auto{i}", **kw}


FIN = {"id": "fin", "collection": "c1", "status": "final", "duration_sec": 20.0,
       "spoken_languages": ["ml", "en"],
       "segments": [seg(0, final_translation="human"), seg(1, excluded=True)]}
PEND = {"id": "pend", "collection": "c2", "status": "pending", "duration_sec": 5.0,
        "segments": [seg(0)]}
FLAG = {"id": "flag", "collection": "c1", "status": "flagged", "duration_sec": 5.0,
        "segments": [seg(0)]}
EMPTY = {"id": "none", "collection": "c1", "status": "pending", "segments": []}


def test_select():
    ids = lambda cs: [c["id"] for c in cs]
    assert ids(select_clips([FIN, PEND, FLAG, EMPTY])) == ["fin", "pend", "flag"]
    assert ids(select_clips([FIN, PEND, FLAG], "reviewed")) == ["fin"]


def test_segment_row_keeps_text_apart():
    r = segment_row(FIN, FIN["segments"][0])
    assert r["file_name"] == "fin_s000.flac" and r["recording_id"] == "fin"
    assert r["final_translation"] == "human" and r["generated_transcript"] == "auto0"
    assert r["final_transcript"] is None          # machine text never fills a human column
    assert seg_id(PEND, PEND["segments"][0]) == "pend_s000"


def test_recording_text_needs_every_usable_segment():
    assert joined(FIN["segments"], "final_translation") == "human"      # excluded one is skipped
    assert joined([seg(0, final_transcript="a"), seg(1)], "final_transcript") is None
    assert recording_row(PEND)["generated_transcript"] == "auto0"


def test_write_rows_removes_strays_and_refuses_gaps():
    with tempfile.TemporaryDirectory() as d:
        for n in ("keep.flac", "stray.flac"):
            open(os.path.join(d, n), "w").close()
        write_rows(d, [{"file_name": "keep.flac"}])
        assert sorted(os.listdir(d)) == ["keep.flac", "metadata.jsonl"]
        try:
            write_rows(d, [{"file_name": "gone.flac"}])
        except SystemExit:
            return
    raise AssertionError("a row without audio was allowed")


def test_card():
    text = card([FIN, PEND], "cc-by-4.0", "org/repo")
    assert "config_name: c1" in text and "path: data/c2/train/*" in text
    assert "- ml" in text and "- en" in text and "translation" in text
    assert "- multilingual" in card([PEND], "cc-by-4.0", "org/repo")    # guesses aren't listed


if __name__ == "__main__":
    for t in (test_select, test_segment_row_keeps_text_apart,
              test_recording_text_needs_every_usable_segment,
              test_write_rows_removes_strays_and_refuses_gaps, test_card):
        t()
    print("ok")
