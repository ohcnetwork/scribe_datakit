# Corrections

Drop your exported `corrections.json` here (rename it to something unique, e.g.
`corrections/alice.json`) and open a PR. This directory is the **only** dataset
data that lives in git — the audio and `metadata.json` are on the bucket.

Flow:
1. In the app, review clips → **Contribute / Export** → `corrections.json`.
2. Add it here as `corrections/<your-handle>.json` and open a PR.
3. A maintainer runs `make apply-corrections` (merges onto `metadata.json`) then
   `make push`, and clears the merged files.

File shape (what the app exports):

```json
{ "corrections": [ { "id": "…", "final_translation": "…", "spoken_languages": ["ml", "en"], "status": "reviewed" } ] }
```

Only `final_transcript`, `final_translation`, `spoken_languages`, `status`, and
`category` are applied; everything else is ignored. `status: final` is dropped unless a
maintainer merges with `--allow-final`, and changing text on a `qa_complete` or `final`
clip moves it back to `reviewed`.
