# Dataset lives on a GCS bucket, not in git. These targets sync it.
#
# Writes (push/release) need LOCAL gcloud auth — run once:
#     gcloud auth application-default login
# Reads at runtime/CI use the public bucket over HTTPS — no credentials, ever.
#
# Config comes from .env (copy .env.example):
#     GCS_BUCKET   gs://...    push/pull target
#     PUBLIC_BASE  https://... public read URL (Cloudflare-fronted)

ifneq (,$(wildcard .env))
include .env
export
endif

IMMUTABLE := public,max-age=31536000,immutable
SHORT     := public,max-age=300
REGION      ?= us-central1
CORS_ORIGIN ?= *
HF_REPO     ?= gigincg/scribe_dataset

.PHONY: setup-bucket pull push release apply-corrections hf-export check-auth check-bucket

# Provision the bucket: create if absent, then reconcile settings to the desired
# state — so it also REPAIRS a bucket that already exists but is misconfigured
# (access prevention, uniform access, storage class, public read, CORS).
# Idempotent; picks up REGION / CORS_ORIGIN from .env. Location is the one thing
# it can't fix (immutable) — it warns instead. Cloudflare and domain verification
# are separate (see docs/gcs-setup.md).
setup-bucket: check-auth
	@gcloud storage buckets describe $(GCS_BUCKET) >/dev/null 2>&1 \
		&& echo "bucket $(GCS_BUCKET) exists — reconciling settings" \
		|| gcloud storage buckets create $(GCS_BUCKET) --location=$(REGION)
	@loc=$$(gcloud storage buckets describe $(GCS_BUCKET) --format='value(location)' | tr 'A-Z' 'a-z'); \
		test "$$loc" = "$(REGION)" || echo "WARNING: bucket is in '$$loc', not '$(REGION)' — location is immutable; recreate the bucket to change it"
	@printf '[{"origin":["%s"],"method":["GET","HEAD"],"responseHeader":["Content-Type","Range"],"maxAgeSeconds":3600}]\n' '$(CORS_ORIGIN)' > /tmp/scribe-cors.json
	gcloud storage buckets update $(GCS_BUCKET) \
		--uniform-bucket-level-access \
		--no-public-access-prevention \
		--default-storage-class=STANDARD \
		--cors-file=/tmp/scribe-cors.json
	gcloud storage buckets add-iam-policy-binding $(GCS_BUCKET) \
		--member=allUsers --role=roles/storage.objectViewer >/dev/null
	@echo "bucket ready: public read + CORS origin '$(CORS_ORIGIN)'"

check-bucket:
	@test -n "$(GCS_BUCKET)" || { echo "GCS_BUCKET unset — copy .env.example to .env"; exit 1; }

check-auth: check-bucket
	@gcloud auth application-default print-access-token >/dev/null 2>&1 || \
		{ echo "not authenticated — run: gcloud auth application-default login"; exit 1; }

# Fetch the dataset locally and wire the dev symlinks the app serves from.
pull: check-auth
	@mkdir -p audio peaks
	gcloud storage rsync -r $(GCS_BUCKET)/audio audio
	gcloud storage rsync -r $(GCS_BUCKET)/peaks peaks
	gcloud storage cp $(GCS_BUCKET)/metadata.json metadata.json
	@ln -sfn ../../audio app/public/audio
	@ln -sfn ../../peaks app/public/peaks
	@echo "pulled dataset; linked app/public/{audio,peaks}"

# Push local dataset to the bucket, then stamp cache headers (audio/peaks are
# content-addressed and never change → immutable; metadata is short-lived).
# ponytail: re-stamps every object each push; scope to new files if it gets slow.
push: check-auth
	gcloud storage rsync -r audio $(GCS_BUCKET)/audio
	gcloud storage rsync -r peaks $(GCS_BUCKET)/peaks
	gcloud storage cp metadata.json $(GCS_BUCKET)/metadata.json
	gcloud storage objects update "$(GCS_BUCKET)/audio/**" "$(GCS_BUCKET)/peaks/**" --cache-control="$(IMMUTABLE)"
	gcloud storage objects update "$(GCS_BUCKET)/metadata.json" --cache-control="$(SHORT)"
	@echo "pushed dataset to $(GCS_BUCKET)"

# Build the downloadable archive and push it to the bucket.
release: check-auth
	./make_release.sh
	gcloud storage cp app/public/dataset.zip $(GCS_BUCKET)/dataset.zip
	gcloud storage objects update "$(GCS_BUCKET)/dataset.zip" --cache-control="$(SHORT)"
	@echo "released dataset.zip to $(GCS_BUCKET)"

# Apply contributor corrections onto local metadata.json (then review + make push).
apply-corrections:
	python3 merge_corrections.py
	@echo "merged — review the diff, then: make push"

# Export the corpus as a HuggingFace audiofolder dataset in hf/ (needs local audio:
# run `make pull` first). Push it with the `hf` CLI — see docs/huggingface.md.
hf-export:
	python3 hf_export.py
	@echo "→ push:  cd hf && hf upload $(HF_REPO) . --repo-type=dataset"
