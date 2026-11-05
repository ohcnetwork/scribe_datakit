# Setting up the public bucket

One-time setup for the GCS bucket + Cloudflare that host the dataset. After this,
day-to-day publishing is just `make push` / `make release`.

Everything on the GCP side (bucket, IAM, CORS, budget) is `gcloud`, and most of it
is wrapped in `make setup-bucket`. The two steps that aren't: **Cloudflare** — a
different vendor, use its own dashboard or API — and the **domain-ownership
verification**, a one-time manual check (avoidable, see
[Skip the domain-named bucket](#skip-the-domain-named-bucket)).

---

# Quick setup (Makefile)

## 0. Authenticate

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
gcloud auth application-default login   # what the make targets use
```

## 1. Configure `.env`

The bucket is named after the domain you'll serve it on — that's what lets
Cloudflare route to it by Host.

```bash
cp .env.example .env
```

```ini
GCS_BUCKET=gs://data.example.com     # bucket name == the public domain
PUBLIC_BASE=https://data.example.com # public read URL
REGION=us-central1                   # single region = cheapest storage/egress
CORS_ORIGIN=*                        # or https://app.example.com
```

## 2. Create + configure the bucket

```bash
make setup-bucket
```

Creates the bucket (single-region, Standard class, uniform access), makes it
publicly readable, and sets the CORS policy. **Idempotent** — safe to re-run, and
it *repairs* an existing misconfigured bucket (see
[Already created the bucket?](#already-created-the-bucket-but-its-misconfigured)).

> If the bucket name is a domain, GCS requires you to **verify domain ownership**
> once in [Google Search Console](https://search.google.com/search-console) for the
> account creating it. `gcloud` will tell you if it's missing.

## 3. Put Cloudflare in front — *manual, not gcloud*

This is what keeps egress bills near zero: Cloudflare caches at the edge, and the
Google Cloud ↔ Cloudflare [Bandwidth Alliance](https://www.cloudflare.com/bandwidth-alliance/)
waives GCS→Cloudflare egress. Nothing to configure for the Alliance — it applies
automatically.

In the Cloudflare dashboard for your zone:

1. **DNS** → add `CNAME  data  →  c.storage.googleapis.com`, **Proxied** (orange
   cloud). GCS routes to the right bucket because the bucket is named for the domain.
2. **Rules → Caching** → add a Cache Rule: *When* hostname equals `data.example.com`,
   *Then* Cache eligibility = **Eligible for cache** ("Cache Everything"), Edge TTL =
   **Respect origin** (objects already carry `Cache-Control` from `make push`).
3. Leave SSL/TLS at **Full**.

## 4. Publish the data

```bash
make push        # audio/ peaks/ metadata.json  (+ cache headers)
make release     # dataset.zip
```

## 5. Verify

```bash
# Public read works, and the cache header is set:
curl -sI https://data.example.com/metadata.json | grep -i 'cache-control\|HTTP/'

# CORS header comes back for a cross-origin GET:
curl -sI -H 'Origin: https://app.example.com' https://data.example.com/metadata.json \
  | grep -i 'access-control-allow-origin'

# Served through Cloudflare:
curl -sI https://data.example.com/metadata.json | grep -i 'cf-cache-status\|^server'
```

## 6. Cost backstop

A public bucket can in theory be scraped. Cloudflare caching makes that cheap, but
add a budget alert as a safety net:

```bash
gcloud services enable billingbudgets.googleapis.com
BILLING=$(gcloud billing projects describe YOUR_PROJECT_ID \
  --format='value(billingAccountName)')          # billingAccounts/XXXXXX-XXXXXX-XXXXXX

gcloud billing budgets create \
  --billing-account=${BILLING#billingAccounts/} \
  --display-name="scribe-data" \
  --budget-amount=20USD \
  --filter-projects=projects/YOUR_PROJECT_ID \
  --threshold-rule=percent=0.5 \
  --threshold-rule=percent=0.9 \
  --threshold-rule=percent=1.0
```

It emails at 50/90/100% of the amount. It notifies; it doesn't cap.

Done. The app (Cloudflare Pages) needs `VITE_ASSET_BASE` and `PUBLIC_BASE` both set
to `https://data.example.com` — see the [Deploy](../README.md#deploy) section.

---

# Manual setup (reference)

What `make setup-bucket` runs, if you'd rather do it by hand or tweak one piece.

```bash
export DOMAIN=data.example.com
export BUCKET=gs://$DOMAIN
export REGION=us-central1
```

## Create the bucket

Single-region + Standard storage class is cheapest for content that's served (no
retrieval fees, low operation cost). Uniform bucket-level access keeps permissions
simple.

```bash
gcloud storage buckets create $BUCKET --location=$REGION

gcloud storage buckets update $BUCKET \
  --uniform-bucket-level-access \
  --no-public-access-prevention \
  --default-storage-class=STANDARD
```

## Make it publicly readable

```bash
gcloud storage buckets add-iam-policy-binding $BUCKET \
  --member=allUsers \
  --role=roles/storage.objectViewer
```

Anything under the bucket is now world-readable over HTTPS. Writes still require
your credentials — that's the whole security model: **read = public, write = you**.

> Run this *after* clearing public-access-prevention above, or GCS rejects the
> binding. New buckets ship with prevention enforced, so order matters.

## Allow the app to fetch peaks (CORS)

Audio plays through a plain `<audio>` element and needs no CORS. But the app
fetches `peaks/<id>.json` with `fetch()` from a **different origin** (the app on
Cloudflare Pages, the data on `$DOMAIN`), so the bucket must send CORS headers or
those requests fail:

```bash
cat > cors.json <<'EOF'
[
  {
    "origin": ["*"],
    "method": ["GET", "HEAD"],
    "responseHeader": ["Content-Type", "Range"],
    "maxAgeSeconds": 3600
  }
]
EOF
gcloud storage buckets update $BUCKET --cors-file=cors.json
```

`"origin": ["*"]` is fine for an open dataset; restrict it to your app's origin
(`https://app.example.com`) if you'd rather.

---

# Already created the bucket, but it's misconfigured?

Just run `make setup-bucket` against it. It reconciles rather than skips — on an
existing bucket it will:

| Fixes | How |
|---|---|
| Public access prevention = *enforced* (blocks public read) | `--no-public-access-prevention` |
| Uniform bucket-level access off | `--uniform-bucket-level-access` |
| Wrong default storage class | `--default-storage-class=STANDARD` |
| Not publicly readable | re-adds the `allUsers:objectViewer` binding |
| Missing/wrong CORS | rewrites the CORS policy from `CORS_ORIGIN` |

The order matters and the target gets it right: access prevention is cleared
*before* the public-read binding, which GCS would otherwise reject.

**What it can't fix:**

- **Location.** Immutable. The target warns if the bucket's region differs from
  `REGION`. To change it, create a new bucket and copy:
  `gcloud storage cp -r gs://old/* gs://new/`.
- **Existing objects' storage class.** `--default-storage-class` only applies to
  *new* objects. To convert what's already there:
  `gcloud storage objects update "$BUCKET/**" --storage-class=STANDARD`.
- **Existing objects' cache headers.** Not a problem — `make push` re-stamps
  `Cache-Control` on every object each run.

# Skip the domain-named bucket

The domain verification exists only because a domain-named bucket
(`data.example.com`) lets GCS route by Host. If you'd rather not verify a domain,
name the bucket anything (e.g. `gs://scribe-data`) and let Cloudflare rewrite the
path instead — no GCS-side manual step, but it moves one bit of config to Cloudflare:

1. **DNS** → `CNAME  data  →  storage.googleapis.com`, Proxied.
2. **Rules → Transform Rules → Rewrite URL** → *When* hostname = `data.example.com`,
   *Then* rewrite path to `/scribe-data$1` (regex `(.*)` → `/scribe-data/$1`). This
   turns `data.example.com/audio/x.webm` into an origin fetch of
   `storage.googleapis.com/scribe-data/audio/x.webm`.
3. Everything else is unchanged; set `GCS_BUCKET=gs://scribe-data`,
   `PUBLIC_BASE=https://data.example.com`.

Trade-off: no domain verification, but the routing lives in a Cloudflare rule
instead of the bucket name. Either works.
