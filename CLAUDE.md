# Scribe dataset

Speech dataset tooling. See README.md for the maintainer view and design_spec.md for the
data model. `generated_*` is machine text and `final_*` is human text: never copy one into
the other.

## Setting up the review app for a reviewer

When someone asks you to set up or run the review app, do this from the repo root.

1. Check the tools: `python3 --version` (3.11 or newer), `node --version` (18 or newer), `make --version`.
   If one is missing, offer to install it, using Homebrew on a Mac. On Windows, use WSL.
2. Run `make setup`. This creates `.venv/` and installs the app dependencies. Reviewers don't
   need ffmpeg, Whisper or the `audio/` folder.
3. Start it in the background with `make review`. It serves http://127.0.0.1:4321 and opens the
   browser. If that port is taken, run `.venv/bin/python review_server.py --port 4322`.
4. Tell them to connect Hugging Face in the app, and walk them through "Connect Hugging Face"
   in docs/reviewing.md. **The token goes in the app, never in this chat.** Don't read,
   print or store it.
5. Point them to docs/reviewing.md for how to review.

If batches won't load, check `.venv/bin/python -c "from huggingface_hub import HfApi; print(HfApi().whoami()['name'])"`.
A 401 or 404 from Hugging Face usually means their account hasn't been given access to
`ohcnetwork/scribe_dataset`, so ask them to contact the maintainer. Never work around that.

Reviewers' unsent work is in `review_work/`. Never delete that folder.
