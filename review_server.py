#!/usr/bin/env python3
"""Local review app: serves the React UI on 127.0.0.1 and talks to Hugging Face.

Nothing is deployed. Each reviewer runs this on their own machine with their own HF
login. A batch is a chunk of recordings published in the dataset repo:

    claim  → opens a draft PR on the repo (so everyone can see it's taken), downloads
             only that batch's audio
    review → drafts are saved to review_work/ on disk after every edit
    submit → pushes the reviews to the same PR and publishes it for the maintainer

The hub is the only shared state; review_admin.py merges what comes back.

    python3 review_server.py            # or: make review
"""
import argparse, json, mimetypes, os, re, sys, threading, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(HERE, "app", "dist")
WORK = os.path.join(HERE, "review_work")
REPO = os.environ.get("HF_REPO", "ohcnetwork/scribe_dataset")
PORT = 4321
ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")   # no "..", no slashes
LANG = re.compile(r"^[a-z]{2,3}$")
TEXT = ("final_transcript", "final_translation")
DONE = {"review": "reviewed", "qa": "qa_complete"}     # what finishing a clip means, by batch kind
CATEGORIES = {"uncategorized", "medical-scribe", "random", "noisy-background", "music",
              "silence", "test"}


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status, self.message = status, message


def claim_title(batch):
    return f"[claim] {batch}"


def batch_of(title):
    m = re.fullmatch(r"\[claim\] (.+)", title or "")
    return m.group(1) if m else None


def clip_complete(clip):
    """Every usable segment has human text."""
    return all(s.get("excluded") or any((s.get(k) or "").strip() for k in TEXT)
               for s in clip["segments"])


def apply_edit(clip, patch):
    """Validate one edit from the UI and merge it into a draft clip. Returns the clip."""
    if "spoken_languages" in patch:
        langs = patch["spoken_languages"]
        if langs is not None and not (isinstance(langs, list) and langs
                                      and all(isinstance(l, str) and LANG.match(l) for l in langs)):
            raise ApiError(400, "Use language codes such as ml or en.")
        clip["spoken_languages"] = langs
    if "category" in patch:
        if patch["category"] not in CATEGORIES:
            raise ApiError(400, "Unknown category.")
        clip["category"] = patch["category"]
    by_index = {s["index"]: s for s in clip["segments"]}
    for edit in patch.get("segments", []):
        seg = by_index.get(edit.get("index"))
        if seg is None:
            raise ApiError(400, "Unknown segment.")
        for k in TEXT:
            if k in edit:
                if not isinstance(edit[k], (str, type(None))):
                    raise ApiError(400, "Text must be a string.")
                seg[k] = edit[k]
        if "excluded" in edit:
            seg["excluded"] = bool(edit["excluded"])
    return clip


class Hub:
    """The few Hugging Face calls this workflow needs; tests swap in a fake."""

    def __init__(self, repo=REPO):
        from huggingface_hub import HfApi
        self.api, self.repo, self.user = HfApi(), repo, None
        self.kw = dict(repo_id=repo, repo_type="dataset")

    def username(self):
        if not self.user:          # whoami is rate limited, so ask once
            try:
                self.user = self.api.whoami()["name"]
            except Exception:
                return None
        return self.user

    def login(self, token):
        from huggingface_hub import login
        login(token=token, add_to_git_credential=False)
        self.user = None

    def list_batches(self):
        files = self.api.list_repo_files(**self.kw)
        return sorted(os.path.basename(f)[:-5] for f in files
                      if f.startswith("review/batches/") and f.endswith(".json"))

    def list_claims(self):
        """Claim PRs, oldest first: {batch, num, author, status}."""
        out = []
        for d in self.api.get_repo_discussions(discussion_type="pull_request", **self.kw):
            batch = batch_of(d.title)
            if batch:
                out.append({"batch": batch, "num": d.num, "author": d.author, "status": d.status})
        return sorted(out, key=lambda c: c["num"])

    def open_claim(self, batch):
        return self.api.create_pull_request(title=claim_title(batch), **self.kw,
                                            description=f"Review claim for {batch}.").num

    def release_claim(self, num):
        self.api.change_discussion_status(discussion_num=num, new_status="closed", **self.kw)

    def read_file(self, path, revision=None):
        from huggingface_hub import hf_hub_download
        return open(hf_hub_download(filename=path, revision=revision, **self.kw), "rb").read()

    def fetch_to(self, path, dst):
        with open(dst, "wb") as f:
            f.write(self.read_file(path))

    def push_submission(self, num, batch, payload):
        from huggingface_hub import CommitOperationAdd
        self.api.create_commit(revision=f"refs/pr/{num}", commit_message=f"Submit {batch}",
                               operations=[CommitOperationAdd(
                                   f"review/submissions/{batch}.json", payload)], **self.kw)

    def publish_claim(self, num):
        self.api.change_discussion_status(discussion_num=num, new_status="open", **self.kw)

    def merge_claim(self, num):
        self.api.merge_pull_request(discussion_num=num, **self.kw)


