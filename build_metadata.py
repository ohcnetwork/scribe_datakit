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

User-owned fields (segments, spoken_languages, speaker_id, status, category, collection) are always
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

SCHEMA_VERSION = 2   # bump when the clip/doc shape changes; the app warns on mismatch

# fields owned by the user / transcription job — never overwritten by a re-probe
KEEP = ("segments", "whisper_language", "spoken_languages", "speaker_id", "model", "status",
        "category", "collection", "reviewed_by", "qa_by")
MODEL_USER_DEFAULTS = {
    "segments": [], "whisper_language": None, "spoken_languages": None, "speaker_id": None,
    "model": None,
    "status": "pending", "category": "uncategorized", "reviewed_by": None, "qa_by": None,
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


def coded_duration(path):
    """Sum of the audio packet durations, or None. Packet size varies between clips
    (20 ms and 60 ms both occur), so read it rather than assuming one."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "a:0",
             "-show_entries", "packet=duration_time", "-of", "csv=p=0", path],
            capture_output=True, text=True, timeout=300).stdout
        total = sum(float(l.strip().strip(",")) for l in out.splitlines() if l.strip(" ,"))
        return round(total, 2) or None
    except Exception:
        return None


def compute_duration(path, codec):
    """Real duration + corruption flag.

    ~11% of these webm files carry broken container timestamps. The decoder honours
    them and gap-fills silence, so the reported `time=` inflates wildly (one 627 s
    clip reads as 4070 s). For opus the coded-frame count is immune to that and
    exact, so it *is* the duration; the decoded time is only used to detect the
    disagreement, which is precisely what "corrupt" means here.

    Don't reintroduce a bitrate threshold to spot the bad ones — that's what the
    previous version did (< 8 kbps) and it silently missed 26 clips whose inflation
    only dragged them down to 9–20 kbps. Comparing against the frame count has no
    magic number to get wrong. Non-opus codecs have no frame-count shortcut and keep
    the decoded time."""
    decoded = None
    try:
        err = subprocess.run(
            ["ffmpeg", "-v", "error", "-stats", "-err_detect", "ignore_err",
             "-i", path, "-f", "null", "-"],
            capture_output=True, text=True, timeout=600).stderr
        m = re.findall(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)", err)
        if m:
            h, mm, s = m[-1]
            decoded = round(int(h) * 3600 + int(mm) * 60 + float(s), 2)
    except Exception:
        pass

    if codec == "opus":
        coded = coded_duration(path)
        if coded:
            corrupt = decoded is None or abs(decoded - coded) > max(1.0, 0.05 * coded)
            return coded, corrupt
    return decoded, False


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
    duration, corrupt = compute_duration(path, codec)
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
        "whisper_language": None,   # Whisper's guess, by audio covered; unreliable
        "spoken_languages": None,   # human-confirmed list, e.g. ["ml", "en"]; null = unconfirmed
        "speaker_id": None,         # null until known
        "segments": [],             # time ranges holding the text (segment_audio.py)
        "model": None,
        "status": "pending",
        "category": "uncategorized",
        "reviewed_by": None,
        "qa_by": None,
    }


def cached(rec):
    """Reuse a prior record only if it carries every derived field."""
    return set(DERIVED) <= rec.keys()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="re-probe every file")
    ap.add_argument("--collection", default="scribe-staging",
                    help="collection for clips new to the manifest")
    args = ap.parse_args()

    prev = {}
    if os.path.exists(OUT):
        with open(OUT) as f:
            old_doc = json.load(f)
        if old_doc.get("schema_version") != SCHEMA_VERSION:
            sys.exit(f"{OUT} is schema v{old_doc.get('schema_version')}; "
                     "run migrate_schema_v2.py first")
        prev = {c["filename"]: c for c in old_doc.get("clips", [])}

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
                c.update({k: old[k] for k in KEEP if k in old})
        else:
            c = prev[f]                              # cache hit (no re-probe)
        # ensure model/user fields exist on cached records too (schema migration)
        for k, v in MODEL_USER_DEFAULTS.items():
            c.setdefault(k, v)
        c.setdefault("collection", args.collection)
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
