# Reviewers only need `make review`. The rest is for the maintainer.
HF_REPO ?= ohcnetwork/scribe_dataset

.PHONY: setup review test ingest hf-export

# One-time setup: Python and Node dependencies.
setup:
	python3 -m venv .venv
	.venv/bin/pip install --quiet -r requirements-review.txt
	cd app && npm ci --silent

# Build the app and open it. Your work is kept in review_work/.
review:
	@test -d .venv || $(MAKE) setup
	cd app && npm run --silent build
	.venv/bin/python review_server.py

test:
	@for t in test_*.py; do echo "== $$t"; python3 $$t || exit 1; done

# Run new files in audio/ through the pipeline. See docs/ingesting-a-collection.md.
ingest:
	@test -n "$(COLLECTION)" || { echo "usage: make ingest COLLECTION=<name>"; exit 1; }
	python3 build_metadata.py --collection $(COLLECTION)
	python3 segment_audio.py
	python3 extract_peaks.py
	python3 transcribe.py
	python3 test_metadata.py

# Export the corpus as a HuggingFace dataset in hf/. See docs/huggingface.md.
hf-export:
	python3 hf_export.py
	@echo "→ push:  cd hf && hf upload $(HF_REPO) . --repo-type=dataset"
