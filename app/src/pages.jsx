import { useMemo, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import {
  Search, Globe, X, Play, ChevronRight, ChevronLeft, SearchX, ArrowRight,
  Package, FileAudio, Braces, PencilLine, Download, Check, Tag,
} from 'lucide-react'
import Player from './Player'
import { Button, Input, StatusBadge } from './ui'
import { useStore, CATEGORIES, fmtDur, fmtSize, fmtSampleRate, fmtTotalDur, dirFor, langName, WORKFLOW, WORKFLOW_ORDER, workflowState } from './store'

const audioSrc = (c) => `/audio/${c.filename}`
const shortId = (id) => id.slice(0, 8)

// group clips by a key → { count, dur } (single pass)
function groupStats(clips, keyOf) {
  const m = new Map()
  for (const c of clips) {
    const k = keyOf(c); if (k == null) continue
    const e = m.get(k) || { count: 0, dur: 0 }
    e.count++; e.dur += c.duration_sec || 0; m.set(k, e)
  }
  return m
}

// ============ BROWSE ============
export function CollectionList() {
  const { clips } = useStore()
  const nav = useNavigate()
  const [sp] = useSearchParams()
  const fLang = sp.get('language') || ''
  const fStatus = sp.get('status') || ''
  const fCat = sp.get('category') || ''
  const [q, setQ] = useState('')

  const rows = useMemo(() => {
    const t = q.trim().toLowerCase()
    return clips.filter((c) =>
      (!fLang || c.language === fLang) &&
      (!fStatus || workflowState(c) === fStatus) &&
      (!fCat || c.category === fCat) &&
      (!t || c.id.toLowerCase().includes(t) ||
        (c.transcript || '').toLowerCase().includes(t) ||
        (c.language || '').toLowerCase().includes(t)))
      .sort((a, b) => (b.recorded_at || '').localeCompare(a.recorded_at || ''))
  }, [clips, q, fLang, fStatus, fCat])

  const hasFilter = fLang || fStatus || fCat || q
  const clearAll = () => { setQ(''); nav('/') }

  if (!clips.length) return <div className="page" style={{ maxWidth: 1160 }}><p>Loading…</p></div>
  return (
    <div className="page" style={{ maxWidth: 1160 }}>
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 16, marginBottom: 20 }}>
        <div>
          <h1 className="title">Browse collection</h1>
          <p className="subtitle">Showing {rows.length.toLocaleString()} of {clips.length.toLocaleString()} clips</p>
        </div>
        <Input icon={Search} placeholder="Search transcript, id or language…" value={q}
          onChange={(e) => setQ(e.target.value)} style={{ width: 340 }} />
      </div>

      {hasFilter && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 12, color: 'var(--muted-foreground)', fontWeight: 500 }}>Filters</span>
          {fLang && <span className="chip"><Globe size={13} strokeWidth={1.75} />{fLang}</span>}
          {fStatus && <span className="chip">{WORKFLOW[fStatus]?.label || fStatus}</span>}
          {fCat && <span className="chip"><Tag size={13} strokeWidth={1.75} />{fCat}</span>}
          <button className="chip-btn" onClick={clearAll}><X size={13} strokeWidth={1.75} />Clear</button>
        </div>
      )}

      <div className="card" style={{ overflow: 'hidden' }}>
        <div className="tbl-head">
          <span /><span>Transcript</span><span>Language</span><span>Length</span><span>Status</span><span />
        </div>
        {rows.map((c) => (
          <div key={c.id} className="tbl-row" onClick={() => nav(`/clip/${c.id}`)}>
            <button className="playbtn" title="Open" onClick={(e) => { e.stopPropagation(); nav(`/clip/${c.id}`) }}>
              <Play size={13} strokeWidth={1.75} />
            </button>
            <div style={{ minWidth: 0 }}>
              <div className="snippet" dir={dirFor(c.language)} title={c.transcript || ''}>
                {c.transcript || <span style={{ color: 'var(--muted-foreground)' }}>— not transcribed —</span>}
              </div>
              <div className="rowid">{shortId(c.id)}{c.corrupt ? ' · corrupt' : ''}</div>
            </div>
            <span><span className="chip sm">{c.language || '—'}</span></span>
            <span className="mono" style={{ fontSize: 13 }}>{fmtDur(c.duration_sec)}</span>
            <span><StatusBadge clip={c} /></span>
            <ChevronRight size={16} strokeWidth={1.75} style={{ color: 'oklch(0.72 0 0)' }} />
          </div>
        ))}
        {!rows.length && (
          <div className="empty">
            <SearchX size={26} strokeWidth={1.75} />
            <p style={{ margin: '10px 0 14px' }}>No clips match your filters.</p>
            <Button variant="outline" onClick={clearAll}>Clear filters</Button>
          </div>
        )}
      </div>
    </div>
  )
}

