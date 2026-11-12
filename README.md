# Scribe Audio Collection

Multilingual clinical speech with Whisper drafts and human-reviewed transcripts and
English translations, built for fine-tuning speech-to-English models.

- **Here to review recordings?** Go to [Reviewers](#reviewers).
- **Running the dataset?** Go to [Maintainers](#maintainers).

## Reviewers

You listen to recordings and correct the text Whisper produced, using an app that runs on
your own computer. Setup takes a few minutes and you only do it once.

### 1. Get access

Create a free [Hugging Face account](https://huggingface.co/join) and send your username to
the maintainer, who'll give you access.

### 2. Install the tools

You need [Git](https://git-scm.com/downloads), [Python 3.11 or newer](https://www.python.org/downloads/)
and [Node 18 or newer](https://nodejs.org). On Windows, run everything in
[WSL](https://learn.microsoft.com/windows/wsl/install), which also gives you `make`.

### 3. Start the app

```bash
git clone <this repo>
cd scribe_dump
make review
```

The first run takes a few minutes, then the app opens in your browser at
http://127.0.0.1:4321. Keep the terminal open while you work, and press Ctrl-C there to stop.
Next time, run `make review` from the same folder.

**Using Claude Code?** Open it in this folder and ask it to set up the review app.
[CLAUDE.md](CLAUDE.md) tells it what to do.

### 4. Connect Hugging Face

The first time, the app asks for an access token:

1. Open [your access tokens](https://huggingface.co/settings/tokens) and choose **Create new token**.
2. Choose the **Write** type and give it any name.
3. Paste it into the app. It's stored on your computer only. Don't share it with anyone.

### 5. Start reviewing

Open **Reviewer guide** in the app's sidebar. It takes you through claiming a batch,
reviewing clips and submitting your work. [docs/reviewing.md](docs/reviewing.md) has the same
steps without screenshots.
**How it works**, also in the sidebar, explains what each step does on Hugging Face.

## Maintainers

| I want to | Go to |
|---|---|
| Add new recordings | [docs/ingesting-a-collection.md](docs/ingesting-a-collection.md) |
| Create batches, or merge and finalise reviews | [docs/maintaining.md](docs/maintaining.md) |
| Publish to Hugging Face | [docs/huggingface.md](docs/huggingface.md) |
| Understand the fields and statuses | [design_spec.md](design_spec.md) |
| See what reviewers are told | [docs/reviewing.md](docs/reviewing.md), and the in-app guide at [app/public/guide.html](app/public/guide.html) |
| Change what coding agents do here | [CLAUDE.md](CLAUDE.md), which [AGENTS.md](AGENTS.md) points to |
| Run the tests | [Tests](#tests) |

The dataset isn't in this repo. Audio, `flac/`, `peaks/` and `metadata.json` are git-ignored
and stay local. The published copy is
[`ohcnetwork/scribe_dataset`](https://huggingface.co/datasets/ohcnetwork/scribe_dataset).

### Layout

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

### Prerequisites

- **ffmpeg and ffprobe** on PATH (`brew install ffmpeg`).
- **Python 3.11+**. `extract_peaks.py` uses `audioop`, which Python 3.13 removed.
- **Node 18+** for the review app.
- Whisper: `pip install -r requirements.txt` (Apple Silicon). The ~3 GB model downloads
  on the first run.

### Processing audio

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

### Tests

```bash
make test                                                   # everything offline
SCRIBE_LIVE_REPO=<you>/<test-repo> python3 test_review_live.py   # against the real Hub
```

`test_review_ui.py` drives the app in Chrome with real audio. It needs `cd app && npm ci`.
