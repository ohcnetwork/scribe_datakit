#!/usr/bin/env python3
"""The whole review loop against an in-memory hub: maintainer publishes batches,
reviewers claim and review, the maintainer merges, QA, finalises.

Run: python3 test_review_workflow.py
Same loop against a real repo: test_review_live.py
"""
import http.client, json, os, tempfile, threading
from http.server import ThreadingHTTPServer

from review_admin import apply_submission, batch_payload, finalize, make_batches, merge_all
from review_server import ApiError, Reviewer, make_handler
from segment_audio import blank_segment


class FakeHub:
    """Same surface as review_server.Hub. Shared between reviewers, like the real repo."""
    repo = "org/test"

    def __init__(self):
        self.files, self.prs = {}, {}

    def as_user(self, name):
        view = FakeHubView.__new__(FakeHubView)
        view.shared, view.user = self, name
        return view


class FakeHubView:
    repo = FakeHub.repo

    def username(self):
        return self.user

    def login(self, token):
        if token != "good":
            raise ValueError("bad token")
        self.user = "from-token"

    def list_batches(self):
        return sorted(p[len("review/batches/"):-5] for p in self.shared.files
                      if p.startswith("review/batches/"))

    def list_claims(self):
        return [{"batch": v["batch"], "num": n, "author": v["author"], "status": v["status"]}
                for n, v in sorted(self.shared.prs.items())]

    def open_claim(self, batch):
        num = len(self.shared.prs) + 1
        self.shared.prs[num] = {"batch": batch, "author": self.user, "status": "draft", "files": {}}
        return num

    def release_claim(self, num):
        self.shared.prs[num]["status"] = "closed"

    def read_file(self, path, revision=None):
        if revision:
            return self.shared.prs[int(revision.rsplit("/", 1)[1])]["files"][path]
        return self.shared.files[path]

    def fetch_to(self, path, dst):
        with open(dst, "wb") as f:
            f.write(self.read_file(path))

    def push_submission(self, num, batch, payload):
        self.shared.prs[num]["files"][f"review/submissions/{batch}.json"] = payload

    def publish_claim(self, num):
        assert self.shared.prs[num]["status"] == "draft", "publishing a non-draft fails on the real hub"
        self.shared.prs[num]["status"] = "open"

    def merge_claim(self, num):
        self.shared.prs[num]["status"] = "merged"
        self.shared.files.update(self.shared.prs[num]["files"])


def clip(id, segments=2, **kw):
    return {"id": id, "collection": "c1", "duration_sec": 20.0 * segments, "whisper_language": "hi",
            "spoken_languages": None, "category": "uncategorized", "status": "pending",
            "recorded_at": id, "reviewed_by": None, "qa_by": None,
            "segments": [{**blank_segment(i, i * 20.0, i * 20.0 + 20),
                          "generated_transcript": f"t{i}", "generated_translation": f"e{i}"}
                         for i in range(segments)], **kw}


def publish(hub, doc, **kw):
    made = make_batches(doc["clips"], "c1", **kw)
    for b in made:
        hub.files[f"review/batches/{b['name']}.json"] = json.dumps(batch_payload(b)).encode()
        for c in b["clips"]:
            hub.files[f"recordings/c1/{c['id']}.flac"] = b"audio bytes for " + c["id"].encode()
            hub.files[f"review/peaks/{c['id']}.json"] = b'{"peaks": []}'
    return made


def fails(status, fn):
    try:
        fn()
    except ApiError as e:
        assert e.status == status, (e.status, e.message)
        return True
    raise AssertionError(f"expected {status}")


def review_everything(reviewer, batch):
    for c in reviewer.batch(batch)["clips"]:
        edits = [{"index": s["index"], "final_translation": f"human {s['index']}"} for s in c["segments"]]
        reviewer.edit(batch, c["id"], {"segments": edits})
        reviewer.edit(batch, c["id"], {"done": True})


