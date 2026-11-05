#!/usr/bin/env python3
"""Make a seekable FLAC per recording and split it into segments of 28 s or less.

Recordings stay whole: a segment is only a time range inside its recording, so
reviewers keep the context while each segment fits Whisper's 30 s training window.
Cuts land in pauses found by ffmpeg silencedetect; speech with no usable pause gets
a forced cut, counted in the summary.

Incremental: a clip that has segments is skipped (--force redoes it, which also
discards its generated text, so it refuses clips a human has touched).

    python segment_audio.py
"""
import argparse, json, os, re, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(__file__)
AUDIO_DIR = os.path.join(HERE, "audio")
FLAC_DIR = os.path.join(HERE, "flac")
META = os.path.join(HERE, "metadata.json")
SR = 16000
MAX_LEN = 28.0        # Whisper's window is 30 s; leave room
MIN_LEN = 1.0         # don't cut a sliver off the front of a segment
NOISE, MIN_PAUSE = "-35dB", 0.3   # ponytail: fixed threshold; per-clip noise floor if cuts land badly
DUR_TOLERANCE = 1.0


def blank_segment(index, start, end):
    return {"index": index, "start": start, "end": end, "whisper_language": None,
            "confidence": None, "no_speech_prob": None,
            "generated_transcript": None, "generated_translation": None,
            "final_transcript": None, "final_translation": None, "excluded": False}


def plan_cuts(duration, silences, max_len=MAX_LEN, min_len=MIN_LEN):
    """Time ranges covering 0..duration. Returns (ranges, forced_cut_count)."""
    pauses = sorted((a + b) / 2 for a, b in silences)
    ranges, start, forced = [], 0.0, 0
    while duration - start > max_len:
        fits = [p for p in pauses if start + min_len < p <= start + max_len]
        cut = fits[-1] if fits else start + max_len
        forced += not fits
        ranges.append((round(start, 2), round(cut, 2)))
        start = cut
    ranges.append((round(start, 2), round(duration, 2)))
    return ranges, forced


def probe_duration(path):
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                              "-of", "csv=p=0", path], capture_output=True, text=True, timeout=60)
        return float(out.stdout.strip())
    except (ValueError, subprocess.SubprocessError):
        return None


def transcode(c, dst, force=False):
    """Source audio → 16 kHz mono FLAC, capped at the known duration. True on success."""
    if os.path.exists(dst) and not force:
        return True
    src = os.path.join(AUDIO_DIR, c["filename"])
    if not os.path.exists(src):
        print(f"  missing audio {c['filename']}", file=sys.stderr)
        return False
    want = c["duration_sec"]
    tmp = dst + ".tmp.flac"
    try:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-err_detect", "ignore_err", "-i", src,
                        # corrupt clips have broken timestamps but intact audio frames:
                        # rebuild the timeline from the sample count
                        "-vn", "-ac", "1", "-ar", str(SR), "-af", "asetpts=N/SR/TB",
                        "-t", str(want + DUR_TOLERANCE),
                        "-c:a", "flac", tmp], capture_output=True, timeout=600, check=True)
    except subprocess.SubprocessError as e:
        print(f"  transcode failed {c['id']}: {e}", file=sys.stderr)
        return False
    got = probe_duration(tmp)
    if got is None or abs(got - want) > max(DUR_TOLERANCE, 0.05 * want):
        print(f"  duration mismatch {c['id']}: flac {got}s vs metadata {want}s", file=sys.stderr)
        os.remove(tmp)
        return False
    os.replace(tmp, dst)
    return True


def find_silences(path):
    err = subprocess.run(["ffmpeg", "-v", "info", "-i", path, "-af",
                          f"silencedetect=noise={NOISE}:d={MIN_PAUSE}", "-f", "null", "-"],
                         capture_output=True, text=True, timeout=600).stderr
    starts = re.findall(r"silence_start: ([\d.]+)", err)
    ends = re.findall(r"silence_end: ([\d.]+)", err)
    return [(float(a), float(b)) for a, b in zip(starts, ends)]


def prepare(c):
    """Returns (clip, ranges, forced), with ranges None when the audio is unusable."""
    dst = os.path.join(FLAC_DIR, f"{c['id']}.flac")
    if not c.get("duration_sec") or not transcode(c, dst):
        return c, None, 0
    ranges, forced = plan_cuts(probe_duration(dst), find_silences(dst))
    return c, ranges, forced


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="re-split clips nobody has reviewed")
    args = ap.parse_args()
    os.makedirs(FLAC_DIR, exist_ok=True)
    with open(META) as f:
        doc = json.load(f)
    if doc.get("schema_version") != 2:
        sys.exit("metadata.json is not schema v2; run migrate_schema_v2.py first")

    todo = [c for c in doc["clips"] if not c["segments"] or (args.force and c["status"] == "pending")]
    print(f"{len(todo)} clip(s) to segment", file=sys.stderr)
    failed = forced_total = 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        for c, ranges, forced in ex.map(prepare, todo):
            if ranges is None:
                failed += 1
                continue
            c["segments"] = [blank_segment(i, a, b) for i, (a, b) in enumerate(ranges)]
            forced_total += forced
    tmp = META + ".tmp"
    with open(tmp, "w") as f:
        json.dump(doc, f, indent=2)
    os.replace(tmp, META)
    segs = [s for c in doc["clips"] for s in c["segments"]]
    longest = max((s["end"] - s["start"] for s in segs), default=0)
    print(f"{len(segs)} segments in {sum(bool(c['segments']) for c in doc['clips'])} clips, "
          f"longest {longest:.1f}s, {forced_total} forced cuts, {failed} failed", file=sys.stderr)


if __name__ == "__main__":
    main()
