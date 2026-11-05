// Prefix for dataset assets (audio, peaks, dataset.zip). Empty in dev → served
// from the local app/public symlinks; set to the public bucket URL via
// VITE_ASSET_BASE in production so the browser fetches them from GCS/Cloudflare.
// Metadata is NOT routed through here — it's baked into the bundle at build time.
export const asset = (path) => (import.meta.env.VITE_ASSET_BASE || '') + path
