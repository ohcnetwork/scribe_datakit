# Reviewing

You listen to clinical recordings and correct the text Whisper produced. Everything runs
on your own computer, and your work goes back through your Hugging Face account.

Once the app is open, **Reviewer guide** in its sidebar has these steps, plus the whole
process from recording to release.

## Set up

You need [Git](https://git-scm.com/downloads), Python 3.11 or newer,
[Node 18 or newer](https://nodejs.org), and a free
[Hugging Face account](https://huggingface.co/join) that the maintainer has added.

```bash
git clone <this repo>
cd scribe_dump
make review
```

The first run takes a few minutes. The app then opens in your browser. Next time, run
`make review` again from the same folder. Press Ctrl-C in the terminal to stop it.

**Using Claude Code?** Open it in this folder and ask it to set up the review app.
[`CLAUDE.md`](../CLAUDE.md) tells it what to do.

Windows: run these in [WSL](https://learn.microsoft.com/windows/wsl/install), which has `make`.

## Connect Hugging Face

The first time, the app asks for an access token:

1. Open [your access tokens](https://huggingface.co/settings/tokens) and choose **Create new token**.
2. Choose the **Write** type and give it any name.
3. Paste it into the app. It's stored on your computer only. Don't share it with anyone.

## Review a batch

A batch is about 30 minutes of audio.

1. **Claim a batch.** Others then see it's taken. Its audio downloads to your computer.
2. **Open a clip.** The waveform plays the whole recording. Each segment has its own play
   button that plays just that part.
3. **Check the languages.** Type what's really spoken, such as `ml, en`. Whisper's guess
   is often wrong. Translation boxes disappear for English-only audio.
4. **Review each segment.** Listen, then fix the text. If it's already right, use
   **Accept as is**. A box you don't touch isn't counted as reviewed.
5. **Mark reviewed.** This needs at least one reviewed box per segment. If you're
   annotating in English only, you can leave the transcript boxes alone. The app takes you
   to the next clip.
6. **Submit the batch** when every clip is done. This sends your work to the maintainer.

Your work saves after each box, so you can stop and come back. It stays on this computer
until you submit, so finish a batch on the machine you started it on.

If a segment has no real speech, tick **No usable speech**. If a whole clip has a problem,
such as the wrong audio, use **Flag clip**.

## How to write the text

- **Transcript:** write what was said, in the language it was said. Leave out "um" and
  false starts unless they change the meaning.
- **English terms inside Malayalam or Hindi speech:** keep them in English letters, such as
  `patient` or `paracetamol`.
- **Translation:** translate what was said. Don't summarise, tidy up or add anything.
- **Numbers, units and doses:** write them exactly as spoken. Listen again if unsure. Take
  extra care with doses, left and right, and negation ("no fever"), because one wrong word
  changes the clinical meaning.
- **Can't make out a word:** write `[unclear]`. Don't guess.

Whisper's translation can read fluently and still be wrong, so check it against the audio.

## QA

A QA batch works the same way, but starts from the first reviewer's text. Check it against
the audio, fix anything wrong and choose **Mark QA complete**.

## If something goes wrong

| Problem | What to do |
|---|---|
| "Hugging Face didn't accept that token" | Create a new token with the **Write** type. |
| The batch list is empty or won't load | Ask the maintainer to confirm your account has access. |
| "already claimed this batch" | Someone got there first. Choose another batch. |
| You can't finish a batch | Tell the maintainer, who can release it for someone else. |
