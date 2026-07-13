#!/usr/bin/env python3
"""Regression check for the tricky bits of build_metadata.py.

Guards the duration/corruption logic: the whole reason that code exists is that
raw last-packet pts leaks 24h+ gap-filled durations from 256KB files. If that
logic breaks, durations blow up again and these asserts fail.

    python test_metadata.py      # run after build_metadata.py
"""
import json, os

META = os.path.join(os.path.dirname(__file__), "metadata.json")


def main():
    d = json.load(open(META))
    clips = d["clips"]
    assert clips, "no clips"
    assert d["clip_count"] == len(clips)
    assert d.get("schema_version") == 1, "schema_version missing/unexpected"

    for c in clips:
        dur = c["duration_sec"]
        assert dur is not None, f"{c['filename']}: null duration"
        assert 0 < dur < 7200, f"{c['filename']}: implausible duration {dur}s (gap-fill leak?)"
        # a corrupt clip must never keep an absurd size:duration ratio
        if dur:
            kbps = c["size_bytes"] * 8 / dur / 1000
            assert kbps >= 1, f"{c['filename']}: {kbps:.2f} kbps — corruption not corrected"
        assert set(("id", "language", "transcript", "transcript_auto", "confidence",
                    "no_speech_prob", "model", "status", "category", "container",
                    "codec", "channels", "bitrate_kbps", "tags")) <= c.keys()

    total = sum(c["duration_sec"] for c in clips)
    assert abs(total - d["total_duration_sec"]) < 1, "total_duration_sec mismatch"
    print(f"ok: {len(clips)} clips, {total/3600:.1f}h, "
          f"{sum(c.get('corrupt', False) for c in clips)} corrupt — all durations sane")


if __name__ == "__main__":
    main()
