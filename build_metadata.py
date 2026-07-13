#!/usr/bin/env python3
"""Scan audio/ and (re)build metadata.json — incremental by default.

ffmpeg/ffprobe run **once per file, ever**: a clip already probed in metadata.json
is reused untouched, so re-runs after adding new audio only pay for the new files.
A file is re-probed only if it's new, missing a derived field (auto-migration when
this script gains fields), or when --force is passed (use after changing the
derivation logic itself).

Everything ffprobe can derive is captured: container, codec, sample rate, channels,
channel layout, bitrate, duration, corruption flag, and container tags. Duration is
computed defensively — these webm files carry no duration header and ~7% have
corrupt timestamps that gap-fill silence to 24h+; see compute_duration().

User-owned fields (transcript, language, model, status, category) are always
preserved across runs. ffmpeg + ffprobe must be on PATH.

    python build_metadata.py            # incremental
    python build_metadata.py --force    # re-derive every file
"""
import argparse, json, os, re, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

AUDIO_DIR = os.path.join(os.path.dirname(__file__), "audio")
OUT = os.path.join(os.path.dirname(__file__), "metadata.json")
EXTS = (".webm", ".mp4", ".ogg", ".mp3", ".wav", ".m4a")

SCHEMA_VERSION = 1   # bump when the clip/doc shape changes; the app warns on mismatch

# fields owned by the user / transcription job — never overwritten by a re-probe
KEEP = ("transcript", "transcript_auto", "confidence", "no_speech_prob",
        "language", "model", "status", "category")
MODEL_USER_DEFAULTS = {
    "transcript_auto": None, "transcript": None, "confidence": None,
    "no_speech_prob": None, "language": None, "model": None,
    "status": "unverified", "category": "uncategorized",
}
# derived fields; if any is missing on a cached record we re-probe it (auto-migrate)
DERIVED = ("container", "codec", "codec_long", "sample_rate", "channels",
           "channel_layout", "size_bytes", "duration_sec", "bitrate_kbps",
           "corrupt", "recorded_at", "format", "tags")


