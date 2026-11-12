#!/usr/bin/env python3
"""Maintainer side of the review workflow. metadata.json stays the source of truth.

    python3 review_admin.py batches --collection scribe-staging --minutes 30
    python3 review_admin.py batches --collection scribe-staging --kind qa
    python3 review_admin.py merge                # apply submitted PRs, needs reviewers.txt
    python3 review_admin.py finalize --collection scribe-staging

`batches` writes review/ files into hf/, ready to upload with the rest of the export.

Status rules live here because a PR is the trust boundary: only listed reviewers count,
only whitelisted fields apply, and `final` can't arrive through a PR at all.
"""
import argparse, json, os

from review_server import CATEGORIES, LANG, TEXT

HERE = os.path.dirname(os.path.abspath(__file__))
META = os.path.join(HERE, "metadata.json")
HF_DIR = os.path.join(HERE, "hf")
REVIEWERS = os.path.join(HERE, "reviewers.txt")
SUBMITTED = {"reviewed", "qa_complete", "flagged"}
SOURCE = {"review": "pending", "qa": "reviewed"}     # which clips each batch kind picks up


def make_batches(clips, collection, kind="review", minutes=30, existing=()):
    """Chunk clips needing this stage into batches of about `minutes` of audio. Recordings
    stay whole, and a clip already in an existing batch is not handed out twice."""
    taken = {i for b in existing if b["kind"] == kind for i in b["clip_ids"]}
    todo = [c for c in clips if c["collection"] == collection and c["segments"]
            and c["status"] == SOURCE[kind] and c["id"] not in taken
            and c["category"] != "silence"]
    n = sum(b["kind"] == kind and b["collection"] == collection for b in existing)
    batches, cur, total = [], [], 0.0
    for c in sorted(todo, key=lambda c: c.get("recorded_at") or ""):
        cur.append(c)
        total += c["duration_sec"]
        if total >= minutes * 60:
            batches.append(cur)
            cur, total = [], 0.0
    if cur:
        batches.append(cur)
    return [{"name": f"{collection}-{kind}-{n + i + 1:04d}", "kind": kind, "collection": collection,
             "clips": chunk} for i, chunk in enumerate(batches)]


def clean_segments(clip, edits):
    """Whitelisted text per segment; returns {index: patch} or None if the shape is wrong."""
    known = {s["index"] for s in clip["segments"]}
    out = {}
    for e in edits if isinstance(edits, list) else [None]:
        if not isinstance(e, dict) or e.get("index") not in known:
            return None
        patch = {"excluded": bool(e.get("excluded"))}
        for k in TEXT:
            v = e.get(k)
            if not isinstance(v, (str, type(None))):
                return None
            patch[k] = v
        out[e["index"]] = patch
    return out


def complete(clip):
    return all(s["excluded"] or s["final_transcript"] or s["final_translation"]
               for s in clip["segments"])


def apply_submission(doc, submission, reviewer):
    """Merge one reviewer's submission. Returns (applied, problems)."""
    by_id = {c["id"]: c for c in doc["clips"]}
    applied, problems = 0, []
    for corr in submission.get("corrections", []):
        clip = by_id.get(corr.get("id"))
        status = corr.get("status")
        if not clip:
            problems.append(f"unknown clip {corr.get('id')}")
            continue
        if status not in SUBMITTED:
            problems.append(f"{clip['id']}: status {status!r} not allowed")
            continue
        if clip["status"] == "final":
            problems.append(f"{clip['id']}: already final")
            continue
        if status == "qa_complete" and clip["status"] != "reviewed":
            problems.append(f"{clip['id']}: QA on a clip that wasn't reviewed")
            continue
        patches = clean_segments(clip, corr.get("segments"))
        if patches is None:
            problems.append(f"{clip['id']}: bad segments")
            continue
        langs = corr.get("spoken_languages")
        if langs is not None and not (isinstance(langs, list) and langs and all(
                isinstance(l, str) and LANG.match(l) for l in langs)):
            problems.append(f"{clip['id']}: bad spoken_languages")
            continue
        merged = [{**s, **patches.get(s["index"], {})} for s in clip["segments"]]
        if status != "flagged" and not complete({"segments": merged}):
            problems.append(f"{clip['id']}: {status} is missing human text")
            continue
        clip["segments"] = merged
        clip["spoken_languages"] = langs
        if corr.get("category") in CATEGORIES:
            clip["category"] = corr["category"]
        clip["status"] = status
        if status == "reviewed":
            clip["reviewed_by"] = reviewer
        elif status == "qa_complete":
            clip["qa_by"] = reviewer
        applied += 1
    return applied, problems


