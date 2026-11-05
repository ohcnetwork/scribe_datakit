# Publishing to HuggingFace

The corpus is published to the Hub as a derived artifact. `metadata.json` stays the
single source of truth; the HF dataset is regenerated from it, never edited in place.
Corrections flow through the app → `make apply-corrections`, and you re-export afterwards.

```
metadata.json (source of truth)
      └─ make hf-export  → hf/  →  hf upload
```

## Export

```bash
make hf-export    # needs the audio locally
```

Output — HF's `audiofolder` layout, which the Hub auto-detects (no loading script):

```
hf/
├── README.md                   dataset card (YAML front-matter)
└── data/train/
    ├── metadata.jsonl          one row per clip
    └── <id>.flac               16 kHz mono
```

`hf/` is git-ignored — it's regenerated, not committed.

### What `hf-export` does

**Transcodes to 16 kHz mono FLAC.** The webm/opus originals are deliberately *not*
shipped: HF's `Audio` feature decodes with libsndfile, which has no WebM support at
all, and these files carry no duration header. FLAC decodes everywhere, is what
LibriSpeech ships, and ASR models resample to 16 kHz regardless.

**Excludes corrupt clips.** ~9% of the source files have broken container timestamps.
Left alone, ffmpeg honours them and gap-fills silence — a 627 s clip decodes as 4070 s.
Those are skipped (`--include-corrupt` to override).

**Verifies every transcode.** Each output is capped at the known duration and re-probed;
a FLAC whose length disagrees with `metadata.json` is dropped rather than published. The
export prints how many were dropped — it should be `0`.

**Incremental.** A clip whose `.flac` already exists is skipped, so re-runs after adding
audio are near-instant. `--force` re-transcodes everything.

### Row schema

`file_name` is HF's magic column — it's cast to the `Audio` feature on load.

```json
{"file_name": "0a1b….flac", "id": "0a1b…", "collection": "scribe-staging",
 "whisper_language": "hi", "spoken_languages": null,
 "generated_transcript": "…", "generated_translation": "…",
 "final_transcript": null, "final_translation": null,
 "duration_sec": 12.3, "confidence": 0.91, "no_speech_prob": 0.02,
 "status": "pending", "category": "medical-scribe", "model": "whisper-large-v3",
 "recorded_at": "2025-…"}
```

`generated_*` is **always machine text** and `final_*` is **always human-reviewed**;
there is no fallback between them. English-only audio has no translation, so use
`final_transcript` as its English text. Train on `status == "final"` rows. (Nothing is
reviewed yet, so `--min-status` currently exports an empty set.)

### Flags

```bash
python3 hf_export.py --min-status final     # reviewed, qa_complete or final; never pending/flagged
python3 hf_export.py --include-corrupt      # include broken-timestamp clips
python3 hf_export.py --force                # re-transcode everything
python3 hf_export.py --license cc0-1.0      # dataset card license (default cc-by-4.0)
```

## Push

Install the CLI and authenticate once (a maintainer credential — never used at runtime
or in CI):

```bash
brew install hf
hf auth login
```

Then upload the export directory as a dataset repo:

```bash
cd hf
hf upload ohcnetwork/scribe_dataset . --repo-type=dataset
```

The CLI content-hashes files, so re-uploads only transfer what changed. Override the
target repo with the `HF_REPO` environment variable (`make hf-export` echoes the exact push command).

## Consuming it

```python
from datasets import load_dataset

ds = load_dataset("ohcnetwork/scribe_dataset", split="train")
ds[0]["audio"]          # {'array': …, 'sampling_rate': 16000}
ds[0]["final_translation"]

gold = ds.filter(lambda r: r["status"] == "final")
```
