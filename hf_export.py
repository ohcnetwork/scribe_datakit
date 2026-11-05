#!/usr/bin/env python3
"""Export the corpus to hf/, in the layout the Hub and its Dataset Viewer understand.

    hf/README.md                           dataset card; one subset per collection
    hf/data/<collection>/train/            one FLAC per segment + metadata.jsonl (training)
    hf/recordings/<collection>/            one FLAC per full recording + metadata.jsonl
    hf/review/peaks/<id>.json              waveforms for the review app
    hf/review/batches/*.json               written by review_admin.py, left alone here

Segment rows keep machine text (generated_*) and human text (final_*) apart; there is
no fallback between them. Incremental: existing audio is kept (--force redoes it), and
files that no longer belong are removed so the audio and the metadata always match.

    python hf_export.py                      # everything
    python hf_export.py --min-status final   # segment rows approved for training only
"""
import argparse, json, os, shutil, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(__file__)
META = os.path.join(HERE, "metadata.json")
FLAC_DIR = os.path.join(HERE, "flac")
PEAKS_DIR = os.path.join(HERE, "peaks")
HF_DIR = os.path.join(HERE, "hf")
TEXT = ("generated_transcript", "generated_translation", "final_transcript", "final_translation")
STATUS_RANK = {"reviewed": 1, "qa_complete": 2, "final": 3}   # pending/flagged rank below all


def seg_id(c, s):
    return f"{c['id']}_s{s['index']:03d}"


def select_clips(clips, min_status=None):
    """Clips with audio segments, at or past min_status."""
    return [c for c in clips if c.get("segments") and (
        not min_status or STATUS_RANK.get(c.get("status"), 0) >= STATUS_RANK[min_status])]


def segment_row(c, s):
    return {"file_name": f"{seg_id(c, s)}.flac", "id": seg_id(c, s), "recording_id": c["id"],
            "collection": c["collection"], "start": s["start"], "end": s["end"],
            "duration_sec": round(s["end"] - s["start"], 2),
            "whisper_language": s.get("whisper_language"),
            "spoken_languages": c.get("spoken_languages"),
            **{k: s.get(k) for k in TEXT},
            "confidence": s.get("confidence"), "no_speech_prob": s.get("no_speech_prob"),
            "status": c["status"], "category": c.get("category"), "model": c.get("model"),
            "recorded_at": c.get("recorded_at")}


def joined(segments, key):
    """The whole recording's text, or None unless every usable segment has it."""
    parts = [s.get(key) for s in segments if not s.get("excluded")]
    return " ".join(p for p in parts if p) if parts and all(p is not None for p in parts) else None


def recording_row(c):
    return {"file_name": f"{c['id']}.flac", "id": c["id"], "collection": c["collection"],
            "duration_sec": c["duration_sec"], "segment_count": len(c["segments"]),
            "whisper_language": c.get("whisper_language"),
            "spoken_languages": c.get("spoken_languages"),
            **{k: joined(c["segments"], k) for k in TEXT},
            "status": c["status"], "category": c.get("category"), "model": c.get("model"),
            "recorded_at": c.get("recorded_at")}


def cut(job):
    src, dst, s, force = job
    if os.path.exists(dst) and not force:
        return True
    tmp = dst + ".tmp.flac"
    try:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(s["start"]),
                        "-t", str(round(s["end"] - s["start"], 3)), "-i", src, "-c:a", "flac", tmp],
                       capture_output=True, timeout=120, check=True)
    except subprocess.SubprocessError as e:
        print(f"  cut failed {dst}: {e}", file=sys.stderr)
        return False
    os.replace(tmp, dst)
    return True


