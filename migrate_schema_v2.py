#!/usr/bin/env python3
"""One-off: migrate metadata.json from schema v1 to v2.

Separates machine output (generated_*) from human text (final_*). In v1 `transcript`
started as a copy of the Whisper output, so it only becomes final_transcript when a
person actually touched it (status=verified, or it differs from the Whisper text).

Writes metadata.v1.json as a backup first; refuses to run twice.

    python migrate_schema_v2.py
    python migrate_schema_v2.py --collection scribe-staging
"""
import argparse, json, os, shutil, sys

HERE = os.path.dirname(__file__)
META = os.path.join(HERE, "metadata.json")
BACKUP = os.path.join(HERE, "metadata.v1.json")
STATUS_MAP = {"unverified": "pending", "verified": "reviewed", "flagged": "flagged"}


def migrate_clip(c, collection):
    auto, cur = c.pop("transcript_auto", None), c.pop("transcript", None)
    old = c.get("status", "unverified")
    if old not in STATUS_MAP:
        raise ValueError(f"{c.get('id')}: unknown status {old!r}")
    if auto is None and old != "verified":
        auto = cur                      # pre-split record: the lone transcript was machine output
    human = old == "verified" or (cur is not None and cur != auto)

    c["whisper_language"] = c.pop("language", None)
    c["spoken_languages"] = None        # null = no human has confirmed the language yet
    c["collection"] = collection
    c["generated_transcript"] = auto
    c["generated_translation"] = None
    c["final_transcript"] = cur if human else None
    c["final_translation"] = None
    status = STATUS_MAP[old]
    c["status"] = "pending" if status == "reviewed" and c["final_transcript"] is None else status
    return c


def migrate(doc, collection):
    if doc.get("schema_version") != 1:
        raise ValueError(f"expected schema_version 1, got {doc.get('schema_version')}")
    for c in doc["clips"]:
        migrate_clip(c, collection)
    doc["schema_version"] = 2
    return doc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--collection", default="scribe-staging", help="collection for existing clips")
    args = ap.parse_args()

    with open(META) as f:
        doc = json.load(f)
    try:
        migrate(doc, args.collection)
    except ValueError as e:
        sys.exit(str(e))
    shutil.copy2(META, BACKUP)
    tmp = META + ".tmp"
    with open(tmp, "w") as f:
        json.dump(doc, f, indent=2)
    os.replace(tmp, META)
    kept = sum(c["final_transcript"] is not None for c in doc["clips"])
    print(f"migrated {len(doc['clips'])} clips ({kept} with human text) → {META}; "
          f"backup: {BACKUP}", file=sys.stderr)


if __name__ == "__main__":
    main()