// ============ CATEGORIES ============
export function CategoryBrowse() {
  const { clips } = useStore()
  const nav = useNavigate()

  const languages = useMemo(() =>
    [...groupStats(clips, (c) => c.language || null)].sort((a, b) => b[1].count - a[1].count), [clips])
  const catStats = useMemo(() => groupStats(clips, (c) => c.category), [clips])
  const statusStats = useMemo(() => groupStats(clips, (c) => workflowState(c)), [clips])
  const cats = CATEGORIES.map((k) => [k, catStats.get(k)]).filter(([, s]) => s?.count)

  return (
    <div className="page" style={{ maxWidth: 1000 }}>
      <h1 className="title">Browse by category</h1>
      <p className="subtitle">Filter the collection by language, content category, or verification status.</p>

      <h2 className="section-label">Language</h2>
      {languages.length ? (
        <div className="cat-grid">
          {languages.map(([code, s]) => (
            <div key={code} className="card cat-card" onClick={() => nav(`/?language=${encodeURIComponent(code)}`)}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Globe size={18} strokeWidth={1.75} style={{ color: 'var(--muted-foreground)' }} />
                <ArrowRight size={15} strokeWidth={1.75} style={{ color: 'oklch(0.75 0 0)' }} />
              </div>
              <div className="cat-num">{s.count}</div>
              <div style={{ fontSize: 14, fontWeight: 500, marginTop: 4 }}>
                {langName(code)} <span style={{ color: 'var(--muted-foreground)', fontWeight: 400 }}>({code})</span>
              </div>
              <div style={{ fontSize: 12, color: 'var(--muted-foreground)' }}>clips ({fmtTotalDur(s.dur)})</div>
            </div>
          ))}
        </div>
      ) : <p className="subtitle" style={{ margin: 0 }}>No languages yet — run transcription to detect them.</p>}

      <h2 className="section-label">Content category</h2>
      <div className="st-grid">
        {cats.map(([k, s]) => (
          <div key={k} className="card cat-card" style={{ display: 'flex', alignItems: 'center', gap: 14 }}
            onClick={() => nav(`/?category=${encodeURIComponent(k)}`)}>
            <Tag size={17} strokeWidth={1.75} style={{ color: 'var(--muted-foreground)', flexShrink: 0 }} />
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 14, fontWeight: 500 }}>{k}</div>
              <div style={{ fontSize: 12, color: 'var(--muted-foreground)' }}>{s.count} clips ({fmtTotalDur(s.dur)})</div>
            </div>
            <ArrowRight size={15} strokeWidth={1.75} style={{ color: 'oklch(0.75 0 0)' }} />
          </div>
        ))}
      </div>

      <h2 className="section-label">Workflow status</h2>
      <div className="st-grid">
        {WORKFLOW_ORDER.map((k) => {
          const s = statusStats.get(k) || { count: 0, dur: 0 }
          return (
          <div key={k} className="card cat-card" style={{ display: 'flex', alignItems: 'center', gap: 14 }}
            onClick={() => nav(`/?status=${k}`)}>
            <span style={{ width: 10, height: 10, borderRadius: '50%', background: WORKFLOW[k].dot, flexShrink: 0 }} />
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 14, fontWeight: 500 }}>{WORKFLOW[k].label}</div>
              <div style={{ fontSize: 12, color: 'var(--muted-foreground)' }}>{s.count} clips ({fmtTotalDur(s.dur)})</div>
            </div>
            <ArrowRight size={15} strokeWidth={1.75} style={{ color: 'oklch(0.75 0 0)' }} />
          </div>
          )
        })}
      </div>
    </div>
  )
}

