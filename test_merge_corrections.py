#!/usr/bin/env python3
"""Self-check for merge_corrections.apply — run: python3 test_merge_corrections.py"""
from merge_corrections import apply


def clip(id, **kw):
    return {"id": id, "status": "pending", "final_transcript": None,
            "final_translation": None, "generated_transcript": "auto", **kw}


def test_apply():
    doc = {"clips": [clip("a", duration_sec=5), clip("b")]}
    n = apply(doc, [
        {"id": "a", "final_translation": "new", "status": "reviewed", "category": "medical-scribe",
         "spoken_languages": ["ml", "en"]},
        {"id": "b", "status": "flagged"},
        {"id": "ghost", "status": "reviewed"},           # unknown id → skipped
        {"id": "a", "size_bytes": 999, "corrupt": True,  # non-whitelisted → ignored
         "generated_transcript": "tampered", "collection": "other"},
    ])
    a, b = doc["clips"]
    assert n == 3, n                                     # ghost skipped
    assert a["final_translation"] == "new" and a["status"] == "reviewed"
    assert a["category"] == "medical-scribe" and a["spoken_languages"] == ["ml", "en"]
    assert a["duration_sec"] == 5 and "size_bytes" not in a and "collection" not in a
    assert a["generated_transcript"] == "auto"           # machine text is immutable
    assert b["status"] == "flagged" and b["final_transcript"] is None


def test_status_rules():
    text = {"final_translation": "t"}
    doc = {"clips": [clip("a", **text, status="qa_complete"), clip("b", **text, status="final"),
                     clip("c"), clip("d", **text, status="reviewed"), clip("e", **text)]}
    apply(doc, [
        {"id": "a", "status": "final"},                  # contributor can't approve
        {"id": "b", "final_translation": "changed"},     # edit reopens a final clip
        {"id": "c", "status": "reviewed"},               # no human text → refused
        {"id": "d", "status": "nonsense", "spoken_languages": "ml"},
        {"id": "e", "final_transcript": 5},
    ])
    a, b, c, d, e = doc["clips"]
    assert a["status"] == "qa_complete"
    assert b["status"] == "reviewed" and b["final_translation"] == "changed"
    assert c["status"] == "pending"
    assert d["status"] == "reviewed" and "spoken_languages" not in d
    assert e["final_transcript"] is None

    apply(doc, [{"id": "a", "status": "final"}], allow_final=True)
    assert a["status"] == "final"


if __name__ == "__main__":
    test_apply()
    test_status_rules()
    print("ok")