def finalize(clips, collection, include_reviewed=False):
    """Approve clips for training. Returns the count."""
    ok = {"qa_complete", "reviewed"} if include_reviewed else {"qa_complete"}
    n = 0
    for c in clips:
        if c["collection"] == collection and c["status"] in ok:
            c["status"] = "final"
            n += 1
    return n


def merge_all(doc, hub, reviewers):
    """Apply every published claim PR from a listed reviewer. Returns a list of report lines."""
    report = []
    for claim in hub.list_claims():
        if claim["status"] != "open":
            continue
        who, num, batch = claim["author"], claim["num"], claim["batch"]
        if who not in reviewers:
            report.append(f"PR {num} ({batch}): skipped, {who} isn't in reviewers.txt")
            continue
        try:
            submission = json.loads(hub.read_file(f"review/submissions/{batch}.json",
                                                  revision=f"refs/pr/{num}"))
        except Exception as e:
            report.append(f"PR {num} ({batch}): can't read submission: {e}")
            continue
        applied, problems = apply_submission(doc, submission, who)
        report.extend(f"PR {num} ({batch}): {p}" for p in problems)
        report.append(f"PR {num} ({batch}): applied {applied} from {who}")
        if not problems:
            hub.merge_claim(num)
    return report


def save(doc):
    tmp = META + ".tmp"
    with open(tmp, "w") as f:
        json.dump(doc, f, indent=2)
    os.replace(tmp, META)


def batch_payload(batch):
    keep = ("id", "collection", "duration_sec", "whisper_language", "spoken_languages",
            "category", "status", "segments")
    return {"name": batch["name"], "kind": batch["kind"], "collection": batch["collection"],
            "clips": [{k: c.get(k) for k in keep} for c in batch["clips"]]}


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("batches")
    b.add_argument("--collection", required=True)
    b.add_argument("--kind", choices=SOURCE, default="review")
    b.add_argument("--minutes", type=int, default=30)
    sub.add_parser("merge")
    f = sub.add_parser("finalize")
    f.add_argument("--collection", required=True)
    f.add_argument("--include-reviewed", action="store_true", help="skip QA for reviewed clips")
    args = ap.parse_args()

    with open(META) as fh:
        doc = json.load(fh)
    if args.cmd == "batches":
        out = os.path.join(HF_DIR, "review", "batches")
        os.makedirs(out, exist_ok=True)
        existing = []
        for name in os.listdir(out):
            with open(os.path.join(out, name)) as fh:
                d = json.load(fh)
            existing.append({**d, "clip_ids": [c["id"] for c in d["clips"]]})
        made = make_batches(doc["clips"], args.collection, args.kind, args.minutes, existing)
        for batch in made:
            with open(os.path.join(out, batch["name"] + ".json"), "w") as fh:
                json.dump(batch_payload(batch), fh, ensure_ascii=False, indent=1)
        print(f"wrote {len(made)} batch(es) to {out}; upload with: make hf-export, then the push command it prints")
    elif args.cmd == "merge":
        from review_server import Hub
        with open(REVIEWERS) as fh:
            reviewers = {l.strip() for l in fh if l.strip() and not l.startswith("#")}
        hub = Hub()
        print("\n".join(merge_all(doc, hub, reviewers)) or "no open submissions")
        save(doc)
    else:
        print(f"{finalize(doc['clips'], args.collection, args.include_reviewed)} clip(s) now final")
        save(doc)


if __name__ == "__main__":
    main()
