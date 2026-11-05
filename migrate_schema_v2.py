#!/usr/bin/env python3
"""One-off: migrate metadata.json from schema v1 to v2.

v2 keeps each recording whole and hangs its text on `segments` (see segment_audio.py).
Whisper text is regenerated per segment, so v1's transcripts are not carried over;
they stay in the metadata.v1.json backup. Refuses to run if any v1 clip holds human
work, because that text has no segment to go to.

    python migrate_schema_v2.py
    python migrate_schema_v2.py --collection scribe-staging
"""
import argparse, json, os, shutil, sys

HERE = os.path.dirname(__file__)
META = os.path.join(HERE, "metadata.json")
BACKUP = os.path.join(HERE, "metadata.v1.json")
DROP = ("transcript", "transcript_auto", "confidence", "no_speech_prob")


def migrate(doc, collection):
    if doc.get("schema_version") != 1:
        raise ValueError(f"expected schema_version 1, got {doc.get('schema_version')}")
    human = [c["id"] for c in doc["clips"] if c.get("status", "unverified") != "unverified"
             or c.get("transcript") != c.get("transcript_auto")]
    if human:
        raise ValueError(f"{len(human)} clip(s) hold human work, e.g. {human[0]}")
    for c in doc["clips"]:
        for k in DROP:
            c.pop(k, None)
        c["whisper_language"] = c.pop("language", None)
        c["spoken_languages"] = None     # null = no human has confirmed the language yet
        c["collection"] = collection
        c["segments"] = []
        c["status"] = "pending"
        c["reviewed_by"] = c["qa_by"] = None
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
    print(f"migrated {len(doc['clips'])} clips → {META}; backup: {BACKUP}", file=sys.stderr)


if __name__ == "__main__":
    main()
