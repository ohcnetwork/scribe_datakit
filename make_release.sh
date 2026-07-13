#!/usr/bin/env bash
# Build the single downloadable dataset archive the app links at /dataset.zip.
# Not committed (see .gitignore) — regenerate whenever audio/ or metadata.json change.
set -euo pipefail
cd "$(dirname "$0")"
out="app/public/dataset.zip"
rm -f "$out"
zip -r -q "$out" audio metadata.json
echo "wrote $out ($(du -h "$out" | cut -f1))"