def test_batches_keep_recordings_whole_and_never_repeat():
    clips = [clip(str(i)) for i in range(5)]           # 40 s each
    first = make_batches(clips, "c1", minutes=1)
    assert [len(b["clips"]) for b in first] == [2, 2, 1]
    assert first[0]["name"] == "c1-review-0001"
    existing = [{"kind": b["kind"], "collection": "c1", "clip_ids": [c["id"] for c in b["clips"]]}
                for b in first]
    clips.append(clip("new"))
    again = make_batches(clips, "c1", minutes=1, existing=existing)
    assert [c["id"] for b in again for c in b["clips"]] == ["new"]
    assert again[0]["name"] == "c1-review-0004"
    clips[0]["status"] = "reviewed"                    # QA can pick up a clip review already had
    assert make_batches(clips, "c1", kind="qa", existing=existing)[0]["clips"][0]["id"] == "0"
    assert not make_batches([clip("s", category="silence")], "c1")
    assert not make_batches([clip("x", collection="other")], "c1")


def test_full_loop():
    with tempfile.TemporaryDirectory() as work:
        hub = FakeHub()
        doc = {"clips": [clip("a"), clip("b")]}
        batch = publish(hub, doc)[0]["name"]
        ann = Reviewer(hub.as_user("ann"), os.path.join(work, "ann"))

        # claim: the batch shows as taken and only its audio comes down
        assert ann.state()["batches"][0]["state"] == "available"
        ann.claim(batch)
        assert hub.prs[1]["status"] == "draft"
        assert ann.state()["batches"][0]["state"] == "mine"
        assert os.path.exists(ann.media(batch, "audio", "a.flac"))

        # someone else can't take it
        bob = Reviewer(hub.as_user("bob"), os.path.join(work, "bob"))
        assert bob.state()["batches"][0] == {"name": batch, "state": "taken", "reviewer": "ann", "local": False}
        assert fails(409, lambda: bob.claim(batch))

        # edit one box: the other stays null, drafts survive a restart
        ann.edit(batch, "a", {"segments": [{"index": 0, "final_translation": "fever"}]})
        again = Reviewer(hub.as_user("ann"), os.path.join(work, "ann"))
        s0, s1 = again.batch(batch)["clips"][0]["segments"]
        assert s0["final_translation"] == "fever" and s0["final_transcript"] is None
        assert s1["final_translation"] is None and s0["generated_translation"] == "e0"
        again.claim(batch)                               # continuing never overwrites work
        assert again.batch(batch)["clips"][0]["segments"][0]["final_translation"] == "fever"

        # a clip can't finish with a segment unreviewed, unless it's excluded or flagged
        assert fails(400, lambda: ann.edit(batch, "a", {"done": True}))
        ann.edit(batch, "a", {"segments": [{"index": 1, "excluded": True}]})
        ann.edit(batch, "a", {"done": True})
        assert fails(400, lambda: ann.submit(batch))      # b is still to do
        ann.edit(batch, "b", {"done": True, "flagged": True})

        # submit: lands on the same PR and is published, main is untouched
        assert ann.submit(batch) == {"submitted": 2, "pr": 1}
        assert hub.prs[1]["status"] == "open"
        assert f"review/submissions/{batch}.json" not in hub.files
        assert ann.state()["batches"][0]["state"] == "submitted"
        ann.submit(batch)                                 # a resubmission doesn't re-publish

        # merge: only listed reviewers count
        admin = hub.as_user("maintainer")
        assert "isn't in reviewers.txt" in merge_all(doc, admin, {"someone-else"})[0]
        assert doc["clips"][0]["status"] == "pending"
        merge_all(doc, admin, {"ann"})
        a, b = doc["clips"]
        assert a["status"] == "reviewed" and a["reviewed_by"] == "ann"
        assert a["segments"][0]["final_translation"] == "fever" and a["segments"][1]["excluded"]
        assert a["segments"][0]["generated_translation"] == "e0"
        assert b["status"] == "flagged"
        assert hub.prs[1]["status"] == "merged"
        assert ann.state()["batches"][0]["state"] == "done"
        assert bob.state()["batches"][0]["state"] == "done"

        # QA reuses the same flow, starting from the reviewed text
        qa_batch = publish(hub, doc, kind="qa")[0]["name"]
        assert qa_batch == "c1-qa-0001"
        bob.claim(qa_batch)
        qa = bob.batch(qa_batch)["clips"]
        assert [c["id"] for c in qa] == ["a"] and qa[0]["segments"][0]["final_translation"] == "fever"
        bob.edit(qa_batch, "a", {"segments": [{"index": 0, "final_translation": "fever, 2 days"}]})
        bob.edit(qa_batch, "a", {"done": True})
        bob.submit(qa_batch)
        merge_all(doc, hub.as_user("maintainer"), {"ann", "bob"})
        assert a["status"] == "qa_complete" and a["qa_by"] == "bob"
        assert a["segments"][0]["final_translation"] == "fever, 2 days"

        # only the maintainer reaches final
        assert finalize(doc["clips"], "c1") == 1 and a["status"] == "final"