def write_rows(directory, rows):
    """metadata.jsonl, after removing audio it doesn't list and checking the rest exists."""
    os.makedirs(directory, exist_ok=True)
    want = {r["file_name"] for r in rows}
    for name in os.listdir(directory):
        if name.endswith(".flac") and name not in want:
            os.remove(os.path.join(directory, name))
    missing = [n for n in want if not os.path.exists(os.path.join(directory, n))]
    if missing:
        sys.exit(f"{directory}: {len(missing)} audio file(s) missing, e.g. {missing[0]}")
    with open(os.path.join(directory, "metadata.jsonl"), "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


CARD = """---
license: {license}
pretty_name: Scribe Audio Collection
task_categories:
- automatic-speech-recognition
- translation
language:
{langs}
size_categories:
- {size}
configs:
- config_name: all
  default: true
  data_files:
  - split: train
    path: data/*/train/*
- config_name: recordings
  data_files:
  - split: train
    path: recordings/*/*
{collections}---

# Scribe Audio Collection

{n} segments of 28 seconds or less from {recordings} recordings ({hours:.1f} h), as 16 kHz
mono FLAC, with Whisper drafts and human-reviewed text.

Generated by `hf_export.py`. Don't edit this repo by hand: reviews arrive as pull
requests and are re-exported.

## Subsets

- `all`: every segment, for training.
- One subset per collection: {collection_names}.
- `recordings`: the full recordings, with each recording's text joined.

## Fields

| Field | Meaning |
|---|---|
| `audio` | 16 kHz mono FLAC |
| `generated_transcript` | Whisper output in the spoken language; machine text |
| `generated_translation` | Whisper English translation; machine text |
| `final_transcript` | human-reviewed transcript; null until reviewed |
| `final_translation` | human-reviewed English translation; null until reviewed |
| `status` | `pending`, `reviewed`, `qa_complete`, `final` (approved for training) or `flagged` |
| `whisper_language` | Whisper's language guess; unreliable |
| `spoken_languages` | human-confirmed languages; null until confirmed |
| `recording_id`, `start`, `end` | where a segment sits in its recording, in seconds |
| `confidence` | mean `exp(avg_logprob)`, 0..1; a poor filter for bad text |
| `no_speech_prob` | mean no-speech probability, 0..1 |
| `collection`, `category`, `duration_sec`, `model`, `recorded_at` | as derived upstream |

English-only audio has no reviewed translation, so use `final_transcript` as its English
text. For training, keep final rows:

```python
from datasets import load_dataset
ds = load_dataset("{repo}", split="train").filter(lambda r: r["status"] == "final")
```
"""


def card(clips, license_, repo):
    collections = sorted({c["collection"] for c in clips})
    langs = sorted({l for c in clips for l in c.get("spoken_languages") or []}) or ["multilingual"]
    segs = sum(len(c["segments"]) for c in clips)
    size = "1K<n<10K" if segs >= 1000 else "n<1K"
    blocks = "".join(f"- config_name: {n}\n  data_files:\n  - split: train\n"
                     f"    path: data/{n}/train/*\n" for n in collections)
    return CARD.format(license=license_, size=size, repo=repo, n=segs, recordings=len(clips),
                       hours=sum(c["duration_sec"] for c in clips) / 3600, collections=blocks,
                       collection_names=", ".join(f"`{n}`" for n in collections),
                       langs="\n".join(f"- {l}" for l in langs))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-status", choices=STATUS_RANK, help="segment rows at this status or later")
    ap.add_argument("--force", action="store_true", help="re-cut every segment")
    ap.add_argument("--license", default="cc-by-4.0")
    ap.add_argument("--repo", default=os.environ.get("HF_REPO", "ohcnetwork/scribe_dataset"))
    args = ap.parse_args()

    with open(META) as f:
        clips = json.load(f)["clips"]
    every = select_clips(clips)
    picked = select_clips(clips, args.min_status)
    print(f"{len(every)} recordings, {len(picked)} with segment rows", file=sys.stderr)

    for c in every:     # full recordings always ship: reviewers need them
        d = os.path.join(HF_DIR, "recordings", c["collection"])
        os.makedirs(d, exist_ok=True)
        dst = os.path.join(d, f"{c['id']}.flac")
        if not os.path.exists(dst):
            shutil.copy2(os.path.join(FLAC_DIR, f"{c['id']}.flac"), dst)
    jobs = []
    for c in picked:
        d = os.path.join(HF_DIR, "data", c["collection"], "train")
        os.makedirs(d, exist_ok=True)
        for s in c["segments"]:
            jobs.append((os.path.join(FLAC_DIR, f"{c['id']}.flac"),
                         os.path.join(d, f"{seg_id(c, s)}.flac"), s, args.force))
    with ThreadPoolExecutor(max_workers=8) as ex:
        failed = sum(not ok for ok in ex.map(cut, jobs))
    if failed:
        sys.exit(f"{failed} segment(s) failed to cut")

    for name in sorted({c["collection"] for c in every}):
        write_rows(os.path.join(HF_DIR, "recordings", name),
                   [recording_row(c) for c in every if c["collection"] == name])
        write_rows(os.path.join(HF_DIR, "data", name, "train"),
                   [segment_row(c, s) for c in picked if c["collection"] == name
                    for s in c["segments"]])
    peaks = os.path.join(HF_DIR, "review", "peaks")
    os.makedirs(peaks, exist_ok=True)
    for c in every:
        shutil.copy2(os.path.join(PEAKS_DIR, f"{c['id']}.json"), peaks)
    with open(os.path.join(HF_DIR, "README.md"), "w") as f:
        f.write(card(every, args.license, args.repo))
    print(f"wrote {HF_DIR}: {len(jobs)} segments, {len(every)} recordings", file=sys.stderr)


if __name__ == "__main__":
    main()
