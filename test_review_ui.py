#!/usr/bin/env python3
"""Browser test of the review app: real Chrome, real audio, fake hub.

Run: python3 test_review_ui.py    (needs app dependencies: cd app && npm ci)
"""
import json, os, subprocess, sys, tempfile, threading
from http.server import ThreadingHTTPServer

from review_server import Reviewer, make_handler, DIST
from test_review_workflow import FakeHub, clip, publish

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    subprocess.run(["npm", "run", "--silent", "build"], cwd=os.path.join(HERE, "app"), check=True,
                   stdout=subprocess.DEVNULL)
    with tempfile.TemporaryDirectory() as tmp:
        wav = os.path.join(tmp, "tone.flac")
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=300:duration=6",
                        "-ar", "16000", "-ac", "1", wav], check=True)
        hub = FakeHub()
        a, b = clip("a"), clip("b", 1)
        a["duration_sec"] = 6.0
        for i, s in enumerate(a["segments"]):
            s.update(start=i * 2.0, end=i * 2.0 + 2.0, generated_transcript=f"generated transcript {i}")
        a["segments"][1]["start"], a["segments"][1]["end"] = 2.0, 4.0
        publish(hub, {"clips": [a, b]})
        with open(wav, "rb") as f:
            audio = f.read()
        hub.files["recordings/c1/a.flac"] = hub.files["recordings/c1/b.flac"] = audio
        hub.files["review/batches/other.json"] = json.dumps({"kind": "review", "clips": []}).encode()
        hub.prs[1] = {"batch": "other", "author": "someone-else", "status": "draft", "files": {}}

        server = ThreadingHTTPServer(("127.0.0.1", 0), None)
        port = server.server_address[1]
        server.RequestHandlerClass = make_handler(
            Reviewer(hub.as_user(None), os.path.join(tmp, "work")), DIST, port)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        shots = os.environ.get("SCRIBE_SHOTS", tmp)
        code = subprocess.run(["node", "e2e/review.mjs", f"http://127.0.0.1:{port}", shots],
                              cwd=os.path.join(HERE, "app")).returncode
        server.shutdown()
    if code:
        sys.exit("browser test failed")
    print("ok")


if __name__ == "__main__":
    main()
