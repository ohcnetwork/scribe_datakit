#!/usr/bin/env python3
"""Self-check for merge_corrections.apply — run: python3 test_merge_corrections.py"""
from merge_corrections import apply


def test_apply():
    doc = {"clips": [
        {"id": "a", "transcript": "old", "status": "unverified", "duration_sec": 5},
        {"id": "b", "transcript": None, "status": "unverified"},
    ]}
    n = apply(doc, [
        {"id": "a", "transcript": "new", "status": "verified", "category": "medical-scribe"},
        {"id": "b", "status": "flagged"},
        {"id": "ghost", "status": "verified"},          # unknown id → skipped
        {"id": "a", "size_bytes": 999, "corrupt": True},  # non-whitelisted → ignored
    ])
    a, b = doc["clips"]
    assert n == 3, n                                    # ghost skipped
    assert a["transcript"] == "new" and a["status"] == "verified"
    assert a["category"] == "medical-scribe"
    assert a["duration_sec"] == 5 and "size_bytes" not in a  # derived fields untouched
    assert b["status"] == "flagged" and b["transcript"] is None
    print("ok")


if __name__ == "__main__":
    test_apply()
