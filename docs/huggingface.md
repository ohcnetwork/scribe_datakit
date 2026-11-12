# Publishing to HuggingFace

The corpus is published as a derived artifact. `metadata.json` stays the single source of
truth; the HF dataset is regenerated from it, never edited in place. Reviews arrive as PRs
on the same repo (see [maintaining.md](maintaining.md)).

## Export

```bash
make hf-export    # needs flac/ and peaks/ locally
```

Output follows the Hub's folder conventions, so it needs no loading script. Each
`metadata.jsonl` sits beside its audio with a `file_name` column:

```
hf/
├── README.md                     dataset card; the YAML defines the subsets
├── data/<collection>/train/
│   ├── metadata.jsonl            one row per segment
│   └── <id>_s003.flac            16 kHz mono, 28 s or less
├── recordings/<collection>/
│   ├── metadata.jsonl            one row per recording
│   └── <id>.flac                 16 kHz mono
└── review/
    ├── batches/*.json            written by review_admin.py
    └── peaks/<id>.json           waveforms for the review app
```

**Subsets.** `all` (default) is every segment, there's one per collection, and `recordings`
holds the full recordings. `review/` isn't part of any subset.

**The audio and metadata always match.** The export deletes audio no row lists and stops if
a row has no audio. Existing segments are kept; `--force` re-cuts them.

### Row schema

`generated_*` is **always machine text** and `final_*` is **always human-reviewed**; there is
no fallback between them. English-only audio has no translation, so use `final_transcript` as
its English text. Train on `status == "final"` rows.

### Flags

```bash
python3 hf_export.py --min-status final     # segment rows at this status or later
python3 hf_export.py --force                # re-cut every segment
python3 hf_export.py --license cc0-1.0      # dataset card license (default cc-by-4.0)
```

Full recordings always ship, because reviewers need them.

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
hf upload ohcnetwork/scribe_dataset . --repo-type=dataset \
  --delete "data/*" --delete "recordings/*" --delete "review/peaks/*"
```

The CLI content-hashes files, so re-uploads only transfer what changed. There's no
`push` or `pull`: `hf upload` is the push and `hf download` the pull. (`hf sync` works only
with buckets, not dataset repos.)

`hf upload` adds and replaces files but never removes them, while `make hf-export` removes
the files that no longer belong from `hf/`. Each `--delete` pattern removes the remote files
it matches that aren't in the upload, in the same commit, and `*` also matches subfolders.
Only the folders the export owns are listed. Don't use `--delete "*"`: it would also remove
`review/submissions/`, which reaches the repo through merged pull requests, and any
`review/batches/` file that isn't on this computer.

`hf/` isn't tracked by git. On a new computer, download the batch files before you create
batches, because `review_admin.py batches` reads `hf/review/batches/` to avoid putting a
clip in two batches:

```bash
hf download ohcnetwork/scribe_dataset --repo-type=dataset --include "review/batches/*" --local-dir hf
```

The target repo is `HF_ORG/HF_DATASET` from `.env`, which the review app and
`review_admin.py` read too; a variable set in the shell wins. `make hf-export` prints the exact push command.

## Consuming it

```python
from datasets import load_dataset

ds = load_dataset("ohcnetwork/scribe_dataset", split="train")
ds[0]["audio"]          # {'array': …, 'sampling_rate': 16000}
ds[0]["final_translation"]

gold = ds.filter(lambda r: r["status"] == "final")
```
