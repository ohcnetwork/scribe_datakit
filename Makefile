# Local dataset tasks. audio/, peaks/ and metadata.json are git-ignored.
HF_REPO ?= ohcnetwork/scribe_dataset

.PHONY: link apply-corrections hf-export

# Serve local audio and peaks through the dev server.
link:
	@ln -sfn ../../audio app/public/audio
	@ln -sfn ../../peaks app/public/peaks
	@echo "linked app/public/{audio,peaks}"

# Apply contributor corrections onto local metadata.json, then review the diff.
apply-corrections:
	python3 merge_corrections.py
	@echo "merged: review the diff, then re-export with: make hf-export"

# Export the corpus as a HuggingFace audiofolder dataset in hf/ (needs local audio).
# Push it with the `hf` CLI, see docs/huggingface.md.
hf-export:
	python3 hf_export.py
	@echo "→ push:  cd hf && hf upload $(HF_REPO) . --repo-type=dataset"
