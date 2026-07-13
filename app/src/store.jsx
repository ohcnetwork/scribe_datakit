import { createContext, useContext, useEffect, useMemo, useRef, useState } from 'react'

// The site is static: no server. Base facts come from /metadata.json; user edits
// (transcript / status / category) live in localStorage and are merged on top,
// then exported as a corrections file to be merged back upstream.
const LS_KEY = 'scribe-edits-v1'
const EXPECTED_SCHEMA = 1   // keep in sync with build_metadata.SCHEMA_VERSION
const Ctx = createContext(null)

function loadEdits() {
  try { return JSON.parse(localStorage.getItem(LS_KEY)) || {} } catch { return {} }
}

export function StoreProvider({ children }) {
  const [base, setBase] = useState(null)
  const [edits, setEdits] = useState(loadEdits)
  const [error, setError] = useState(null)
  const [toast, setToast] = useState(null)
  const toastTimer = useRef(null)
  function showToast(msg) {
    clearTimeout(toastTimer.current)
    setToast(msg)
    toastTimer.current = setTimeout(() => setToast(null), 2600)
  }

  useEffect(() => {
    fetch('/metadata.json')
      .then((r) => { if (!r.ok) throw new Error(`metadata.json ${r.status}`); return r.json() })
      .then((d) => {
        if (d.schema_version !== EXPECTED_SCHEMA)
          console.warn(`metadata.json schema_version ${d.schema_version} != expected ${EXPECTED_SCHEMA} — fields may be missing`)
        setBase(d)
      })
      .catch((e) => setError(e.message))
  }, [])

  useEffect(() => { localStorage.setItem(LS_KEY, JSON.stringify(edits)) }, [edits])

  // merge base clip + local edit (edit wins on the three user fields)
  const clips = useMemo(() => {
    if (!base) return []
    return base.clips.map((c) => ({ ...c, ...(edits[c.id] || {}) }))
  }, [base, edits])

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
    clips, doc: base, error,
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
export const STATUSES = ['unverified', 'verified', 'flagged']

// Derived 4-state workflow. The raw `status` field only records human
// verification; this folds in whether a machine transcript exists yet, so
// "never transcribed" and "auto-draft awaiting review" no longer both read as
// "unverified". Human status (verified/flagged) always wins; otherwise the
// presence of a transcript decides untranscribed vs needs-review.
export const WORKFLOW = {
  untranscribed: { label: 'Untranscribed', cls: 'untranscribed', dot: 'var(--status-unverified)' },
  'needs-review': { label: 'Needs review', cls: 'needs-review', dot: 'var(--status-review)' },
  verified: { label: 'Verified', cls: 'verified', dot: 'var(--status-verified)' },
  flagged: { label: 'Flagged', cls: 'flagged', dot: 'var(--status-flagged)' },
}
export const WORKFLOW_ORDER = ['untranscribed', 'needs-review', 'verified', 'flagged']
export function workflowState(c) {
  if (c.status === 'verified') return 'verified'
  if (c.status === 'flagged') return 'flagged'
  return c.transcript ? 'needs-review' : 'untranscribed'
}

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
