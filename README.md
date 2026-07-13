# Scribe Audio Collection

Open, browsable collection of 601 scribing audio clips (~9.7 h). Browse, play,
transcribe/correct, categorise, and download.

See [`design_spec.md`](design_spec.md) for the data model and page design.

## Layout

| Path | What |
|---|---|
| `audio/` | the 601 source clips (webm/opus, 48 kHz mono) |
| `metadata.json` | one record per clip — the app's data + the metadata dump |
| `build_metadata.py` | incremental ffprobe scan → `metadata.json` (all derivable fields + corruption flag) |
| `transcribe.py` | batch Whisper large-v3 → transcript (+auto), language, confidence, resumable |
| `extract_peaks.py` | ffmpeg → `peaks/<id>.json` per clip, for the app's waveform |
| `make_release.sh` | zip `audio/` + `metadata.json` → `app/public/dataset.zip` |
| `test_metadata.py` | regression check for the duration/corruption logic |
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
cd app && npm install
npm run dev          # dev server, http://localhost:5173
npm run serve        # build + preview the production bundle on the LAN (0.0.0.0:4173)
npm run preview      # preview an existing build on the LAN (0.0.0.0:4173)
npm run dev:host     # dev server exposed on the LAN
```
`app/public/` symlinks `metadata.json`, `audio/`, and `peaks/` from the repo root;
`vite build` copies them into `dist/`, so `serve`/`preview` expose the whole
dataset over the network. The `--host` builds print a `Network:` URL to open from
another device.

## (Re)build metadata

```bash
python3 build_metadata.py           # incremental: probes only new files
python3 build_metadata.py --force   # re-derive every file (after logic changes)
python3 test_metadata.py            # regression check
```
**Incremental by default** — ffmpeg touches each file once, ever. A clip already
in `metadata.json` is reused untouched; only new files (or ones missing a derived
field) are probed, so adding audio and re-running is near-instant. User edits
(transcript, language, model, status, category) are always preserved. Derives
container, codec, sample rate, channels, channel layout, bitrate, duration,
corruption flag, recorded-at, and container tags.

## Transcribe

```bash
pip install -r requirements.txt   # Apple Silicon (mlx-whisper); ~3 GB model on first run
python3 transcribe.py             # or --limit N to smoke-test
```
Writes after each clip, so it's Ctrl-C-safe and resumable. Fills `transcript_auto`
(immutable model output), `transcript` (human-editable copy), `confidence`,
`no_speech_prob`, `language`, `model`, and auto-tags silent clips `category=silence`.
On CUDA, swap the transcribe call for faster-whisper (same loop).

## Waveform peaks

```bash
python3 extract_peaks.py          # incremental; --force to redo all
```
Precomputes ~800 amplitude peaks per clip into `peaks/<id>.json` (symlinked into
`app/public/`). The app renders the waveform from these — no in-browser decode.
Optional: without peaks, the player falls back to a plain `<audio>` element.

## Contributions

Edit transcripts/categories/status in the app → **Export** → merge the
`corrections.json` back into `metadata.json`. The site is static; there is no
server.

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
