#!/usr/bin/env python3
"""Apply corrections/*.json (the app's Export output) onto metadata.json.

Each file is {"corrections": [{"id": ..., "final_transcript": ..., "status": ...}, ...]}.
Only the user-editable fields are applied; every derived and generated field in
metadata.json is left untouched. Contributors submit these files as a PR (the dataset
itself isn't in the repo); the maintainer merges then pushes.

Status rules enforced here, because a PR is the trust boundary:
- `final` needs --allow-final. Pass it only for your own file, never for contributors'.
- reviewed/qa_complete/final need at least one final_* text.
- changing text on a qa_complete/final clip sends it back to reviewed.

    python merge_corrections.py                 # all of corrections/*.json
    python merge_corrections.py path/to/one.json
    python merge_corrections.py --allow-final my-approvals.json
"""
import argparse, glob, json, os, re, sys

HERE = os.path.dirname(__file__)
OUT = os.path.join(HERE, "metadata.json")
TEXT = ("final_transcript", "final_translation")
ALLOWED = {*TEXT, "spoken_languages", "status", "category"}   # whitelist = trust boundary
STATUSES = {"pending", "reviewed", "qa_complete", "final", "flagged"}
NEEDS_TEXT = {"reviewed", "qa_complete", "final"}
LOCKED = {"qa_complete", "final"}


def clean(corr, allow_final):
    """Whitelisted, well-typed fields of one correction; warn about anything dropped."""
    patch = {k: v for k, v in corr.items() if k in ALLOWED}

    def drop(k, why):
        print(f"  {corr['id']}: dropped {k}: {why}", file=sys.stderr)
        del patch[k]

    for k in TEXT:
        if k in patch and not isinstance(patch[k], (str, type(None))):
            drop(k, "not text")
    langs = patch.get("spoken_languages")
    if langs is not None and not (isinstance(langs, list) and langs and all(
            isinstance(l, str) and re.fullmatch("[a-z]{2,3}", l) for l in langs)):
        drop("spoken_languages", "not a list of language codes")
    status = patch.get("status")
    if "status" in patch and status not in STATUSES:
        drop("status", f"unknown value {status!r}")
    elif status == "final" and not allow_final:
        drop("status", "final needs --allow-final")
    return patch


def apply(doc, corrections, allow_final=False):
    """Merge a list of {id, ...patch} onto doc['clips'] in place; return count applied."""
    by_id = {c["id"]: c for c in doc["clips"]}
    applied = 0
    for corr in corrections:
        clip = by_id.get(corr.get("id"))
        if not clip:
            print(f"  skip unknown id {corr.get('id')}", file=sys.stderr)
            continue
        before = clip.get("status")
        old_text = [clip.get(k) for k in TEXT]
        clip.update(clean(corr, allow_final))
        if before in LOCKED and old_text != [clip.get(k) for k in TEXT]:
            clip["status"] = "reviewed"          # changed text needs checking again
        if clip.get("status") in NEEDS_TEXT and all(clip.get(k) is None for k in TEXT):
            print(f"  {clip['id']}: {clip['status']} needs human text, status kept at {before}",
                  file=sys.stderr)
            clip["status"] = before
        applied += 1
    return applied


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*", help="corrections files (default: corrections/*.json)")
    ap.add_argument("--allow-final", action="store_true", help="accept status=final (maintainer only)")
    args = ap.parse_args()
    files = args.files or sorted(glob.glob(os.path.join(HERE, "corrections", "*.json")))
    if not files:
        sys.exit("no corrections files")

    with open(OUT) as f:
        doc = json.load(f)
    if doc.get("schema_version") != 2:
        sys.exit("metadata.json is not schema v2; run migrate_schema_v2.py first")
    total = 0
    for path in files:
        with open(path) as f:
            total += apply(doc, json.load(f).get("corrections", []), args.allow_final)
    with open(OUT, "w") as f:
        json.dump(doc, f, indent=2)
    print(f"applied {total} correction(s) from {len(files)} file(s) → {OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
