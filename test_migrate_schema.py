#!/usr/bin/env python3
"""Self-check for migrate_schema_v2 — run: python3 test_migrate_schema.py"""
from migrate_schema_v2 import migrate


def clip(id, **kw):
    return {"id": id, "language": "hi", **kw}


def test_migrate():
    doc = {"schema_version": 1, "clips": [
        clip("copy", transcript="auto", transcript_auto="auto", status="unverified"),
        clip("edited", transcript="fixed", transcript_auto="auto", status="unverified"),
        clip("accepted", transcript="auto", transcript_auto="auto", status="verified"),
        clip("flagged", transcript="auto", transcript_auto="auto", status="flagged"),
        clip("presplit", transcript="old", transcript_auto=None, status="unverified"),
        clip("empty", transcript=None, transcript_auto=None, status="verified"),
    ]}
    copy, edited, accepted, flagged, presplit, empty = migrate(doc, "c1")["clips"]
    assert doc["schema_version"] == 2
    # an untouched Whisper copy must never count as human text
    assert copy["final_transcript"] is None and copy["status"] == "pending"
    assert copy["generated_transcript"] == "auto"
    # human work survives, whether edited or accepted unchanged
    assert edited["final_transcript"] == "fixed" and edited["generated_transcript"] == "auto"
    assert accepted["final_transcript"] == "auto" and accepted["status"] == "reviewed"
    assert flagged["final_transcript"] is None and flagged["status"] == "flagged"
    assert presplit["generated_transcript"] == "old" and presplit["final_transcript"] is None
    assert empty["status"] == "pending"          # `reviewed` needs human text
    assert copy["whisper_language"] == "hi" and copy["collection"] == "c1"
    assert not {"transcript", "transcript_auto", "language"} & copy.keys()


def test_refuses_second_run():
    try:
        migrate({"schema_version": 2, "clips": []}, "c1")
    except ValueError:
        return
    raise AssertionError("second run was allowed")


if __name__ == "__main__":
    test_migrate()
    test_refuses_second_run()
    print("ok")