// ============ DOWNLOAD ============
export function DatasetDownload() {
  const { clips, doc, showToast } = useStore()
  if (!doc) return <div className="page" style={{ maxWidth: 940 }}><p>Loading…</p></div>
  const hours = doc.total_duration_sec / 3600
  const totalDur = hours >= 1 ? `${hours.toFixed(1)} h` : `${Math.round(doc.total_duration_sec / 60)} min`
  const langCount = new Set(clips.map((c) => c.language).filter(Boolean)).size
  const verifiedPct = Math.round(clips.filter((c) => c.status === 'verified').length / clips.length * 100)
  const stats = [['Clips', doc.clip_count.toLocaleString()], ['Duration', totalDur], ['Languages', langCount], ['Verified', `${verifiedPct}%`]]

  return (
    <div className="page" style={{ maxWidth: 940 }}>
      <h1 className="title">Download the dataset</h1>
      <p className="subtitle">Audio and transcripts are released as an open, forkable corpus.</p>

      <div className="stat-grid" style={{ marginTop: 22 }}>
        {stats.map(([k, v]) => (
          <div key={k} className="card stat"><div className="k">{k}</div><div className="v">{v}</div></div>
        ))}
      </div>

      <div className="card" style={{ padding: 24, marginTop: 14, display: 'flex', alignItems: 'center', gap: 24, flexWrap: 'wrap' }}>
        <div style={{ width: 52, height: 52, borderRadius: 'var(--radius-lg)', background: 'var(--secondary)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
          <Package size={24} strokeWidth={1.75} />
        </div>
        <div style={{ flex: 1, minWidth: 220 }}>
          <div style={{ fontSize: 16, fontWeight: 600 }}>Full corpus archive</div>
          <div style={{ fontSize: 13, color: 'var(--muted-foreground)', marginTop: 3 }}>dataset.zip · audio/ + metadata.json</div>
          <div style={{ display: 'flex', gap: 8, marginTop: 12, flexWrap: 'wrap' }}>
            {['WebM · Opus 48 kHz', 'metadata.json', 'open dataset'].map((t) => <span key={t} className="chip sm">{t}</span>)}
          </div>
        </div>
        <a className="btn lg" href="/dataset.zip" download onClick={() => showToast('Starting dataset.zip download…')}>
          <Download size={17} strokeWidth={1.75} />Download .zip
        </a>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginTop: 12 }}>
        <div className="card" style={{ padding: 18 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}><FileAudio size={17} strokeWidth={1.75} style={{ color: 'var(--muted-foreground)' }} /><span style={{ fontSize: 14, fontWeight: 600 }}>Individual clips</span></div>
          <p style={{ fontSize: 13, color: 'var(--muted-foreground)', lineHeight: 1.5, margin: '8px 0 0' }}>
            Open any clip and use <strong style={{ color: 'var(--foreground)', fontWeight: 600 }}>Download clip</strong> to grab a single file.
          </p>
        </div>
        <a className="card" href="/metadata.json" download style={{ padding: 18, display: 'block' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}><Braces size={17} strokeWidth={1.75} style={{ color: 'var(--muted-foreground)' }} /><span style={{ fontSize: 14, fontWeight: 600 }}>Manifest (metadata.json)</span></div>
          <p className="mono" style={{ fontSize: 12, color: 'var(--muted-foreground)', lineHeight: 1.5, margin: '8px 0 0' }}>
            {'{ id, filename, duration_sec, sample_rate, language, transcript, confidence, status }'}
          </p>
        </a>
      </div>
    </div>
  )
}

// ============ shared ============
function useClip() {
  const { id } = useParams()
  const { clips } = useStore()
  return clips.find((c) => c.id === id)
}

// ============ DETAIL ============
export function ClipDetail() {
  const c = useClip()
  const { clips, showToast } = useStore()
  const nav = useNavigate()
  if (!clips.length) return <div className="page" style={{ maxWidth: 900 }}><p>Loading…</p></div>
  if (!c) return <div className="page" style={{ maxWidth: 900 }}><p>Clip not found. <Link to="/">Back</Link></p></div>

  const meta = [
    ['Language', c.language || '—'], ['Duration', fmtDur(c.duration_sec)],
    ['Sample rate', fmtSampleRate(c.sample_rate)], ['Status', WORKFLOW[workflowState(c)].label],
    ['Bitrate', c.bitrate_kbps ? `${c.bitrate_kbps} kbps` : '—'], ['Codec', c.codec || '—'],
    ['Confidence', c.confidence != null ? `${Math.round(c.confidence * 100)}%` : '—'],
    ['No-speech', c.no_speech_prob != null ? `${Math.round(c.no_speech_prob * 100)}%` : '—'],
  ]

  return (
    <div className="page" style={{ maxWidth: 900, paddingTop: 24 }}>
      <Button variant="ghost" size="sm" icon={ChevronLeft} onClick={() => nav('/')}>Collection</Button>

      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16, margin: '14px 0 20px', flexWrap: 'wrap' }}>
        <div>
          <h1 className="title mono" style={{ fontSize: 22 }}>{shortId(c.id)}</h1>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 9 }}>
            <span className="chip sm">{c.language || 'unknown'}</span>
            <StatusBadge clip={c} />
            {c.corrupt && <span className="chip sm" style={{ background: 'oklch(0.577 0.245 27 / 0.12)', color: 'var(--destructive)' }}>corrupt</span>}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 9 }}>
          <a className="btn outline" href={audioSrc(c)} download onClick={() => showToast(`Downloading ${shortId(c.id)}…`)}>
            <Download size={15} strokeWidth={1.75} />Download clip
          </a>
          <Button icon={PencilLine} onClick={() => nav(`/clip/${c.id}/edit`)}>Correct transcript</Button>
        </div>
      </div>

      <Player id={c.id} src={audioSrc(c)} duration={c.duration_sec} sampleRate={c.sample_rate} showMeta />

      <div className="meta-grid" style={{ marginTop: 14 }}>
        {meta.map(([k, v]) => <div key={k} className="meta-cell"><div className="k">{k}</div><div className={`v${k === 'Duration' || k === 'Sample rate' || k === 'Bitrate' ? ' mono' : ''}`}>{v}</div></div>)}
      </div>

      <div className="card transcript-card" style={{ marginTop: 14 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span className="lbl">Transcript</span>
          <span style={{ fontSize: 12, color: 'var(--muted-foreground)' }}>
            · {c.transcript ? 'auto-generated, editable' : 'not transcribed yet'}
            {c.transcript_auto && c.transcript !== c.transcript_auto && ' · edited'}
          </span>
        </div>
        <p className="transcript-text" dir={dirFor(c.language)}>
          {c.transcript || <span style={{ color: 'var(--muted-foreground)' }}>No transcript yet — use “Correct transcript” to add one.</span>}
        </p>
      </div>
    </div>
  )
}

