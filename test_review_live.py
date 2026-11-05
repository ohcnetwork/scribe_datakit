#!/usr/bin/env python3
"""The review loop against a real Hugging Face dataset repo, with synthetic files.

Skipped unless you name a throwaway repo you own:

    SCRIBE_LIVE_REPO=gigincg/test_repo python3 test_review_live.py
"""
import json, os, sys, tempfile, time

REPO = os.environ.get("SCRIBE_LIVE_REPO")


def main():
    if not REPO:
        print("skipped: set SCRIBE_LIVE_REPO to a throwaway repo")
        return
    from huggingface_hub import CommitOperationAdd
    from review_admin import batch_payload, merge_all, make_batches
    from review_server import Hub, Reviewer
    from test_review_workflow import clip, review_everything

    hub = Hub(REPO)
    user = hub.username()
    doc = {"clips": [clip(f"live{int(time.time())}")]}
    batch = make_batches(doc["clips"], "c1")[0]
    batch["name"] = f"live-{int(time.time())}"
    cid = doc["clips"][0]["id"]
    hub.api.create_commit(commit_message="test: seed synthetic batch", **hub.kw, operations=[
        CommitOperationAdd(f"review/batches/{batch['name']}.json", json.dumps(batch_payload(batch)).encode()),
        CommitOperationAdd(f"recordings/c1/{cid}.flac", b"not real audio"),
        CommitOperationAdd(f"review/peaks/{cid}.json", b'{"peaks": []}')])
    with tempfile.TemporaryDirectory() as work:
        r = Reviewer(hub, work)
        row = next(b for b in r.state()["batches"] if b["name"] == batch["name"])
        assert row["state"] == "available", row
        r.claim(batch["name"])
        assert next(b for b in r.state()["batches"] if b["name"] == batch["name"])["state"] == "mine"
        review_everything(r, batch["name"])
        result = r.submit(batch["name"])
        r.submit(batch["name"])                       # resubmitting must work too
        assert next(c for c in hub.list_claims() if c["num"] == result["pr"])["status"] == "open"
        report = merge_all(doc, hub, {user})
        print("\n".join(report))
    c = doc["clips"][0]
    assert c["status"] == "reviewed" and c["reviewed_by"] == user, c["status"]
    assert c["segments"][0]["final_translation"] == "human 0"
    assert next(x for x in hub.list_claims() if x["num"] == result["pr"])["status"] == "merged"
    print("ok")


if __name__ == "__main__":
    sys.exit(main())
