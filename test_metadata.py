#!/usr/bin/env python3
"""Regression check for the tricky bits of build_metadata.py.

Guards the duration/corruption logic: the whole reason that code exists is that
raw last-packet pts leaks 24h+ gap-filled durations from 256KB files. If that
logic breaks, durations blow up again and these asserts fail.

    python test_metadata.py      # run after build_metadata.py
"""
import json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(__file__)
META = os.path.join(HERE, "metadata.json")
AUDIO_DIR = os.path.join(HERE, "audio")
STATUSES = ("pending", "reviewed", "qa_complete", "final", "flagged")


def check_against_audio(clips):
    """The invariant that actually matters: for opus, duration == coded frame count.

    Metadata alone can't prove a duration is real — the bug this guards against
    (gap-filled timestamps inflating a 627 s clip to 4070 s) produced values that
    looked perfectly plausible in isolation. Only the packet count catches it. A
    bitrate floor can't substitute: genuinely silent clips run at ~2 kbps via opus
    DTX, so low bitrate is not evidence of corruption.

    Skipped when audio/ is absent (the repo is data-free by default).
    """
    if not os.path.isdir(AUDIO_DIR):
        print("audio/ absent: skipping packet cross-check")
        return

    def coded(c):
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "a:0",
             "-show_entries", "packet=duration_time", "-of", "csv=p=0",
             os.path.join(AUDIO_DIR, c["filename"])],
            capture_output=True, text=True).stdout
        return c, sum(float(l.strip().strip(",")) for l in out.splitlines() if l.strip(" ,")) or None

    opus = [c for c in clips if c.get("codec") == "opus"]
    bad = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        for c, want in ex.map(coded, opus):
            if want is not None and abs(c["duration_sec"] - want) > 0.02:
                bad.append(f"{c['filename']}: {c['duration_sec']}s != {want:.2f}s (coded frames)")
    assert not bad, "durations disagree with the coded frame count:\n  " + "\n  ".join(bad[:10])
    print(f"  packet cross-check: {len(opus)} opus clips, all durations exact")


def main():
    d = json.load(open(META))
    clips = d["clips"]
    assert clips, "no clips"
    assert d["clip_count"] == len(clips)
    assert d.get("schema_version") == 2, "schema_version missing/unexpected"

    for c in clips:
        dur = c["duration_sec"]
        assert dur is not None, f"{c['filename']}: null duration"
        assert 0 < dur < 7200, f"{c['filename']}: implausible duration {dur}s (gap-fill leak?)"
        # a corrupt clip must never keep an absurd size:duration ratio
        if dur:
            kbps = c["size_bytes"] * 8 / dur / 1000
            assert kbps >= 1, f"{c['filename']}: {kbps:.2f} kbps — corruption not corrected"
        assert set(("id", "whisper_language", "spoken_languages", "speaker_id", "collection", "segments",
                    "model", "status", "category", "container", "codec", "channels",
                    "bitrate_kbps", "tags")) <= c.keys()
        assert c["status"] in STATUSES, f"{c['filename']}: bad status {c['status']!r}"
        if c["status"] in ("reviewed", "qa_complete", "final"):
            assert all(s["excluded"] or s["final_transcript"] or s["final_translation"]
                       for s in c["segments"]), f"{c['filename']}: {c['status']} missing human text"
        for a, b in zip(c["segments"], c["segments"][1:]):
            assert a["end"] == b["start"], f"{c['filename']}: segments don't join up"
        assert all(s["end"] - s["start"] <= 28.01 for s in c["segments"]), c["filename"]

    total = sum(c["duration_sec"] for c in clips)
    assert abs(total - d["total_duration_sec"]) < 1, "total_duration_sec mismatch"
    check_against_audio(clips)
    print(f"ok: {len(clips)} clips, {total/3600:.1f}h, "
          f"{sum(c.get('corrupt', False) for c in clips)} corrupt — all durations sane")


if __name__ == "__main__":
    main()
