#!/usr/bin/env python3
"""Batch-transcribe the collection with Whisper large-v3, resumable.

For every clip not yet processed (no `model`), fills: `transcript_auto` (immutable
model output), `transcript` (starts equal, edited by humans in the app),
`confidence` (0..1), `no_speech_prob` (0..1), `language`, `model`; and auto-tags
`category="silence"` for empty/no-speech clips. Safe to Ctrl-C and re-run — it
writes after each clip and skips finished ones.

Backend: mlx-whisper (Apple-Silicon native, fast). On CUDA, swap the transcribe
call for faster-whisper — same loop, same fields.
    pip install mlx-whisper
Model is downloaded once from HuggingFace (~3 GB) on first run.

Audio is pre-decoded with ffmpeg to 16 kHz mono wav, capped at the known duration
so the ~7% timestamp-corrupt clips can't expand into hours of gap-filled silence.

Usage:
    python transcribe.py            # transcribe all remaining
    python transcribe.py --limit 5  # do 5 (smoke test)
"""
import argparse, json, math, os, subprocess, sys, tempfile

HERE = os.path.dirname(__file__)
AUDIO_DIR = os.path.join(HERE, "audio")
META = os.path.join(HERE, "metadata.json")
MODEL = os.environ.get("WHISPER_MODEL", "mlx-community/whisper-large-v3-mlx")
MODEL_NAME = "whisper-large-v3"
SILENCE_NSP = 0.6   # ponytail: mean no_speech_prob over this auto-tags 'silence'


def decode_16k(path, duration_sec):
    """webm/opus → 16 kHz mono wav, capped so corrupt clips stay bounded."""
    wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
    cap = (duration_sec + 2) if duration_sec else 3600
    # capture stderr instead of inheriting it: the ~7% corrupt clips spew
    # "File ended prematurely"/"Error parsing Opus packet header" but ffmpeg still
    # exits 0 and decodes fine. Only surface stderr when ffmpeg truly fails.
    p = subprocess.run(
        ["ffmpeg", "-v", "error", "-err_detect", "ignore_err", "-t", str(cap),
         "-i", path, "-ac", "1", "-ar", "16000", "-y", wav],
        capture_output=True, text=True, timeout=1200)
    if p.returncode != 0:
        tail = (p.stderr or "").strip().splitlines()
        raise RuntimeError(tail[-1] if tail else f"ffmpeg exit {p.returncode}")
    return wav


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="max clips this run (0 = all)")
    args = ap.parse_args()

    try:
        import mlx_whisper
    except ImportError:
        sys.exit("mlx-whisper not installed. Run: pip install mlx-whisper")

    doc = json.load(open(META))
    clips = doc["clips"]
    # key resumability on `model`, not `transcript`: a silent clip transcribes to
    # an empty string, which must not look "not done" and re-run every time.
    todo = [c for c in clips if not c.get("model")]
    if args.limit:
        todo = todo[:args.limit]
    print(f"{len(todo)} clip(s) to transcribe with {MODEL_NAME}", file=sys.stderr)

    done = fails = 0
    for c in todo:
        path = os.path.join(AUDIO_DIR, c["filename"])
        wav = None
        try:
            wav = decode_16k(path, c.get("duration_sec"))
            r = mlx_whisper.transcribe(wav, path_or_hf_repo=MODEL)
            text = (r.get("text") or "").strip()
            segs = r.get("segments") or []
            # Whisper can return non-finite avg_logprob/no_speech_prob on garbage
            # audio; filter them so we never emit NaN (Python json writes NaN
            # literally, which is valid to json.load but breaks browser JSON.parse).
            fin = lambda xs: [x for x in xs if isinstance(x, (int, float)) and math.isfinite(x)]
            lp = fin(s.get("avg_logprob") for s in segs)
            nsp = fin(s.get("no_speech_prob") for s in segs)
            confidence = round(math.exp(sum(lp) / len(lp)), 3) if lp else None
            no_speech = round(sum(nsp) / len(nsp), 3) if nsp else None

            c["transcript_auto"] = text
            c["transcript"] = text           # human correction starts from the auto text
            c["confidence"] = confidence
            c["no_speech_prob"] = no_speech
            c["language"] = r.get("language")
            c["model"] = MODEL_NAME
            if no_speech is not None and no_speech >= SILENCE_NSP and not text:
                c["category"] = "silence"    # auto-triage empty/no-speech clips
        except Exception as e:
            fails += 1
            print(f"  ✗ FAIL  {c['filename']}: {e}", file=sys.stderr)
            continue
        finally:
            if wav and os.path.exists(wav):
                os.remove(wav)

        done += 1
        # atomic write: a Ctrl-C mid-dump must not truncate metadata.json to junk
        tmp = META + ".tmp"
        with open(tmp, "w") as f:
            json.dump(doc, f, indent=2)
        os.replace(tmp, META)                       # write-after-each = resumable
        tag = f" [{c['category']}]" if c.get("category") == "silence" else ""
        print(f"  ✓ [{done}/{len(todo)}] {c['language']} conf={c['confidence']}"
              f"{tag} {c['filename']}: {c['transcript'][:50]!r}", file=sys.stderr)

    print(f"done: {done} transcribed, {fails} failed / {len(todo)} total", file=sys.stderr)


if __name__ == "__main__":
    main()
