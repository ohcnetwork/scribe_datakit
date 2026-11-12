import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Check, ChevronLeft, ChevronRight, ExternalLink, Flag, Loader2, LogIn, Play, RefreshCw, Send } from 'lucide-react'
import Player from './Player'
import { Button } from './ui'
import { api, useToast, useConfig, hf, CATEGORIES, clipLangs, isEnglishOnly, segmentDone, fmtDur, dirFor } from './store'

const shortId = (id) => id.slice(0, 8)

// Seconds since `since`, ticking, so a long wait visibly isn't frozen.
function useElapsed(since) {
  const [now, setNow] = useState(Date.now())
  useEffect(() => {
    if (!since) return
    const t = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(t)
  }, [since])
  return since ? Math.max(0, Math.round((now - since) / 1000)) : 0
}

// What's happening right now, how far along, and for how long.
function Busy({ step, done, total, item, since, children }) {
  const secs = useElapsed(since)
  return (
    <div className="card busy" role="status" aria-live="polite">
      <div className="busy-head">
        <Loader2 size={16} strokeWidth={2} className="spin" />
        <span style={{ flex: 1 }}>{step}{total ? ` · ${done} of ${total}` : ''}</span>
        {secs > 0 && <span className="rowid">{secs}s</span>}
      </div>
      {total > 0 && (
        <div className="progress" role="progressbar" aria-valuenow={done} aria-valuemin={0} aria-valuemax={total}>
          <span style={{ width: `${(done / total) * 100}%` }} />
        </div>
      )}
      {item && <div className="rowid" style={{ marginTop: 6 }}>clip {shortId(item)}</div>}
      {children}
    </div>
  )
}

function Load({ error, what = 'Loading…', retry }) {
  const [since] = useState(Date.now())
  const secs = useElapsed(error ? null : since)
  if (error) return (
    <div className="page"><p className="error-text">{error}</p>
      {retry && <Button variant="outline" icon={RefreshCw} onClick={retry}>Try again</Button>}</div>
  )
  return (
    <div className="page" style={{ maxWidth: 560 }}>
      <Busy step={what} since={since}>
        {secs >= 15 && <p className="subtitle">Hugging Face is slow to answer. If this doesn't finish, check your internet and{' '}
          {retry ? <a href="#" onClick={(e) => { e.preventDefault(); retry() }}>try again</a> : 'reload the page'}.</p>}
      </Busy>
    </div>
  )
}

const PrLink = ({ repo, num, children }) => repo && num
  ? <a className="ext-link" href={hf.pr(repo, num)} target="_blank" rel="noreferrer">{children || `PR #${num}`}<ExternalLink size={11} /></a>
  : null

// ============ SIGN IN ============
function Login({ repo, onDone }) {
  const [token, setToken] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  async function submit(e) {
    e.preventDefault()
    setBusy(true); setError(null)
    try { onDone(await api('/login', 'POST', { token })) }
    catch (err) { setError(err.message) }
    setBusy(false)
  }
  return (
    <div className="page" style={{ maxWidth: 560 }}>
      <h1 className="title">Connect to Hugging Face</h1>
      <p className="subtitle">Your reviews are sent to {repo} from your own account.</p>
      <ol className="steps">
        <li>Open <a href="https://huggingface.co/settings/tokens" target="_blank" rel="noreferrer">your access tokens</a> and create a token.</li>
        <li>Paste it below. It's saved on this computer only.</li>
      </ol>
      <form onSubmit={submit} className="card" style={{ padding: 18 }}>
        <label className="lbl" htmlFor="hf-token">Access token</label>
        <input id="hf-token" className="input" type="password" autoComplete="off" value={token}
          onChange={(e) => setToken(e.target.value)} style={{ margin: '10px 0 14px' }} />
        {error && <p className="error-text">{error}</p>}
        <Button icon={busy ? Loader2 : LogIn} spin={busy} type="submit" disabled={busy || !token.trim()}>{busy ? 'Checking your token and loading batches…' : 'Connect'}</Button>
      </form>
    </div>
  )
}

