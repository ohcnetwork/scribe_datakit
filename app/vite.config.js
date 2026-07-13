import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// public/ symlinks metadata.json and audio/ to the repo root, so /metadata.json
// and /audio/<file> are served as-is in dev and copied on build.
export default defineConfig({
  plugins: [react()],
  server: { fs: { allow: ['..', '../..'] } },
  // `npm run serve` builds then serves dist/ on 0.0.0.0 for LAN access.
  // allowedHosts: true lets it answer to any hostname (LAN IP or *.local).
  preview: { host: true, port: 4173, allowedHosts: true },
})
