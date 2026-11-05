#!/usr/bin/env python3
"""Run Whisper large-v3 over every segment, both tasks, resumable.

Per segment fills `generated_transcript` (task=transcribe) and `generated_translation`
(task=translate, X→English), plus `whisper_language`, `confidence` and `no_speech_prob`.
Never writes `final_*`: those hold human-reviewed text only. Run segment_audio.py first.

Translation runs on everything with speech, including clips Whisper calls English,
because its language guess is unreliable. Only human-confirmed English is skipped.

Safe to Ctrl-C and re-run: it writes after each clip and skips finished segments.
Backend: mlx-whisper (Apple Silicon). On CUDA, swap whisper_run for faster-whisper.

    python transcribe.py            # all remaining
    python transcribe.py --limit 5  # 5 clips (smoke test)
"""
import argparse, collections, json, math, os, subprocess, sys, time

HERE = os.path.dirname(__file__)
FLAC_DIR = os.path.join(HERE, "flac")
META = os.path.join(HERE, "metadata.json")
MODEL = os.environ.get("WHISPER_MODEL", "mlx-community/whisper-large-v3-mlx")
MODEL_NAME = "whisper-large-v3"
SR = 16000
SILENCE_NSP = 0.6   # ponytail: mean no_speech_prob over this auto-tags 'silence'


def confirmed_english(c):
    return c.get("spoken_languages") == ["en"]


def needs_transcript(s):
    return s["generated_transcript"] is None


def needs_translation(c, s):
    """Has speech, not translated yet, and not confirmed English by a person."""
    return s["generated_translation"] is None and bool(s["generated_transcript"]) \
        and not confirmed_english(c)


def source_language(c):
    """Language token when a person confirmed one, else None so Whisper detects it."""
    return next((l for l in c.get("spoken_languages") or [] if l != "en"), None)


def majority_language(segments):
    """The language covering the most audio, by Whisper's per-segment guess."""
    t = collections.Counter()
    for s in segments:
        if s["whisper_language"] and s["generated_transcript"]:
            t[s["whisper_language"]] += s["end"] - s["start"]
    return t.most_common(1)[0][0] if t else None


def is_silent(segments):
    nsp = [s["no_speech_prob"] for s in segments if s["no_speech_prob"] is not None]
    return bool(nsp) and not any(s["generated_transcript"] for s in segments) \
        and sum(nsp) / len(nsp) >= SILENCE_NSP


def load_audio(clip_id):
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", os.path.join(FLAC_DIR, f"{clip_id}.flac"),
                          "-f", "s16le", "-ac", "1", "-ar", str(SR), "-"],
                         capture_output=True, check=True, timeout=600).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0


def stats(r):
    """Mean confidence and no-speech probability; Whisper can emit NaN on garbage audio."""
    fin = lambda xs: [x for x in xs if isinstance(x, (int, float)) and math.isfinite(x)]
    segs = r.get("segments") or []
    lp = fin(s.get("avg_logprob") for s in segs)
    nsp = fin(s.get("no_speech_prob") for s in segs)
    return (round(math.exp(sum(lp) / len(lp)), 3) if lp else None,
            round(sum(nsp) / len(nsp), 3) if nsp else None)


def process(c, whisper_run):
    audio = load_audio(c["id"])
    for s in c["segments"]:
        chunk = audio[int(s["start"] * SR):int(s["end"] * SR)]
        if needs_transcript(s):
            r = whisper_run(chunk, task="transcribe", language=source_language(c))
            s["generated_transcript"] = (r.get("text") or "").strip()
            s["whisper_language"] = r.get("language")
            s["confidence"], s["no_speech_prob"] = stats(r)
        if needs_translation(c, s):
            r = whisper_run(chunk, task="translate",
                            language=source_language(c) or s["whisper_language"])
            s["generated_translation"] = (r.get("text") or "").strip()
    c["model"] = MODEL_NAME
    c["whisper_language"] = majority_language(c["segments"])
    if is_silent(c["segments"]):
        c["category"] = "silence"


def save(doc):
    # atomic write: a Ctrl-C mid-dump must not truncate metadata.json to junk
    tmp = META + ".tmp"
    with open(tmp, "w") as f:
        json.dump(doc, f, indent=2)
    os.replace(tmp, META)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="max clips this run (0 = all)")
    args = ap.parse_args()
    try:
        import mlx_whisper
    except ImportError:
        sys.exit("mlx-whisper not installed. Run: pip install -r requirements.txt")

    with open(META) as f:
        doc = json.load(f)
    if doc.get("schema_version") != 2:
        sys.exit("metadata.json is not schema v2; run migrate_schema_v2.py first")
    todo = [c for c in doc["clips"]
            if any(needs_transcript(s) or needs_translation(c, s) for s in c["segments"])]
    if args.limit:
        todo = todo[:args.limit]
    print(f"{len(todo)} clip(s) to process with {MODEL_NAME}", file=sys.stderr)

    def whisper_run(chunk, **kw):
        return mlx_whisper.transcribe(chunk, path_or_hf_repo=MODEL, **kw)

    done = fails = audio_sec = 0
    began = time.time()
    for c in todo:
        try:
            process(c, whisper_run)
        except Exception as e:
            fails += 1
            print(f"  ✗ FAIL  {c['id']}: {e}", file=sys.stderr)
            continue
        save(doc)
        done += 1
        audio_sec += c["duration_sec"] or 0
        print(f"  ✓ [{done}/{len(todo)}] {c['id'][:8]} {c['whisper_language']} "
              f"{len(c['segments'])} seg, {audio_sec / (time.time() - began):.2f}x realtime",
              file=sys.stderr, flush=True)
    print(f"done: {done} processed, {fails} failed / {len(todo)} total", file=sys.stderr)


if __name__ == "__main__":
    main()
