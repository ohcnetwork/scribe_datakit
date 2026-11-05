#!/usr/bin/env python3
"""Precompute waveform peaks per clip so the app can draw a real, seekable
waveform without decoding audio in the browser.

Why offline: these webm/opus files carry no duration header and the browser's
decodeAudioData fails on them, so wavesurfer can't render or seek. Here we decode
once with ffmpeg (which tolerates them), reduce to ~800 amplitude peaks, and write
a sidecar the app feeds to wavesurfer as { peaks, duration } — no browser decode.

Output: peaks/<id>.json = {"peaks": [0..1, ...], "duration": <sec>}
Incremental: skips clips that already have a peaks file (--force to redo).
ffmpeg must be on PATH. Run build_metadata.py first (needs durations).

    python extract_peaks.py            # incremental
    python extract_peaks.py --force
"""
import argparse, json, os, subprocess, sys
# ponytail: audioop is C-speed and stdlib on 3.11, but removed in Python 3.13.
# Upgrade path when moving to 3.13+: replace audioop.max with a strided pure-Python
# scan (max(abs()) over ~256 samples/bucket) or numpy — see extract().
import audioop
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(__file__)
FLAC_DIR = os.path.join(HERE, "flac")
META = os.path.join(HERE, "metadata.json")
OUT_DIR = os.path.join(HERE, "peaks")
N_PEAKS = 800          # horizontal resolution of the rendered waveform
SR = 8000              # decode rate — plenty for an amplitude envelope


def extract(clip):
    path = os.path.join(FLAC_DIR, f"{clip['id']}.flac")   # what reviewers hear
    dur = clip.get("duration_sec")
    cap = (dur + 2) if dur else 3600           # bound the ~7% timestamp-corrupt clips
    try:
        raw = subprocess.run(
            ["ffmpeg", "-v", "error", "-err_detect", "ignore_err", "-t", str(cap),
             "-i", path, "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
            capture_output=True, timeout=600).stdout
    except Exception as e:
        return clip["id"], None, str(e)

    n = len(raw) // 2
    if n == 0:
        peaks = [0.0] * N_PEAKS
    else:
        gmax = audioop.max(raw, 2) or 1        # audioop.max = C-speed |max sample|
        step = (n // N_PEAKS) or 1
        peaks = []
        for i in range(N_PEAKS):
            a = (i * step) * 2                 # byte offsets (2 bytes/sample)
            b = a + step * 2
            chunk = raw[a:b]
            peaks.append(round(audioop.max(chunk, 2) / gmax, 3) if chunk else 0.0)

    with open(os.path.join(OUT_DIR, clip["id"] + ".json"), "w") as f:
        json.dump({"peaks": peaks, "duration": dur}, f)
    return clip["id"], len(peaks), None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="re-extract every clip")
    args = ap.parse_args()
    os.makedirs(OUT_DIR, exist_ok=True)

    clips = json.load(open(META))["clips"]
    todo = [c for c in clips
            if args.force or not os.path.exists(os.path.join(OUT_DIR, c["id"] + ".json"))]
    print(f"{len(clips)} clips, extracting {len(todo)}", file=sys.stderr)

    done = fail = 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        for i, (cid, npk, err) in enumerate(ex.map(extract, todo), 1):
            if err:
                fail += 1
                print(f"  FAIL {cid}: {err}", file=sys.stderr)
            else:
                done += 1
            if i % 100 == 0:
                print(f"  {i}/{len(todo)}", file=sys.stderr)
    print(f"done: {done} written, {fail} failed", file=sys.stderr)


if __name__ == "__main__":
    main()