def test_two_people_claiming_at_once():
    with tempfile.TemporaryDirectory() as work:
        hub = FakeHub()
        batch = publish(hub, {"clips": [clip("a")]})[0]["name"]
        bob_hub = hub.as_user("bob")
        real_open = bob_hub.open_claim

        def race(b):            # ann's claim lands just before bob's
            hub.prs[1] = {"batch": b, "author": "ann", "status": "draft", "files": {}}
            return real_open(b)

        bob_hub.open_claim = race
        bob = Reviewer(bob_hub, work)
        assert fails(409, lambda: bob.claim(batch))
        assert hub.prs[2]["status"] == "closed" and hub.prs[1]["status"] == "draft"


def test_released_claim_is_available_again():
    with tempfile.TemporaryDirectory() as work:
        hub = FakeHub()
        batch = publish(hub, {"clips": [clip("a")]})[0]["name"]
        Reviewer(hub.as_user("ann"), os.path.join(work, "a")).claim(batch)
        hub.prs[1]["status"] = "closed"                  # maintainer closes an abandoned claim
        bob = Reviewer(hub.as_user("bob"), os.path.join(work, "b"))
        assert bob.state()["batches"][0]["state"] == "available"
        bob.claim(batch)


def test_login():
    with tempfile.TemporaryDirectory() as work:
        hub = FakeHub()
        r = Reviewer(hub.as_user(None), work)
        assert r.state()["user"] is None
        assert fails(401, lambda: r.claim("x"))
        assert fails(400, lambda: r.login("wrong"))
        assert fails(400, lambda: r.login("  "))
        assert r.login("good")["user"] == "from-token"


def test_bad_edits_are_refused():
    with tempfile.TemporaryDirectory() as work:
        hub = FakeHub()
        batch = publish(hub, {"clips": [clip("a")]})[0]["name"]
        r = Reviewer(hub.as_user("ann"), work)
        r.claim(batch)
        assert fails(400, lambda: r.edit(batch, "a", {"spoken_languages": ["malayalam"]}))
        assert fails(400, lambda: r.edit(batch, "a", {"category": "nope"}))
        assert fails(400, lambda: r.edit(batch, "a", {"segments": [{"index": 9}]}))
        assert fails(400, lambda: r.edit(batch, "a", {"segments": [{"index": 0, "final_transcript": 5}]}))
        assert fails(404, lambda: r.edit(batch, "ghost", {}))
        r.edit(batch, "a", {"segments": [{"index": 0, "generated_transcript": "tampered"}]})
        assert r.batch(batch)["clips"][0]["segments"][0]["generated_transcript"] == "t0"
        # whitespace isn't review work
        r.edit(batch, "a", {"segments": [{"index": 0, "final_translation": "   "}, {"index": 1, "excluded": True}]})
        assert fails(400, lambda: r.edit(batch, "a", {"done": True}))


def test_merge_treats_submissions_as_untrusted():
    def fresh(**kw):
        return {"clips": [clip("a", 1, **kw)]}

    text = [{"index": 0, "final_translation": "x"}]
    good = {"id": "a", "status": "reviewed", "segments": text}

    def problems(corr, **kw):
        doc = fresh(**kw)
        n, p = apply_submission(doc, {"corrections": [corr]}, "ann")
        return n, p, doc["clips"][0]

    assert problems(good)[0] == 1
    for bad in ({**good, "status": "final"}, {**good, "status": "pending"},
                {**good, "id": "ghost"}, {**good, "segments": [{"index": 7}]},
                {**good, "segments": "x"}, {**good, "segments": [{"index": 0, "final_translation": 5}]},
                {**good, "spoken_languages": "ml"},
                {"id": "a", "status": "reviewed", "segments": [{"index": 0}]}):
        n, p, c = problems(bad)
        assert n == 0 and p and c["status"] == "pending" and c["segments"][0]["final_translation"] is None, bad
    # QA needs a reviewed clip, and rejection leaves its text alone
    n, p, c = problems({**good, "status": "qa_complete"})
    assert n == 0 and c["status"] == "pending" and c["segments"][0]["final_translation"] is None
    # final clips are locked
    n, p, c = problems(good, status="final")
    assert n == 0 and c["status"] == "final"
    # only whitelisted segment fields apply
    n, p, c = problems({**good, "segments": [{"index": 0, "final_translation": "x", "generated_transcript": "bad", "start": 99}]})
    assert n == 1 and c["segments"][0]["generated_transcript"] == "t0" and c["segments"][0]["start"] == 0


