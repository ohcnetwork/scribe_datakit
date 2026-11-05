import { createContext, useContext, useEffect, useMemo, useRef, useState } from 'react'
import doc from './data.json'   // metadata baked into the bundle at build time (scripts/bake-metadata.mjs)

// The site is static and credential-free: base facts are baked in at build time
// (no runtime metadata fetch, no GCS hit per render); audio/peaks come from the
// public bucket via asset(). User edits (final text / languages / status) live in
// localStorage, merged on top, then exported as a corrections file to submit as a PR.
const LS_KEY = 'scribe-edits-v2'
const OLD_LS_KEY = 'scribe-edits-v1'
const EXPECTED_SCHEMA = 2   // keep in sync with build_metadata.SCHEMA_VERSION
const Ctx = createContext(null)

if (doc.schema_version !== EXPECTED_SCHEMA)
  console.warn(`metadata schema_version ${doc.schema_version} != expected ${EXPECTED_SCHEMA} — fields may be missing`)

// v1 edits are converted, not dropped: they may be unexported work. The v1 key is
// left in place as a safety copy.
const OLD_STATUS = { unverified: 'pending', verified: 'reviewed', flagged: 'flagged' }
export function convertV1Edits(old) {
  return Object.fromEntries(Object.entries(old).map(([id, { transcript, status, ...rest }]) => {
    const e = { ...rest }
    if (transcript !== undefined) e.final_transcript = transcript
    if (status) e.status = OLD_STATUS[status] || 'pending'
    return [id, e]
  }))
}

function loadEdits() {
  try {
    const cur = localStorage.getItem(LS_KEY)
    if (cur) return JSON.parse(cur) || {}
    return convertV1Edits(JSON.parse(localStorage.getItem(OLD_LS_KEY)) || {})
  } catch { return {} }
}

export function StoreProvider({ children }) {
  const [edits, setEdits] = useState(loadEdits)
  const [toast, setToast] = useState(null)
  const toastTimer = useRef(null)
  function showToast(msg) {
    clearTimeout(toastTimer.current)
    setToast(msg)
    toastTimer.current = setTimeout(() => setToast(null), 2600)
  }

  useEffect(() => { localStorage.setItem(LS_KEY, JSON.stringify(edits)) }, [edits])

  // merge base clip + local edit (edit wins on the user fields)
  const clips = useMemo(() =>
    doc.clips.map((c) => ({ ...c, ...(edits[c.id] || {}) })), [edits])

  function editClip(id, patch) {
    setEdits((e) => ({ ...e, [id]: { ...(e[id] || {}), ...patch } }))
  }

  // export only what the user actually changed, as a mergeable corrections file
  function exportCorrections() {
    const out = Object.entries(edits).map(([id, patch]) => ({ id, ...patch }))
    const blob = new Blob([JSON.stringify({ corrections: out }, null, 2)],
      { type: 'application/json' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = 'corrections.json'
    a.click()
    URL.revokeObjectURL(a.href)
  }

  const value = {
    clips, doc,
    editCount: Object.keys(edits).length,
    editClip, exportCorrections,
    clearEdits: () => setEdits({}),
    toast, showToast,
  }
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export const useStore = () => useContext(Ctx)

// --- shared helpers -------------------------------------------------------
export const CATEGORIES = [
  'uncategorized', 'medical-scribe', 'random', 'noisy-background',
  'music', 'silence', 'test',
]
// stored status values, in workflow order. `final` is maintainer-only: merge_corrections
// drops it from contributor files unless run with --allow-final.
export const STATUSES = ['pending', 'reviewed', 'qa_complete', 'final', 'flagged']
export const NEEDS_TEXT = ['reviewed', 'qa_complete', 'final']
export const LOCKED = ['qa_complete', 'final']

// Display workflow: the stored status, except `pending` splits on whether a machine
// draft exists, so "never transcribed" and "draft awaiting review" read differently.
export const WORKFLOW = {
  untranscribed: { label: 'Untranscribed', cls: 'untranscribed', dot: 'var(--status-unverified)' },
  'needs-review': { label: 'Needs review', cls: 'needs-review', dot: 'var(--status-review)' },
  reviewed: { label: 'Reviewed', cls: 'reviewed', dot: 'var(--status-reviewed)' },
  qa_complete: { label: 'QA complete', cls: 'qa-complete', dot: 'var(--status-qa)' },
  final: { label: 'Final', cls: 'final', dot: 'var(--status-final)' },
  flagged: { label: 'Flagged', cls: 'flagged', dot: 'var(--status-flagged)' },
}
export const WORKFLOW_ORDER = ['untranscribed', 'needs-review', 'reviewed', 'qa_complete', 'final', 'flagged']
export function workflowState(c) {
  if (c.status !== 'pending') return c.status
  return c.generated_transcript || c.final_transcript ? 'needs-review' : 'untranscribed'
}

// human-confirmed languages win over Whisper's guess
export const clipLangs = (c) => c.spoken_languages?.length ? c.spoken_languages
  : c.whisper_language ? [c.whisper_language] : []
export const primaryLang = (c) => clipLangs(c)[0] || null
export const isEnglishOnly = (langs) => langs.length === 1 && langs[0] === 'en'
// reviewed text when there is one, else the machine draft. Display only: exports keep them apart.
export const shownTranscript = (c) => c.final_transcript ?? c.generated_transcript ?? ''
export const shownTranslation = (c) => c.final_translation ?? c.generated_translation ?? ''

export function fmtDur(s) {
  if (s == null) return '—'
  const m = Math.floor(s / 60), sec = Math.round(s % 60)
  return m ? `${m}:${String(sec).padStart(2, '0')}` : `${sec}s`
}
export const fmtSize = (b) => b > 1e6 ? `${(b / 1e6).toFixed(1)} MB` : `${Math.round(b / 1e3)} KB`

// aggregate/group duration → compact label (h / min / s)
export function fmtTotalDur(sec) {
  if (!sec) return '0s'
  if (sec >= 3600) return `${(sec / 3600).toFixed(1)} h`
  if (sec >= 60) return `${Math.round(sec / 60)} min`
  return `${Math.round(sec)}s`
}
export const fmtSampleRate = (sr) => sr ? `${(sr / 1000).toFixed(sr % 1000 ? 1 : 0)} kHz` : '—'

// right-to-left scripts, for dir= on transcript text
const RTL = new Set(['ar', 'he', 'fa', 'ur', 'ps', 'sd'])
export const dirFor = (lang) => RTL.has((lang || '').toLowerCase()) ? 'rtl' : 'ltr'

// human-readable language name via the platform (no hardcoded map); falls back
// to the raw code for anything Intl doesn't recognise.
const langDisplay = typeof Intl !== 'undefined' && Intl.DisplayNames
  ? new Intl.DisplayNames(['en'], { type: 'language' }) : null
export function langName(code) {
  if (!code) return 'Unknown'
  try { return langDisplay?.of(code) || code } catch { return code }
}
