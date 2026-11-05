// Bake metadata.json into the bundle at build/dev time so the app never fetches
// it at runtime (no per-render GCS hit). Prefers the local file (maintainer dev);
// falls back to the public bucket URL (CI/Cloudflare Pages has no local data).
import { existsSync, copyFileSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))
const out = resolve(here, '../src/data.json')
const local = resolve(here, '../../metadata.json')

if (existsSync(local)) {
  copyFileSync(local, out)
  console.log(`baked metadata from ${local}`)
} else {
  const base = process.env.PUBLIC_BASE
  if (!base) {
    console.error('no local metadata.json and PUBLIC_BASE unset — run `make pull` or set PUBLIC_BASE')
    process.exit(1)
  }
  const url = `${base.replace(/\/$/, '')}/metadata.json`
  const r = await fetch(url)
  if (!r.ok) {
    console.error(`fetch ${url} → ${r.status}`)
    process.exit(1)
  }
  writeFileSync(out, await r.text())
  console.log(`baked metadata from ${url}`)
}
