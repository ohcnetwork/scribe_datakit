# Scribe Audio Collection

Open, browsable collection of 601 scribing audio clips (~6.9 h). Browse, play,
transcribe/correct, categorise, and download.

See [`design_spec.md`](design_spec.md) for the data model and page design.

**The dataset is not in this repo.** Audio, `metadata.json`, and `peaks/` live on a
public GCS bucket (git-ignored locally); the repo holds only code. See
[Data & GCS](#data--gcs) for the layout and how to sync it.

## Layout

| Path | What |
|---|---|
| `audio/` | the 601 source clips (webm/opus, 48 kHz mono) — **on the bucket, git-ignored** |
| `metadata.json` | one record per clip — the app's data — **on the bucket, git-ignored** |
| `peaks/` | precomputed waveform peaks — **on the bucket, git-ignored** |
| `build_metadata.py` | incremental ffprobe scan → `metadata.json` (all derivable fields + corruption flag) |
| `transcribe.py` | batch Whisper large-v3 → transcript (+auto), language, confidence, resumable |
| `extract_peaks.py` | ffmpeg → `peaks/<id>.json` per clip, for the app's waveform |
| `make_release.sh` | zip `audio/` + `metadata.json` → `app/public/dataset.zip` |
| `merge_corrections.py` | apply `corrections/*.json` onto `metadata.json` |
| `hf_export.py` | corpus → HuggingFace `audiofolder` dataset in `hf/` (see [docs/huggingface.md](docs/huggingface.md)) |
| `corrections/` | contributor correction files, submitted as PRs (the only dataset data in git) |
| `Makefile` | `pull` / `push` / `release` / `apply-corrections` — sync the dataset with the bucket |
| `.env.example` | bucket config (`GCS_BUCKET`, `PUBLIC_BASE`) — copy to `.env` |
| `test_metadata.py`, `test_merge_corrections.py` | regression checks |
| `requirements.txt` | Python deps for `transcribe.py` |
| `app/` | React (Vite) browser UI |

## Prerequisites

- **ffmpeg + ffprobe** on PATH — required by `build_metadata.py` and `transcribe.py`
  (`brew install ffmpeg`).
- **Python 3** (3.11+).
- **Node 18+** for the app.
- **gcloud CLI** — only for syncing the dataset with the bucket (`make pull/push`).
  Authenticate once: `gcloud auth application-default login`. Not needed to just
  build or run the app.
- Transcription downloads the **~3 GB Whisper large-v3 model** from HuggingFace on
  the first `transcribe.py` run (not at install time), so the first clip is slow.

## Run the app

```bash
cp .env.example .env      # set GCS_BUCKET / PUBLIC_BASE
make pull                 # fetch the dataset + link app/public/{audio,peaks} (needs gcloud auth)
cd app && npm install
npm run dev               # dev server, http://localhost:5173
npm run serve             # build + preview the production bundle on the LAN (0.0.0.0:4173)
npm run dev:host          # dev server exposed on the LAN
```
Every `dev`/`build` first runs `npm run bake`, which writes `src/data.json` — the
metadata **baked into the bundle** so the app never fetches it at runtime. It uses
the local `metadata.json` if present (after `make pull`), else fetches `PUBLIC_BASE/metadata.json`.

In dev the asset base is empty, so `audio/` and `peaks/` are served from the
`app/public/` symlinks (`make pull` creates them) — fully local and offline. In a
production build, set `VITE_ASSET_BASE` to the public bucket URL and the app
fetches audio/peaks from there instead. See [Deploy](#deploy).

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
Precomputes ~800 amplitude peaks per clip into `peaks/<id>.json`. The app renders
the waveform from these — no in-browser decode. Optional: without peaks, the player
falls back to a plain `<audio>` element. `peaks/` is part of the dataset (bucket),
served locally in dev via the `app/public/peaks` symlink from `make pull`.

## Contributions

The site is static and has no server, so corrections travel through git:

1. Edit transcripts/categories/status in the app → **Contribute / Export** →
   `corrections.json`.
2. Add it to the repo as `corrections/<your-handle>.json` and open a PR (see
   [`corrections/README.md`](corrections/README.md)). This is the only dataset
   data that lives in git.
3. A maintainer runs `make apply-corrections` (merges onto `metadata.json`),
   reviews the diff, then `make push` to publish — and clears the merged files.

## Data & GCS

The repo is code-only. The dataset (`audio/`, `metadata.json`, `peaks/`,
`dataset.zip`) lives on a **public GCS bucket**, fronted by Cloudflare for
edge-caching and egress-free delivery. **No credentials exist at runtime or in
CI** — the app and the build only read the bucket over public HTTPS. Bucket
*writes* use your local gcloud auth and happen only via the make targets:

```bash
make setup-bucket      # one-time, idempotent: create bucket + public read + CORS
make pull              # bucket → local audio/ peaks/ metadata.json + dev symlinks
make push              # local → bucket, then stamp Cache-Control headers
make release           # build dataset.zip and push it
make apply-corrections # apply corrections/*.json onto local metadata.json
make hf-export         # corpus → HuggingFace dataset in hf/ (push with the hf CLI)
```

Config lives in `.env` (`GCS_BUCKET` for push/pull, `PUBLIC_BASE` for the public
read URL). `make push`/`pull` fail early with a clear message if `gcloud` isn't
authenticated.

**Cost.** Audio/peaks are content-addressed and pushed with
`Cache-Control: immutable, max-age=1y`, so Cloudflare serves repeat plays from the
edge and GCS egress stays near zero (Bandwidth Alliance waives GCS→Cloudflare
egress). `metadata.json` gets a short TTL since it changes. Set a GCP budget alert
as a backstop.

## Deploy

- **App** → Cloudflare Pages. Build command `cd app && npm install && npm run build`,
  output `app/dist`. Set env `VITE_ASSET_BASE` and `PUBLIC_BASE` both to the public
  bucket URL (e.g. `https://data.example.com`). The build bakes `metadata.json` from
  `PUBLIC_BASE` and points audio/peaks at `VITE_ASSET_BASE`.
- **Data** → a GCS bucket (single-region, Standard class, `allUsers:objectViewer`,
  a CORS rule so the app can `fetch` peaks), with a Cloudflare-proxied custom domain
  and a "Cache Everything" rule. Full walkthrough: **[docs/gcs-setup.md](docs/gcs-setup.md)**.
  Publish/update with `make push` / `make release`.

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