def ffprobe_json(path):
    """Container + first audio stream via a single ffprobe call."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-print_format", "json",
             "-show_format", "-show_streams", path],
            capture_output=True, text=True, timeout=120).stdout
        d = json.loads(out or "{}")
    except Exception:
        return {}, {}
    fmt = d.get("format", {})
    astream = next((s for s in d.get("streams", []) if s.get("codec_type") == "audio"), {})
    return fmt, astream


def compute_duration(path, codec, size):
    """Real duration + corruption flag.

    Decode to null and read the real `time=` (accurate for any codec). If that
    implies < 8 kbps it's impossible for this ~128 kbps opus voice — the decoder
    inflated it with gap-filled silence, so fall back to the coded-frame count
    (opus = 60 ms/pkt, validated exactly against healthy files)."""
    duration = None
    try:
        err = subprocess.run(
            ["ffmpeg", "-v", "error", "-stats", "-err_detect", "ignore_err",
             "-i", path, "-f", "null", "-"],
            capture_output=True, text=True, timeout=600).stderr
        m = re.findall(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)", err)
        if m:
            h, mm, s = m[-1]
            duration = round(int(h) * 3600 + int(mm) * 60 + float(s), 2)
    except Exception:
        pass

    corrupt = False
    if codec == "opus" and duration and size * 8 / duration < 8000:
        try:
            n = subprocess.run(
                ["ffprobe", "-v", "error", "-select_streams", "a:0", "-count_packets",
                 "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", path],
                capture_output=True, text=True, timeout=300).stdout.strip()
            if n.isdigit():
                duration, corrupt = round(int(n) * 0.06, 2), True
        except Exception:
            pass
    return duration, corrupt


def probe(fname):
    path = os.path.join(AUDIO_DIR, fname)
    stem, ext = os.path.splitext(fname)
    uid = stem[:36] if len(stem) >= 36 else stem      # UUID prefix
    ts = stem[36:] if len(stem) >= 36 else ""          # trailing unix seconds
    recorded_at = None
    if ts.isdigit():
        try:
            recorded_at = datetime.fromtimestamp(int(ts), timezone.utc).isoformat()
        except (ValueError, OSError):
            pass

    size = os.path.getsize(path)
    fmt, astream = ffprobe_json(path)
    codec = astream.get("codec_name")
    sr = astream.get("sample_rate")
    ch = astream.get("channels")
    duration, corrupt = compute_duration(path, codec, size)
    tags = {k.lower(): v for k, v in (fmt.get("tags") or {}).items()}

    return {
        "id": uid,
        "filename": fname,
        "format": ext.lstrip(".").lower(),          # from extension
        "container": fmt.get("format_name"),        # e.g. "matroska,webm"
        "codec": codec,
        "codec_long": astream.get("codec_long_name"),
        "sample_rate": int(sr) if sr and sr.isdigit() else None,
        "channels": ch,
        "channel_layout": astream.get("channel_layout"),
        "size_bytes": size,
        "duration_sec": duration,
        "bitrate_kbps": round(size * 8 / duration / 1000, 1) if duration else None,
        "corrupt": corrupt,
        "recorded_at": recorded_at,
        "tags": tags,
        "language": None,
        "transcript_auto": None,    # immutable Whisper output (transcribe.py)
        "transcript": None,         # human-corrected, defaults to transcript_auto
        "confidence": None,         # 0..1, mean exp(avg_logprob) over segments
        "no_speech_prob": None,     # 0..1, mean over segments
        "model": None,
        "status": "unverified",
        "category": "uncategorized",
    }


def cached(rec):
    """Reuse a prior record only if it carries every derived field."""
    return set(DERIVED) <= rec.keys()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="re-probe every file")
    args = ap.parse_args()

    prev = {}
    if os.path.exists(OUT):
        with open(OUT) as f:
            prev = {c["filename"]: c for c in json.load(f).get("clips", [])}

    files = sorted(f for f in os.listdir(AUDIO_DIR) if f.lower().endswith(EXTS))
    to_probe = [f for f in files
                if args.force or f not in prev or not cached(prev[f])]
    print(f"{len(files)} files on disk, probing {len(to_probe)} "
          f"(reusing {len(files) - len(to_probe)})", file=sys.stderr)

    probed = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        for i, c in enumerate(ex.map(probe, to_probe), 1):
            probed[c["filename"]] = c
            if i % 50 == 0:
                print(f"  {i}/{len(to_probe)}", file=sys.stderr)

    clips = []
    for f in files:
        if f in probed:
            c = probed[f]
            old = prev.get(f)
            if old:                                  # carry user fields forward
                for k in KEEP:
                    if old.get(k) not in (None, "", "unverified", "uncategorized"):
                        c[k] = old[k]
        else:
            c = prev[f]                              # cache hit (no re-probe)
        # ensure model/user fields exist on cached records too (schema migration)
        for k, v in MODEL_USER_DEFAULTS.items():
            c.setdefault(k, v)
        # pre-split records: the old single transcript was the auto output
        if c.get("transcript") and not c.get("transcript_auto"):
            c["transcript_auto"] = c["transcript"]
        clips.append(c)

    total = sum(c["duration_sec"] or 0 for c in clips)
    doc = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": None,   # stamped by caller/CI; kept null for reproducible diffs
        "clip_count": len(clips),
        "total_duration_sec": round(total, 2),
        "clips": clips,
    }
    with open(OUT, "w") as f:
        json.dump(doc, f, indent=2)
    print(f"wrote {OUT}: {len(clips)} clips, {total/3600:.1f}h audio, "
          f"{sum(c.get('corrupt') for c in clips)} corrupt", file=sys.stderr)


if __name__ == "__main__":
    main()
