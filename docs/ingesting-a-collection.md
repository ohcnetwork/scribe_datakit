# Ingesting a collection

A collection is a named set of recordings. This takes new audio from your computer to
batches reviewers can claim. You need the tools under Prerequisites in the
[README](../README.md#prerequisites).

## 1. Add the audio

Copy the files straight into `audio/`, with no subfolders. Accepted formats are `.webm`,
`.mp4`, `.ogg`, `.mp3`, `.wav` and `.m4a`.

## 2. Run the pipeline

```bash
make ingest COLLECTION=my-collection
```

Use lowercase letters, numbers and hyphens in the name, because it becomes a folder and a
dataset config on Hugging Face. It's set when a file is first seen, so a later run with
another name won't move existing recordings.

This adds the files to `metadata.json`, cuts them into segments, draws waveforms, runs
Whisper and checks the result. Whisper takes about 35 minutes per hour of audio on an M4
Pro. It's safe to stop with Ctrl-C and run again, and it only processes what's left.

If you know who is speaking, set `speaker_id` on those recordings in `metadata.json`. It
stays null otherwise, and later runs keep it.

## 3. Publish batches

```bash
python3 review_admin.py batches --collection my-collection --minutes 30
make hf-export
cd hf && hf upload ohcnetwork/scribe_dataset . --repo-type=dataset \
  --delete "data/*" --delete "recordings/*" --delete "review/peaks/*"
```

Reviewers now see the new batches. From here, follow
[maintaining.md](maintaining.md).
