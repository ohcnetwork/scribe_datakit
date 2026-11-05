import { createContext, useContext, useRef, useState } from 'react'

// All data comes from the local review server (review_server.py); nothing is baked in.
export async function api(path, method = 'GET', body) {
  const r = await fetch(`/api${path}`, {
    method,
    headers: body === undefined && method === 'GET' ? {} : { 'Content-Type': 'application/json' },
    body: method === 'GET' ? undefined : JSON.stringify(body ?? {}),
  })
  const data = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error(data.error || 'Something went wrong. Try again.')
  return data
}

const Ctx = createContext(null)

export function ToastProvider({ children }) {
  const [toast, setToast] = useState(null)
  const timer = useRef(null)
  function showToast(msg) {
    clearTimeout(timer.current)
    setToast(msg)
    timer.current = setTimeout(() => setToast(null), 3200)
  }
  return <Ctx.Provider value={{ toast, showToast }}>{children}</Ctx.Provider>
}

export const useToast = () => useContext(Ctx)

export const CATEGORIES = [
  'uncategorized', 'medical-scribe', 'random', 'noisy-background',
  'music', 'silence', 'test',
]

// human-confirmed languages win over Whisper's guess
export const clipLangs = (c) => c.spoken_languages?.length ? c.spoken_languages
  : c.whisper_language ? [c.whisper_language] : []
export const isEnglishOnly = (langs) => langs.length === 1 && langs[0] === 'en'
export const segmentDone = (s) => s.excluded || !!(s.final_transcript?.trim() || s.final_translation?.trim())

export function fmtDur(s) {
  if (s == null) return '—'
  const m = Math.floor(s / 60), sec = Math.round(s % 60)
  return m ? `${m}:${String(sec).padStart(2, '0')}` : `${sec}s`
}

// right-to-left scripts, for dir= on transcript text
const RTL = new Set(['ar', 'he', 'fa', 'ur', 'ps', 'sd'])
export const dirFor = (lang) => RTL.has((lang || '').toLowerCase()) ? 'rtl' : 'ltr'
