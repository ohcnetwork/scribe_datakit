import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// public/{audio,peaks} symlink to the repo root (created by `make link`) so
// /audio/<file> and /peaks/<id>.json serve local data. Metadata is baked into the
// bundle (scripts/bake-metadata.mjs), not served from public/.
export default defineConfig({
  plugins: [react()],
  server: { fs: { allow: ['..', '../..'] } },
  // `npm run serve` builds then serves dist/ on 0.0.0.0 for LAN access.
  // allowedHosts: true lets it answer to any hostname (LAN IP or *.local).
  preview: { host: true, port: 4173, allowedHosts: true },
})
