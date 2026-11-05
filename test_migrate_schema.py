#!/usr/bin/env python3
"""Self-check for migrate_schema_v2 — run: python3 test_migrate_schema.py"""
from migrate_schema_v2 import migrate


def v1(id, **kw):
    return {"id": id, "language": "hi", "transcript": "auto", "transcript_auto": "auto",
            "confidence": 0.5, "no_speech_prob": 0.1, "status": "unverified", **kw}


def refused(doc):
    try:
        migrate(doc, "c1")
    except ValueError:
        return True
    return False


def test_migrate():
    doc = migrate({"schema_version": 1, "clips": [v1("a")]}, "c1")
    c = doc["clips"][0]
    assert doc["schema_version"] == 2
    assert c["segments"] == [] and c["status"] == "pending" and c["collection"] == "c1"
    assert c["whisper_language"] == "hi" and c["spoken_languages"] is None
    assert not {"transcript", "transcript_auto", "language", "confidence"} & c.keys()


def test_refusals():
    assert refused({"schema_version": 2, "clips": []})                       # second run
    assert refused({"schema_version": 1, "clips": [v1("a", transcript="fixed")]})
    assert refused({"schema_version": 1, "clips": [v1("a", status="verified")]})


if __name__ == "__main__":
    test_migrate()
    test_refusals()
    print("ok")