// ============ TRANSCRIBE / EDIT ============
export function EditView() {
  const c = useClip()
  const { clips } = useStore()
  if (!clips.length) return <div className="page" style={{ maxWidth: 900 }}><p>Loading…</p></div>
  if (!c) return <div className="page" style={{ maxWidth: 900 }}><p>Clip not found. <Link to="/">Back</Link></p></div>
  return <Editor c={c} />
}

function Editor({ c }) {
  const { editClip, showToast } = useStore()
  const nav = useNavigate()
  const [draft, setDraft] = useState(c.transcript || c.transcript_auto || '')

  function save() {
    editClip(c.id, { transcript: draft, status: 'verified' })
    showToast('Correction saved · marked verified')
    nav(`/clip/${c.id}`)
  }

  return (
    <div className="page" style={{ maxWidth: 900, paddingTop: 24 }}>
      <Button variant="ghost" size="sm" icon={ChevronLeft} onClick={() => nav(`/clip/${c.id}`)}>Back to clip</Button>
      <h1 className="title" style={{ fontSize: 22, margin: '14px 0 4px' }}>Correct transcript</h1>
      <p className="subtitle mono" style={{ margin: '0 0 18px' }}>{shortId(c.id)} · {c.language || 'unknown'}</p>

      <Player id={c.id} src={audioSrc(c)} duration={c.duration_sec} height={72} bars={44} />

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginTop: 14 }}>
        <div className="card" style={{ padding: 18 }}>
          <div className="lbl" style={{ marginBottom: 10 }}>Auto-generated</div>
          <p dir={dirFor(c.language)} style={{ fontSize: 16, lineHeight: 1.55, margin: 0, color: 'var(--muted-foreground)' }}>
            {c.transcript_auto || <em>Not transcribed yet — type the transcript from the audio.</em>}
          </p>
        </div>
        <div className="card" style={{ padding: 18 }}>
          <div className="lbl" style={{ marginBottom: 10 }}>Your correction</div>
          <textarea className="input" dir={dirFor(c.language)} value={draft} onChange={(e) => setDraft(e.target.value)}
            style={{ fontSize: 16 }} placeholder="Type the corrected transcript…" />
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 18 }}>
        <div style={{ flex: 1, fontSize: 13, color: 'var(--muted-foreground)' }}>
          Saving marks this clip as <strong style={{ color: 'var(--foreground)', fontWeight: 600 }}>verified</strong> and stores your edit locally.
        </div>
        <Button variant="ghost" onClick={() => nav(`/clip/${c.id}`)}>Cancel</Button>
        <Button icon={Check} onClick={save}>Save correction</Button>
      </div>
    </div>
  )
}
