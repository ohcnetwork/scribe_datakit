# Scribe Audio Collection

Multilingual clinical speech with Whisper drafts and human-reviewed transcripts and
English translations, built for fine-tuning speech-to-English models.

Reviewers: start with **[docs/reviewing.md](docs/reviewing.md)**. The app has the same
steps under **Reviewer guide** ([source](app/public/guide.html)). The rest of this page is
for the maintainer.

The dataset isn't in this repo. Audio, `flac/`, `peaks/` and `metadata.json` are
git-ignored and stay local; the published copy is
[`ohcnetwork/scribe_dataset`](https://huggingface.co/datasets/ohcnetwork/scribe_dataset).
See [design_spec.md](design_spec.md) for the data model and statuses.

## Layout

| Path | What |
|---|---|
| `build_metadata.py` | incremental ffprobe scan of `audio/` → `metadata.json` |
| `segment_audio.py` | `audio/` → seekable `flac/`, and segments of 28 s or less cut at pauses |
| `extract_peaks.py` | `flac/` → `peaks/<id>.json` waveforms |
| `transcribe.py` | Whisper large-v3 per segment: transcript and English translation, resumable |
| `hf_export.py` | corpus → `hf/`, ready to upload ([docs/huggingface.md](docs/huggingface.md)) |
| `review_admin.py` | maintainer: make batches, merge reviews, finalise |
| `review_server.py` | reviewer: local server behind the review app |
| `app/` | the review app (React, Vite) |
| `reviewers.txt` | Hugging Face usernames whose reviews are accepted |
| `migrate_schema_v2.py` | one-off v1 → v2 metadata migration; keeps `metadata.v1.json` |
| `test_*.py`, `app/e2e/` | checks, run with `make test` |

## Prerequisites

- **ffmpeg and ffprobe** on PATH (`brew install ffmpeg`).
- **Python 3.11+**. `extract_peaks.py` uses `audioop`, which Python 3.13 removed.
- **Node 18+** for the review app.
- Whisper: `pip install -r requirements.txt` (Apple Silicon). The ~3 GB model downloads
  on the first run.

## Processing audio

To add recordings, see [docs/ingesting-a-collection.md](docs/ingesting-a-collection.md).
`make ingest COLLECTION=<name>` runs these steps in order:

```bash
python3 build_metadata.py    # add new files to metadata.json; --collection names them
python3 segment_audio.py     # FLAC and segments
python3 extract_peaks.py     # waveforms
python3 transcribe.py        # both Whisper tasks; --limit N to smoke-test
python3 test_metadata.py     # durations and segments are sane
```

Every step is incremental and safe to re-run. `transcribe.py` is safe to stop with Ctrl-C.
Durations come from the audio packets themselves, because broken container timestamps
inflate what ffmpeg reports; `corrupt` marks those clips. `segment_audio.py` rebuilds
their timeline, so they're usable like any other clip.

## Review workflow

See [docs/maintaining.md](docs/maintaining.md) for how batches are created, claimed and merged.

## Tests

```bash
make test                                                   # everything offline
SCRIBE_LIVE_REPO=gigincg/test_repo python3 test_review_live.py   # against the real Hub
```

`test_review_ui.py` drives the app in Chrome with real audio. It needs `cd app && npm ci`.
