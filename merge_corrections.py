#!/usr/bin/env python3
"""Apply corrections/*.json (the app's Export output) onto metadata.json.

Each file is {"corrections": [{"id": ..., "transcript": ..., "status": ...,
"category": ...}, ...]}. Only the user-editable fields are applied; every derived
field in metadata.json is left untouched. Contributors submit these files as a PR
(the dataset itself isn't in the repo); the maintainer merges then pushes.

    python merge_corrections.py                 # all of corrections/*.json
    python merge_corrections.py path/to/one.json
"""
import argparse, glob, json, os, sys

HERE = os.path.dirname(__file__)
OUT = os.path.join(HERE, "metadata.json")
ALLOWED = {"transcript", "status", "category"}   # whitelist = trust boundary


def apply(doc, corrections):
    """Merge a list of {id, ...patch} onto doc['clips'] in place; return count applied."""
    by_id = {c["id"]: c for c in doc["clips"]}
    applied = 0
    for corr in corrections:
        clip = by_id.get(corr.get("id"))
        if not clip:
            print(f"  skip unknown id {corr.get('id')}", file=sys.stderr)
            continue
        clip.update({k: v for k, v in corr.items() if k in ALLOWED})
        applied += 1
    return applied


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*", help="corrections files (default: corrections/*.json)")
    args = ap.parse_args()
    files = args.files or sorted(glob.glob(os.path.join(HERE, "corrections", "*.json")))
    if not files:
        sys.exit("no corrections files")

    with open(OUT) as f:
        doc = json.load(f)
    total = 0
    for path in files:
        with open(path) as f:
            total += apply(doc, json.load(f).get("corrections", []))
    with open(OUT, "w") as f:
        json.dump(doc, f, indent=2)
    print(f"applied {total} correction(s) from {len(files)} file(s) → {OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