class Reviewer:
    """Everything the UI can do. No HTTP in here, so tests can read like the workflow."""

    def __init__(self, hub, work=WORK):
        self.hub, self.work = hub, work
        self.lock = threading.Lock()
        os.makedirs(work, exist_ok=True)

    def _dir(self, batch):
        if not ID.match(batch):
            raise ApiError(400, "Bad batch name.")
        return os.path.join(self.work, batch)

    def _load(self, batch):
        path = os.path.join(self._dir(batch), "draft.json")
        if not os.path.exists(path):
            raise ApiError(404, "This batch isn't on this computer. Claim it first.")
        with open(path) as f:
            return json.load(f)

    def _save(self, batch, doc):
        path = os.path.join(self._dir(batch), "draft.json")
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(doc, f, indent=1, ensure_ascii=False)
        os.replace(tmp, path)     # atomic: a crash mid-save must not lose the draft

    def state(self):
        user = self.hub.username()
        if not user:
            return {"user": None, "repo": self.hub.repo, "batches": []}
        claims = {}
        for c in self.hub.list_claims():         # oldest live claim on a batch wins
            if c["status"] != "closed":
                claims.setdefault(c["batch"], c)
        rows = []
        for name in self.hub.list_batches():
            c = claims.get(name)
            state = "available" if not c else "done" if c["status"] == "merged" \
                else "taken" if c["author"] != user \
                else "submitted" if c["status"] == "open" else "mine"
            rows.append({"name": name, "state": state, "reviewer": c["author"] if c else None,
                         "local": os.path.exists(os.path.join(self._dir(name), "draft.json"))})
        return {"user": user, "repo": self.hub.repo, "batches": rows}

    def login(self, token):
        if not isinstance(token, str) or not token.strip():
            raise ApiError(400, "Paste your Hugging Face token.")
        try:
            self.hub.login(token.strip())
        except Exception:
            raise ApiError(400, "Hugging Face didn't accept that token.")
        return self.state()

    def claim(self, batch):
        user = self.hub.username()
        if not user:
            raise ApiError(401, "Log in to Hugging Face first.")
        if batch not in self.hub.list_batches():
            raise ApiError(404, "That batch doesn't exist.")
        live = [c for c in self.hub.list_claims() if c["batch"] == batch and c["status"] != "closed"]
        mine = next((c for c in live if c["author"] == user), None)
        if live and live[0] is not mine:
            raise ApiError(409, f"{live[0]['author']} already claimed this batch.")
        num = mine["num"] if mine else self.hub.open_claim(batch)
        if not mine:      # two people can claim at once: the lowest PR number wins
            live = [c for c in self.hub.list_claims()
                    if c["batch"] == batch and c["status"] != "closed"]
            if live[0]["num"] != num:
                self.hub.release_claim(num)
                raise ApiError(409, f"{live[0]['author']} claimed this batch first.")
        self._download(batch, num)
        return self.batch(batch)

    def _download(self, batch, num):
        d = self._dir(batch)
        os.makedirs(os.path.join(d, "audio"), exist_ok=True)
        os.makedirs(os.path.join(d, "peaks"), exist_ok=True)
        path = os.path.join(d, "draft.json")
        if os.path.exists(path):
            doc = self._load(batch)      # never overwrite local work
            doc["pr"] = num
        else:
            doc = json.loads(self.hub.read_file(f"review/batches/{batch}.json"))
            doc["pr"] = num
            for c in doc["clips"]:
                c["done"] = False
        for c in doc["clips"]:
            audio = os.path.join(d, "audio", f"{c['id']}.flac")
            if not os.path.exists(audio):
                self.hub.fetch_to(f"recordings/{c['collection']}/{c['id']}.flac", audio)
            peaks = os.path.join(d, "peaks", f"{c['id']}.json")
            if not os.path.exists(peaks):
                self.hub.fetch_to(f"review/peaks/{c['id']}.json", peaks)
        self._save(batch, doc)

    def batch(self, batch):
        return self._load(batch)

    def edit(self, batch, clip_id, patch):
        with self.lock:
            doc = self._load(batch)
            clip = self._clip(doc, clip_id)
            apply_edit(clip, patch)
            if "done" in patch:
                if patch["done"] and not (clip_complete(clip) or patch.get("flagged")):
                    raise ApiError(400, "Every segment needs reviewed text, or mark it as no usable speech.")
                clip["done"] = bool(patch["done"])
                clip["flagged"] = bool(patch.get("flagged"))
            self._save(batch, doc)
            return clip

    def _clip(self, doc, clip_id):
        for c in doc["clips"]:
            if c["id"] == clip_id:
                return c
        raise ApiError(404, "That clip isn't in this batch.")

    def submit(self, batch):
        with self.lock:
            doc = self._load(batch)
            left = sum(not c.get("done") or not (c.get("flagged") or clip_complete(c))
                       for c in doc["clips"])
            if left:
                raise ApiError(400, f"{left} clip(s) still need review.")
            user = self.hub.username()
            status = DONE[doc["kind"]]
            corrections = [{
                "id": c["id"], "status": "flagged" if c.get("flagged") else status,
                "spoken_languages": c.get("spoken_languages"), "category": c.get("category"),
                "segments": [{"index": s["index"], "excluded": s.get("excluded", False),
                              **{k: (s.get(k) or "").strip() or None for k in TEXT}}
                             for s in c["segments"]],
            } for c in doc["clips"]]
            payload = json.dumps({"batch": batch, "reviewer": user, "corrections": corrections},
                                 indent=1, ensure_ascii=False).encode()
            self.hub.push_submission(doc["pr"], batch, payload)
            if any(c["num"] == doc["pr"] and c["status"] == "draft" for c in self.hub.list_claims()):
                self.hub.publish_claim(doc["pr"])     # a resubmission is already published
            return {"submitted": len(corrections), "pr": doc["pr"]}

    def media(self, batch, kind, name):
        """Local path of a downloaded audio or peaks file, or None."""
        if not ID.match(name) or kind not in ("audio", "peaks"):
            return None
        path = os.path.join(self._dir(batch), kind, name)
        return path if os.path.isfile(path) else None


