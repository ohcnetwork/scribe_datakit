# Maintaining reviews

This is how recordings reach reviewers and how their work comes back. For bringing in new
audio, see [ingesting-a-collection.md](ingesting-a-collection.md). For what reviewers do,
see [reviewing.md](reviewing.md).

`metadata.json` on your machine is the source of truth. The Hugging Face repo is the only
place you and reviewers share, and it's regenerated from `metadata.json`.

## How batches work

A batch is a set of whole recordings that one person reviews, about 30 minutes of audio.
A recording is never split across batches, even though its text is on segments.

Each batch is one JSON file, `review/batches/<name>.json`, named
`<collection>-<kind>-<number>`, such as `scribe-staging-review-0001`. It holds a snapshot
of its recordings and their segments, including Whisper's text. Audio isn't in the file.
The app downloads it from `recordings/<collection>/` when someone claims the batch.

There are two kinds:

| Kind | Picks up recordings at | Finishing a recording makes it |
|---|---|---|
| `review` | `pending` | `reviewed` or `flagged` |
| `qa` | `reviewed` | `qa_complete` or `flagged` |

## Create batches

```bash
python3 review_admin.py batches --collection scribe-staging --minutes 30
make hf-export
cd hf && hf upload ohcnetwork/scribe_dataset . --repo-type=dataset
```

`batches` works through the collection, oldest recording first. It adds recordings to a
batch until it reaches the target length, then starts the next one. That means:

- Most batches run a little over the target, and one long recording can add more. The last
  batch is whatever is left, so it can be short. `scribe-staging` currently makes 14
  batches: 13 of 30 to 36 minutes and a last one of 8.5 minutes.
- Recordings with no segments, and any categorised as `silence`, are left out.
- A recording already in a batch of that kind isn't handed out again, so it's safe to run
  this again after ingesting more audio. Numbering carries on from the last batch.

Batches appear to reviewers only after you upload them.

Run `batches` on the machine that holds `hf/review/batches/`, and don't delete those files.
It reads them to see what's been handed out, so without them it would hand out the same
recordings again. It doesn't check the Hugging Face repo.

Run Whisper before creating batches, because the batch keeps the text it was made with.

## How a claim works

A claim is a draft pull request on the dataset repo, titled `[claim] <batch name>`. The app
opens it when a reviewer chooses **Claim**, so there's nothing for you to do.

1. The app checks that nobody holds a live claim on the batch.
2. It opens the draft PR, then checks again. If two people claimed at the same moment, the
   lowest PR number wins and the other person's PR is closed.
3. It downloads the batch, its audio and its waveforms to `review_work/` on the reviewer's
   computer.

Reviewers then work offline, and nothing reaches Hugging Face until they submit. Claiming
the same batch again resumes it, and local work is never overwritten.

Each batch shows one of these states, worked out from its oldest PR that isn't closed:

| In the app | PR state | Meaning |
|---|---|---|
| Available | no PR, or all closed | Anyone can claim it |
| Claimed by you, or by someone else | draft | Being reviewed |
| Submitted | open | Waiting for you to merge |
| Done | merged | Finished |

## Submit and merge

**Submit batch** works only when every recording is finished. The app commits
`review/submissions/<batch>.json` to the claim PR and publishes the draft. A reviewer can
submit again, and the new file replaces the old one on the same PR.

Add each reviewer's Hugging Face username to `reviewers.txt`, one per line. Then run:

```bash
python3 review_admin.py merge
make hf-export
cd hf && hf upload ohcnetwork/scribe_dataset . --repo-type=dataset
```

`merge` treats every submission as untrusted:

- PRs from anyone not in `reviewers.txt` are skipped and stay open.
- Only text, languages, category and the `excluded` tick are applied. Whisper's text can't
  change.
- A submission can't set `final` or change a `final` recording.
- A `reviewed` or `qa_complete` recording must have human text on every usable segment.

If a submission has no problems, its PR is merged. If any recording has a problem, the
report names it, the valid recordings are still applied and the PR stays open. Ask the
reviewer to fix it and submit again, then run `merge` again.

`merge` only changes your `metadata.json`, so the dataset shows the new text only after you
export and upload.

## QA and finalising

QA is optional. A QA batch contains only `reviewed` recordings and starts from the first
reviewer's text:

```bash
python3 review_admin.py batches --collection scribe-staging --kind qa
# export and upload, as above. Merge works the same way.
python3 review_admin.py finalize --collection scribe-staging
```

To skip QA, add `--include-reviewed` to `finalize`. Only `finalize` can set `final`.
`flagged` recordings stay out of QA and out of `final` until you've looked at them.

## Common jobs

| Job | What to do |
|---|---|
| Someone abandons a batch | Close its PR on Hugging Face. The batch becomes available again. Their unsent work stays on their computer. |
| A batch was claimed by mistake | Same as above. |
| See what's outstanding | Open the repo's Pull requests tab. Draft means in progress, open means ready to merge. |
| Add a reviewer | Give their account access to the repo and add them to `reviewers.txt`. |
