# Data model

`metadata.json` is the source of truth: `{schema_version: 2, clips: [...]}`, one record
per recording. Recordings stay whole; their text lives on segments, which are time ranges
inside the recording. That keeps context for reviewers while each segment fits Whisper's
30 second training window.

## Recording

| Field | Source | Notes |
|---|---|---|
| `id`, `filename`, `format`, `container`, `codec`, `codec_long`, `size_bytes`, `sample_rate`, `channels`, `channel_layout`, `bitrate_kbps`, `recorded_at`, `tags` | derived | from ffprobe |
| `duration_sec` | derived | sum of the audio packet durations |
| `corrupt` | derived | broken container timestamps; the audio itself is usable |
| `collection` | set on arrival | which batch of source data the recording came from |
| `whisper_language` | model | Whisper's guess by audio covered; unreliable |
| `spoken_languages` | reviewer | confirmed list, e.g. `["ml", "en"]`; null until confirmed, and wins over the guess |
| `model` | model | e.g. `whisper-large-v3` |
| `status` | workflow | see below |
| `category` | reviewer | `medical-scribe`, `random`, `noisy-background`, `music`, `silence`, `test`, `uncategorized` |
| `reviewed_by`, `qa_by` | workflow | Hugging Face usernames, from the PR author |
| `segments` | see below | |

## Segment

| Field | Source | Notes |
|---|---|---|
| `index`, `start`, `end` | derived | seconds; segments join up with no gaps |
| `generated_transcript` | model | Whisper `transcribe`; never edited |
| `generated_translation` | model | Whisper `translate`; never edited |
| `final_transcript` | reviewer | null until a person edits or accepts it |
| `final_translation` | reviewer | null until a person edits or accepts it |
| `excluded` | reviewer | no usable speech, so it needs no text |
| `whisper_language`, `confidence`, `no_speech_prob` | model | `confidence` is a poor filter: bad text can score high |

`generated_*` is always machine text and `final_*` is always human-reviewed. Nothing falls
back from one to the other. A box the reviewer leaves untouched stays null, so annotating
in English alone never saves the machine transcript as human text.

English-only audio needs no translation: its English text is `final_transcript`.

## Status

One status per recording.

| Status | Meaning | Set by |
|---|---|---|
| `pending` | no human review is complete | default |
| `reviewed` | every usable segment has human text | reviewer |
| `qa_complete` | a second person checked it | QA reviewer |
| `final` | approved for training | maintainer only |
| `flagged` | has a problem and needs a decision; excluded from training | reviewer |

The flow is `pending → reviewed → qa_complete → final`. QA is optional, because reviewer
numbers vary: `finalize --include-reviewed` skips it. A PR can't set `final` or change a
`final` clip.
