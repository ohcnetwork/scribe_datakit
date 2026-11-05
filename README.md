# Scribe Audio Collection

Open, browsable collection of 601 scribing audio clips (~6.9 h). Browse, play,
transcribe/correct, categorise, and download.

See [`design_spec.md`](design_spec.md) for the data model and page design.

**The dataset is not in this repo.** Audio, `metadata.json`, and `peaks/` are
git-ignored and live locally; the repo holds only code. The dataset is published to
[`ohcnetwork/scribe_dataset`](https://huggingface.co/datasets/ohcnetwork/scribe_dataset).

## Layout

| Path | What |
|---|---|
| `audio/` | the 601 source clips (webm/opus, 48 kHz mono) — **git-ignored** |
| `metadata.json` | one record per clip — the app's data — **git-ignored** |
| `peaks/` | precomputed waveform peaks — **git-ignored** |
| `build_metadata.py` | incremental ffprobe scan → `metadata.json` (all derivable fields + corruption flag) |
| `transcribe.py` | batch Whisper large-v3 → generated transcript and translation, language, confidence, resumable |
| `extract_peaks.py` | ffmpeg → `peaks/<id>.json` per clip, for the app's waveform |
| `merge_corrections.py` | apply `corrections/*.json` onto `metadata.json`, enforcing the status rules |
| `migrate_schema_v2.py` | one-off: migrate `metadata.json` from schema v1 to v2 (keeps a `metadata.v1.json` backup) |
| `hf_export.py` | corpus → HuggingFace `audiofolder` dataset in `hf/` (see [docs/huggingface.md](docs/huggingface.md)) |
| `corrections/` | contributor correction files, submitted as PRs (the only dataset data in git) |
| `Makefile` | `link` / `apply-corrections` / `hf-export` |
| `test_*.py` | regression checks |
| `requirements.txt` | Python deps for `transcribe.py` |
| `app/` | React (Vite) browser UI |

## Prerequisites

- **ffmpeg + ffprobe** on PATH — required by `build_metadata.py` and `transcribe.py`
  (`brew install ffmpeg`).
- **Python 3** (3.11+).
- **Node 18+** for the app.
- Transcription downloads the **~3 GB Whisper large-v3 model** from HuggingFace on
  the first `transcribe.py` run (not at install time), so the first clip is slow.

## Run the app

```bash
make link                 # link app/public/{audio,peaks} to the local dataset
cd app && npm install
npm run dev               # dev server, http://localhost:5173
npm run serve             # build + preview the production bundle on the LAN (0.0.0.0:4173)
npm run dev:host          # dev server exposed on the LAN
```
Every `dev`/`build` first runs `npm run bake`, which writes `src/data.json` — the
metadata **baked into the bundle** so the app never fetches it at runtime.
`audio/` and `peaks/` are served from the `app/public/` symlinks, fully local and offline.

## (Re)build metadata

```bash
python3 build_metadata.py           # incremental: probes only new files
python3 build_metadata.py --force   # re-derive every file (after logic changes)
python3 test_metadata.py            # regression check
```
**Incremental by default** — ffmpeg touches each file once, ever. A clip already
in `metadata.json` is reused untouched; only new files (or ones missing a derived
field) are probed, so adding audio and re-running is near-instant. User edits
(final text, spoken languages, status, category, collection) are always preserved.
New clips go into the collection named by `--collection` (default `scribe-staging`). Derives
container, codec, sample rate, channels, channel layout, bitrate, duration,
corruption flag, recorded-at, and container tags.

## Transcribe

```bash
pip install -r requirements.txt   # Apple Silicon (mlx-whisper); ~3 GB model on first run
python3 transcribe.py             # or --limit N to smoke-test
python3 transcribe.py --translate # English translations, after transcribing
```
Writes after each clip, so it's Ctrl-C-safe and resumable. Fills `generated_transcript`
(immutable model output), `confidence`, `no_speech_prob`, `whisper_language`, `model`,
and auto-tags silent clips `category=silence`. `--translate` fills
`generated_translation` for clips with speech, skipping English-only audio. It uses
`spoken_languages` when set, otherwise Whisper's guess, so re-run it after a reviewer
corrects a clip that was wrongly detected as English. Neither pass writes `final_*`.
On CUDA, swap the transcribe call for faster-whisper (same loop).

## Waveform peaks

```bash
python3 extract_peaks.py          # incremental; --force to redo all
```
Precomputes ~800 amplitude peaks per clip into `peaks/<id>.json`. The app renders
the waveform from these — no in-browser decode. Optional: without peaks, the player
falls back to a plain `<audio>` element. `peaks/` is served through the
`app/public/peaks` symlink from `make link`.

## Contributions

The site is static and has no server, so corrections travel through git:

1. Review clips in the app → **Contribute / Export** → `corrections.json`.
2. Add it to the repo as `corrections/<your-handle>.json` and open a PR (see
   [`corrections/README.md`](corrections/README.md)). This is the only dataset
   data that lives in git.
3. A maintainer runs `make apply-corrections` (merges onto `metadata.json`),
   reviews the diff, re-exports with `make hf-export`, and clears the merged files.

Only a maintainer can approve a clip for training: `status: final` is dropped unless
`python3 merge_corrections.py --allow-final <your-file>.json` is used. Never pass that
flag for contributor files.

## Waveform note

The source webm files carry no duration header and the browser can't
`decodeAudioData` them, so wavesurfer can't decode/seek in-browser. We sidestep
that with `extract_peaks.py`: peaks are precomputed offline and the player feeds
wavesurfer `{ peaks, duration }` while playing through a native `<audio>` element
(which decodes these files fine). Clips without a peaks file degrade to a plain
`<audio>` player.

## Known deferrals

- **`extract_peaks.py` uses stdlib `audioop`** (C-speed) — fine on Python 3.11,
  but `audioop` is **removed in Python 3.13**. On 3.13+, swap it for a strided
  pure-Python scan or numpy (see the `ponytail:` note at the import). Run
  `/ponytail-debt` to list all such deferred shortcuts.
