// Bake metadata.json into the bundle at build/dev time so the app never fetches it
// at runtime.
import { existsSync, copyFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))
const out = resolve(here, '../src/data.json')
const local = resolve(here, '../../metadata.json')

if (!existsSync(local)) {
  console.error(`no ${local}: the app needs the local dataset`)
  process.exit(1)
}
copyFileSync(local, out)
console.log(`baked metadata from ${local}`)
