# Reviewing

What you do once the app is running. To install it, see the [README](../README.md#reviewers).
The app's **Reviewer guide** has these same steps with screenshots.

## 1. Claim a batch

A batch is about 30 minutes of audio, split across a few dozen recordings, which the app
calls clips. Choose **Claim** on an available batch. Its audio then downloads to your
computer, which can take a few minutes.

| What you see | What it means | What you can do |
|---|---|---|
| Available | Nobody has it | Choose **Claim** |
| Claimed by you | You're working on it | Choose **Continue** |
| Claimed by someone else | Another reviewer has it | Pick a different batch |
| Submitted, waiting for the maintainer | You've sent it in | Choose **Open** to look at it or make a fix |
| Finished by someone | Accepted into the dataset | Nothing more to do |

## 2. Work through the clips

Choose **Start reviewing**, or **Next clip** if you've already begun. The app moves you on
each time you finish a clip. You can open any clip in the list to change it until you submit.

## 3. Review a clip

1. **Listen to the whole clip.** Use the large play button, or click the waveform to jump.
2. **Type the spoken languages.** Enter codes separated by commas, such as `ml, en`.
   Whisper's guess is often wrong. If you enter only `en`, the translation boxes disappear.
   Common codes: `ml` Malayalam, `en` English, `hi` Hindi, `ta` Tamil, `kn` Kannada,
   `te` Telugu, `bn` Bengali, `mr` Marathi.
3. **Pick a category.**

   | Category | Use it for |
   |---|---|
   | `medical-scribe` | Clinical speech, such as a consultation or dictated note |
   | `noisy-background` | Speech with a lot of noise behind it |
   | `random` | Speech that isn't clinical |
   | `music` | Mostly music |
   | `silence` | Nothing to hear |
   | `test` | Someone testing the microphone |
   | `uncategorized` | The starting value. Leave it only if nothing else fits. |

4. **Check each segment.** Long clips are cut at pauses, and each segment has a play button
   for just that part. Whisper's text is shown in grey above each box and starts off in the
   box. For each box:
   - If it's right, choose **Accept as is**.
   - If it's wrong, type your correction. It saves when you click away.
   - If there's no real speech, tick **No usable speech**. That segment then needs no text.

   A box you haven't touched doesn't count, even if Whisper's text was right. If you've been
   asked to annotate in English only, review just the Translation box.
5. **Finish the clip.** Choose **Mark reviewed** when no segments are left. If the whole clip
   has a problem, such as the wrong audio, choose **Flag clip** instead. You don't need to
   finish its segments first.

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
Whisper also sometimes invents text during silence or noise, such as "thanks for watching".
If you can't hear it in the audio, take it out.

## 4. Submit the batch

When every clip is Done or Flagged, choose **Submit batch** on the batch page. This sends
your work to the maintainer.

If the maintainer asks for a fix, choose **Open** on the batch, make the change and choose
**Submit batch** again. Your new work replaces what you sent. Once it's accepted, the batch
shows as Finished and you can claim another.

## Stopping and coming back

Your work saves as you go. Press Ctrl-C in the terminal to stop. To come back, run
`make review` from the same folder and choose **Continue**.

Your work stays on this computer until you submit, so finish a batch on the machine you
started it on, and don't delete the `review_work` folder.

## QA batches

A QA batch is a second check. It works the same way, but the boxes start with the first
reviewer's text. Check it against the audio, fix anything wrong and choose **Mark QA
complete**.

## If something goes wrong

| What you see | What to do |
|---|---|
| **Mark reviewed** is greyed out | A segment still needs a reviewed box. Look for one with **Accept as is** buttons and no green border. |
| "Use language codes such as ml or en." | Use two or three letter codes separated by commas. |
| No **Submit batch** button | A clip is still To do. Choose **Next clip** to go to it. |
| "No batches are ready yet." | Ask the maintainer when the next batches are coming, and whether your account has access. |
| "already claimed this batch" | Someone got there first. Choose another batch. |
| "Hugging Face didn't accept that token" | Create a new token with the **Write** type. |
| A clip's audio won't play | Reload the page. If it still won't play, choose **Flag clip**. |
| You can't finish a batch | Tell the maintainer, who can release it for someone else. |