def test_http_layer():
    with tempfile.TemporaryDirectory() as tmp:
        dist = os.path.join(tmp, "dist")
        os.makedirs(dist)
        with open(os.path.join(dist, "index.html"), "w") as f:
            f.write("<html>app</html>")
        with open(os.path.join(tmp, "secret.txt"), "w") as f:
            f.write("secret")
        hub = FakeHub()
        batch = publish(hub, {"clips": [clip("a")]})[0]["name"]
        r = Reviewer(hub.as_user("ann"), os.path.join(tmp, "work"))
        r.claim(batch)
        srv = ThreadingHTTPServer(("127.0.0.1", 0), None)
        port = srv.server_address[1]
        srv.RequestHandlerClass = make_handler(r, dist, port)
        threading.Thread(target=srv.serve_forever, daemon=True).start()

        def call(method, path, body=None, **headers):
            c = http.client.HTTPConnection("127.0.0.1", port)
            hdrs = {"Host": f"127.0.0.1:{port}", **headers}
            if body is not None:
                hdrs.setdefault("Content-Type", "application/json")
            c.request(method, path, json.dumps(body) if body is not None else None, hdrs)
            res = c.getresponse()
            return res.status, res.read(), res

        try:
            assert call("GET", "/api/state")[0] == 200
            assert call("GET", "/")[1] == b"<html>app</html>"
            assert call("GET", "/batch/x/clip/y")[1] == b"<html>app</html>"     # client routes
            # another website must not reach this server
            assert call("GET", "/api/state", Host="evil.example")[0] == 403
            assert call("POST", f"/api/batches/{batch}/submit", {}, Origin="https://evil.example")[0] == 403
            assert call("POST", f"/api/batches/{batch}/submit", {}, **{"Content-Type": "text/plain"})[0] == 415
            # files outside the app stay out of reach
            assert b"secret" not in call("GET", "/../secret.txt")[1]
            assert call("GET", f"/media/{batch}/audio/..")[0] == 404
            assert call("GET", "/media/../audio/a.flac")[0] in (400, 404)
            # seeking needs ranges
            url = f"/media/{batch}/audio/a.flac"
            whole = call("GET", url)[1]
            status, part, res = call("GET", url, Range="bytes=2-5")
            assert status == 206 and part == whole[2:6]
            assert res.getheader("Content-Range") == f"bytes 2-5/{len(whole)}"
            assert call("GET", url, Range="bytes=99999-")[0] == 416
            # a POST whose route ignores the body must not poison the kept-alive socket
            c = http.client.HTTPConnection("127.0.0.1", port)
            hdrs = {"Host": f"127.0.0.1:{port}", "Content-Type": "application/json"}
            c.request("POST", f"/api/batches/{batch}/claim", "{}", hdrs)
            assert c.getresponse().read() and True
            c.request("GET", f"/api/batches/{batch}", headers=hdrs)
            assert c.getresponse().status == 200
            # edits go through
            status, body, _ = call("PATCH", f"/api/batches/{batch}/clips/a",
                                   {"segments": [{"index": 0, "final_translation": "ok"}]})
            assert status == 200 and json.loads(body)["segments"][0]["final_translation"] == "ok"
            assert call("PATCH", f"/api/batches/{batch}/clips/a", {"category": "x"})[0] == 400
        finally:
            srv.shutdown()


if __name__ == "__main__":
    for name, t in list(globals().items()):
        if name.startswith("test_"):
            t()
            print("  ok", name)
    print("ok")