def make_handler(reviewer, dist=DIST, port=PORT):
    allowed = {f"127.0.0.1:{port}", f"localhost:{port}"}

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_):
            pass

        def _json(self, status, body):
            data = json.dumps(body, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _body(self):
            n = int(self.headers.get("Content-Length") or 0)
            try:
                body = json.loads(self.rfile.read(n) or b"{}")
            except ValueError:
                raise ApiError(400, "Bad request.")
            if not isinstance(body, dict):
                raise ApiError(400, "Bad request.")
            return body

        def _guard(self):
            """Stop other websites reaching this local server through the browser."""
            host = self.headers.get("Host", "")
            origin = self.headers.get("Origin")
            if host not in allowed or (origin and urlparse(origin).netloc not in allowed):
                raise ApiError(403, "Forbidden.")
            if self.command != "GET" and self.headers.get("Content-Type") != "application/json":
                raise ApiError(415, "JSON only.")

        def _send_file(self, path, ctype):
            """Serves a file with Range support; audio seeking depends on it."""
            size = os.path.getsize(path)
            start, end, status = 0, size - 1, 200
            m = re.fullmatch(r"bytes=(\d*)-(\d*)", self.headers.get("Range") or "")
            if m and (m.group(1) or m.group(2)):
                status = 206
                if m.group(1):
                    start = int(m.group(1))
                    end = min(int(m.group(2)), size - 1) if m.group(2) else size - 1
                else:
                    start = max(0, size - int(m.group(2)))
                if start > end:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{size}")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(end - start + 1))
            if status == 206:
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.end_headers()
            with open(path, "rb") as f:
                f.seek(start)
                self.wfile.write(f.read(end - start + 1))

        def _route(self):
            self._guard()
            path = urlparse(self.path).path
            parts = [p for p in path.split("/") if p]
            method = self.command
            body = {} if method == "GET" else self._body()   # always drain it: keep-alive reuses the socket
            if parts[:1] == ["api"]:
                rest = parts[1:]
                if method == "GET" and rest == ["state"]:
                    return self._json(200, reviewer.state())
                if method == "POST" and rest == ["login"]:
                    return self._json(200, reviewer.login(body.get("token")))
                if len(rest) >= 2 and rest[0] == "batches":
                    batch = rest[1]
                    if method == "GET" and len(rest) == 2:
                        return self._json(200, reviewer.batch(batch))
                    if method == "POST" and rest[2:] == ["claim"]:
                        return self._json(200, reviewer.claim(batch))
                    if method == "POST" and rest[2:] == ["submit"]:
                        return self._json(200, reviewer.submit(batch))
                    if method == "PATCH" and len(rest) == 4 and rest[2] == "clips":
                        return self._json(200, reviewer.edit(batch, rest[3], body))
                raise ApiError(404, "Not found.")
            if method != "GET":
                raise ApiError(405, "Not allowed.")
            if parts[:1] == ["media"] and len(parts) == 4:
                found = reviewer.media(parts[1], parts[2], parts[3])
                if not found:
                    raise ApiError(404, "Not found.")
                return self._send_file(found, "audio/flac" if parts[2] == "audio" else "application/json")
            root = os.path.realpath(dist)
            target = os.path.realpath(os.path.join(root, *parts))
            if target != root and not target.startswith(root + os.sep):
                raise ApiError(404, "Not found.")
            if not os.path.isfile(target):
                target = os.path.join(root, "index.html")      # client-side routes
            if not os.path.isfile(target):
                raise ApiError(500, "The app isn't built. Run: make review")
            self._send_file(target, mimetypes.guess_type(target)[0] or "application/octet-stream")

        def _handle(self):
            try:
                self._route()
            except ApiError as e:
                self._json(e.status, {"error": e.message})
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception as e:
                print(f"error: {e}", file=sys.stderr)
                self._json(500, {"error": "Something went wrong talking to Hugging Face. Try again."})

        do_GET = do_POST = do_PATCH = _handle

    return Handler


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()
    reviewer = Reviewer(Hub())
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(reviewer, port=args.port))
    url = f"http://127.0.0.1:{args.port}"
    print(f"Review app running at {url}  (Ctrl-C to stop)")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