// ============ BATCHES ============
export function Batches() {
  const [state, setState] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(null)
  const [progress, setProgress] = useState(null)
  const [refreshing, setRefreshing] = useState(false)
  const nav = useNavigate()
  const load = () => {
    setError(null); setRefreshing(true)
    return api('/state').then(setState).catch((e) => setError(e.message)).finally(() => setRefreshing(false))
  }
  useEffect(() => { load() }, [])

  async function claim(name) {
    setBusy(name); setError(null)
    setProgress({ step: 'Starting', since: Date.now() })
    // the claim is one long request; poll what it's doing meanwhile
    const poll = setInterval(() => api(`/batches/${name}/progress`)
      .then((p) => p.step && setProgress((old) => ({ ...p, since: old?.since }))).catch(() => {}), 600)
    try { await api(`/batches/${name}/claim`, 'POST'); nav(`/batch/${name}`) }
    catch (e) { setError(e.message); setBusy(null); load() }
    finally { clearInterval(poll); setProgress(null) }
  }

  if (!state) return <Load error={error} retry={load} what="Checking your Hugging Face login and the list of batches" />
  if (!state.user) return <Login repo={state.repo} onDone={setState} />
  return (
    <div className="page" style={{ maxWidth: 820 }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
        <div style={{ flex: 1 }}>
          <h1 className="title">Review batches</h1>
          <p className="subtitle">Signed in as {state.user}, reviewing{' '}
            <a className="ext-link" href={hf.repo(state.repo)} target="_blank" rel="noreferrer">{state.repo}<ExternalLink size={11} /></a>.
            {' '}Claim a batch to download it and start reviewing.</p>
        </div>
        <Button variant="outline" size="sm" icon={refreshing ? Loader2 : RefreshCw} spin={refreshing} onClick={load} disabled={refreshing || !!busy}
          title="See claims other reviewers made since you opened this page">{refreshing ? 'Refreshing…' : 'Refresh'}</Button>
      </div>
      {error && <p className="error-text">{error}</p>}
      {progress && (
        <div style={{ marginTop: 16 }}>
          <Busy {...progress} step={progress.step === 'Starting' ? `Claiming ${busy}` : progress.step}>
            <p className="subtitle">Keep this page open. Everything is downloaded once, so you can review offline afterwards.</p>
          </Busy>
        </div>
      )}
      <div className="card" style={{ marginTop: 18, overflow: 'hidden' }}>
        {state.batches.map((b) => (
          <div key={b.name} className="batch-row">
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="mono" style={{ fontSize: 14 }}>{b.name}</div>
              <div className="rowid">
                {b.state === 'available' && 'Available'}
                {b.state === 'mine' && 'Claimed by you'}
                {b.state === 'taken' && `Claimed by ${b.reviewer}`}
                {b.state === 'submitted' && 'Submitted, waiting for the maintainer'}
                {b.state === 'done' && `Finished by ${b.reviewer}`}
                {b.pr && <> · <PrLink repo={state.repo} num={b.pr} /></>}
              </div>
            </div>
            {b.state === 'available' && <Button onClick={() => claim(b.name)} disabled={!!busy}>{busy === b.name ? 'Claiming…' : 'Claim'}</Button>}
            {b.state === 'mine' && (b.local && busy !== b.name
              ? <Link className="btn outline" to={`/batch/${b.name}`}>Continue</Link>
              : <Button variant="outline" onClick={() => claim(b.name)} disabled={!!busy}>{busy === b.name ? 'Downloading…' : 'Continue'}</Button>)}
            {b.state === 'submitted' && b.local && <Link className="btn outline" to={`/batch/${b.name}`}>Open</Link>}
          </div>
        ))}
        {!state.batches.length && <div className="empty"><p>No batches are ready yet.</p></div>}
      </div>
    </div>
  )
}

// ============ ONE BATCH ============
export function Batch() {
  const { batch } = useParams()
  const [doc, setDoc] = useState(null)
  const [error, setError] = useState(null)
  const [sent, setSent] = useState(false)
  const [sending, setSending] = useState(null)
  const { showToast } = useToast()
  const cfg = useConfig()
  const nav = useNavigate()
  useEffect(() => { api(`/batches/${batch}`).then(setDoc).catch((e) => setError(e.message)) }, [batch])

  async function submit() {
    setError(null); setSending(Date.now())
    try {
      const r = await api(`/batches/${batch}/submit`, 'POST')
      setSent(true)
      showToast(`Submitted ${r.submitted} clips`)
    } catch (e) { setError(e.message) }
    setSending(null)
  }

  if (!doc) return <Load error={error} />
  const done = doc.clips.filter((c) => c.done).length
  const next = doc.clips.find((c) => !c.done)
  return (
    <div className="page" style={{ maxWidth: 820 }}>
      <Button variant="ghost" size="sm" icon={ChevronLeft} onClick={() => nav('/')}>Batches</Button>
      <h1 className="title mono" style={{ fontSize: 22, marginTop: 14 }}>{batch}</h1>
      <p className="subtitle">{doc.kind === 'qa' ? 'QA check' : 'Review'} · {done} of {doc.clips.length} clips done
        {cfg && doc.pr && <> · your claim is <PrLink repo={cfg.repo} num={doc.pr} /></>}</p>
      <div className="progress" role="progressbar" aria-valuenow={done} aria-valuemin={0} aria-valuemax={doc.clips.length}>
        <span style={{ width: `${(done / doc.clips.length) * 100}%` }} />
      </div>
      {error && <p className="error-text">{error}</p>}
      <div style={{ display: 'flex', gap: 10, margin: '16px 0' }}>
        {next
          ? <Button icon={ChevronRight} onClick={() => nav(`/batch/${batch}/clip/${next.id}`)}>{done ? 'Next clip' : 'Start reviewing'}</Button>
          : <Button icon={Send} onClick={submit} disabled={sent || !!sending}>{sent ? 'Submitted' : 'Submit batch'}</Button>}
      </div>
      {sending && <div style={{ marginBottom: 16 }}><Busy step="Sending your reviews to Hugging Face and publishing your claim" since={sending} /></div>}
      {sent && cfg && (
        <p className="subtitle" style={{ marginBottom: 16 }}>Sent. The maintainer will check it on{' '}
          <PrLink repo={cfg.repo} num={doc.pr}>pull request #{doc.pr}</PrLink>, where you can see it too.</p>
      )}
      <div className="card" style={{ overflow: 'hidden' }}>
        {doc.clips.map((c) => (
          <Link key={c.id} className="batch-row" to={`/batch/${batch}/clip/${c.id}`}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="mono" style={{ fontSize: 14 }}>{shortId(c.id)}</div>
              <div className="rowid">{c.segments.length} segment{c.segments.length > 1 ? 's' : ''} · {fmtDur(c.duration_sec)}</div>
            </div>
            <span className={`status ${c.flagged ? 'flagged' : c.done ? 'final' : 'needs-review'}`}>
              <span className="dot" />{c.flagged ? 'Flagged' : c.done ? 'Done' : 'To do'}
            </span>
          </Link>
        ))}
      </div>
    </div>
  )
}

// ============ ONE CLIP ============
function Field({ title, generated, final, dir, onChange, onCommit }) {
  const touched = final !== null && final !== undefined
  return (
    <div className="field">
      <div className="field-head">
        <span className="lbl">{title}</span>
        {touched
          ? <span className="saved"><Check size={13} strokeWidth={2} />Reviewed</span>
          : <Button variant="outline" size="sm" disabled={!generated} onClick={() => onCommit(generated)}>Accept as is</Button>}
      </div>
      {generated && <p className="generated" dir={dir}>{generated}</p>}
      <textarea className="input" dir={dir} aria-label={title} value={final ?? generated ?? ''}
        onChange={(e) => onChange(e.target.value)} onBlur={(e) => touched && onCommit(e.target.value)} />
    </div>
  )
}

function Segment({ s, dir, english, onPlay, update }) {
  const set = (k) => (v) => update(s.index, { [k]: v }, false)
  const commit = (k) => (v) => update(s.index, { [k]: v }, true)
  return (
    <div className={`card segment${segmentDone(s) ? ' done' : ''}`}>
      <div className="segment-head">
        <button className="playbtn" title={`Play segment ${s.index + 1}`} aria-label={`Play segment ${s.index + 1}`} onClick={() => onPlay(s)}>
          <Play size={13} strokeWidth={1.75} />
        </button>
        <span className="mono" style={{ fontSize: 13 }}>{fmtDur(s.start)} – {fmtDur(s.end)}</span>
        <div style={{ flex: 1 }} />
        <label className="check">
          <input type="checkbox" checked={!!s.excluded} onChange={(e) => update(s.index, { excluded: e.target.checked }, true)} />
          No usable speech
        </label>
      </div>
      {!s.excluded && (
        <div className={english ? '' : 'two-col'}>
          <Field title={`Transcript ${s.index + 1}`} generated={s.generated_transcript} final={s.final_transcript} dir={dir}
            onChange={set('final_transcript')} onCommit={commit('final_transcript')} />
          {!english && <Field title={`Translation ${s.index + 1}`} generated={s.generated_translation} final={s.final_translation} dir="ltr"
            onChange={set('final_translation')} onCommit={commit('final_translation')} />}
        </div>
      )}
    </div>
  )
}

export function Clip() {
  const { batch, id } = useParams()
  const [doc, setDoc] = useState(null)
  const [error, setError] = useState(null)
  const [langText, setLangText] = useState('')
  const [finishing, setFinishing] = useState(false)
  const player = useRef(null)
  const queue = useRef(Promise.resolve())   // saves run in order, so "done" never overtakes an edit
  const nav = useNavigate()
  const { showToast } = useToast()

  useEffect(() => {
    setError(null)
    api(`/batches/${batch}`).then((d) => {
      setDoc(d)
      setLangText((d.clips.find((c) => c.id === id)?.spoken_languages || []).join(', '))
    }).catch((e) => setError(e.message))
  }, [batch, id])

  if (!doc) return <Load error={error} />
  const clip = doc.clips.find((c) => c.id === id)
  if (!clip) return <Load error="That clip isn't in this batch." />

  const setClip = (fn) => setDoc((d) => ({ ...d, clips: d.clips.map((c) => (c.id === id ? fn(c) : c)) }))
  const save = (patch) => {
    const run = queue.current.then(() => api(`/batches/${batch}/clips/${id}`, 'PATCH', patch))
    queue.current = run.catch(() => {})
    return run
  }
  const saveQuietly = (patch) => save(patch).catch((e) => setError(e.message))

  function update(index, fields, persist) {
    setClip((c) => ({ ...c, segments: c.segments.map((s) => (s.index === index ? { ...s, ...fields } : s)) }))
    if (persist) saveQuietly({ segments: [{ index, ...fields }] })
  }

  function saveLanguages() {
    const typed = langText.split(',').map((l) => l.trim().toLowerCase()).filter(Boolean)
    if (!typed.every((l) => /^[a-z]{2,3}$/.test(l))) return setError('Use language codes such as ml or en.')
    setError(null)
    const langs = typed.length ? typed : null
    setClip((c) => ({ ...c, spoken_languages: langs }))
    saveQuietly({ spoken_languages: langs })
  }

  async function finish(flagged) {
    setError(null); setFinishing(true)
    try {
      await save({ done: true, flagged })
      const after = doc.clips.find((c) => !c.done && c.id !== id)
      showToast(flagged ? 'Flagged for the maintainer' : 'Saved')
      nav(after ? `/batch/${batch}/clip/${after.id}` : `/batch/${batch}`)
    } catch (e) { setError(e.message) }
    setFinishing(false)
  }

  const langs = clipLangs(clip)
  const english = isEnglishOnly(langs)
  const left = clip.segments.filter((s) => !segmentDone(s)).length
  return (
    <div className="page" style={{ maxWidth: 980, paddingTop: 24 }}>
      <Button variant="ghost" size="sm" icon={ChevronLeft} onClick={() => nav(`/batch/${batch}`)}>{batch}</Button>
      <h1 className="title mono" style={{ fontSize: 22, margin: '14px 0 16px' }}>{shortId(clip.id)}</h1>

      <Player ref={player} id={clip.id} src={`/media/${batch}/audio/${clip.id}.flac`}
        peaks={`/media/${batch}/peaks/${clip.id}.json`} duration={clip.duration_sec} height={72} bars={72} />

      <div className="card meta-row">
        <div style={{ flex: 2, minWidth: 220 }}>
          <label className="lbl" htmlFor="spoken-languages">Spoken languages</label>
          <input id="spoken-languages" className="input" value={langText} onChange={(e) => setLangText(e.target.value)} onBlur={saveLanguages}
            placeholder={`Codes, e.g. ml, en. Whisper guessed ${clip.whisper_language || 'nothing'}.`} />
        </div>
        <div style={{ flex: 1, minWidth: 160 }}>
          <label className="lbl" htmlFor="clip-category">Category</label>
          <select id="clip-category" className="input" value={clip.category}
            onChange={(e) => { setClip((c) => ({ ...c, category: e.target.value })); saveQuietly({ category: e.target.value }) }}>
            {CATEGORIES.map((c) => <option key={c}>{c}</option>)}
          </select>
        </div>
      </div>

      {english && <p className="subtitle" style={{ margin: '14px 0 0' }}>English-only audio doesn't need a translation.</p>}
      {clip.segments.map((s) => (
        <Segment key={s.index} s={s} dir={dirFor(langs[0])} english={english} update={update}
          onPlay={(seg) => player.current?.playRange(seg.start, seg.end)} />
      ))}

      <div className="finish-bar">
        <div style={{ flex: 1, minWidth: 200, fontSize: 13 }} className={error ? 'error-text' : 'subtitle'}>
          {error || (left ? `${left} segment${left > 1 ? 's' : ''} still to review.` : 'All segments reviewed.')}
        </div>
        <Button variant="outline" icon={Flag} disabled={finishing} onClick={() => finish(true)}>Flag clip</Button>
        <Button icon={Check} disabled={left > 0 || finishing} onClick={() => finish(false)}>
          {doc.kind === 'qa' ? 'Mark QA complete' : 'Mark reviewed'}
        </Button>
      </div>
    </div>
  )
}
