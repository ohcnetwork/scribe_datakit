import { useEffect, useRef, useState } from 'react'
import { Play, Pause, Waves } from 'lucide-react'
import { fmtDur, fmtSampleRate } from './store'
import { asset } from './asset'

// Canvas waveform drawn from precomputed peaks (/peaks/<id>.json), played through
// a native <audio> element — Chrome decodes these header-less webm/opus fine while
// audio.duration reports Infinity, so we drive the playhead from our known
// duration. Matches the design's bar waveform with played/idle colouring.
function downsample(peaks, n) {
  if (!peaks?.length) return new Array(n).fill(0.04)
  const step = peaks.length / n
  const out = []
  for (let i = 0; i < n; i++) {
    let m = 0
    for (let j = Math.floor(i * step); j < Math.floor((i + 1) * step); j++) m = Math.max(m, peaks[j])
    out.push(m)
  }
  return out
}

export default function Player({ id, src, duration, sampleRate, height = 92, bars = 56, showMeta = false }) {
  const canvas = useRef(null)
  const audio = useRef(null)
  const barsRef = useRef(null)
  const raf = useRef(0)
  const [playing, setPlaying] = useState(false)
  const [cur, setCur] = useState(0)

  useEffect(() => {
    fetch(asset(`/peaks/${id}.json`))
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { barsRef.current = downsample(d?.peaks, bars); draw(frac()) })
      .catch(() => { barsRef.current = downsample(null, bars); draw(0) })
    return () => cancelAnimationFrame(raf.current)
  }, [id, bars])

  // waveform colours come from CSS vars read at draw time → redraw on theme switch
  useEffect(() => {
    const obs = new MutationObserver(() => draw(frac()))
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
    return () => obs.disconnect()
  }, [])

  const frac = () => {
    const a = audio.current
    return a && duration ? Math.min(1, a.currentTime / duration) : 0
  }

  function draw(played) {
    const cv = canvas.current
    if (!cv || !barsRef.current) return
    const dpr = window.devicePixelRatio || 1
    const rect = cv.getBoundingClientRect()
    const W = rect.width || 600, H = rect.height || height
    cv.width = W * dpr; cv.height = H * dpr
    const ctx = cv.getContext('2d'); ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    ctx.clearRect(0, 0, W, H)
    const style = getComputedStyle(cv)
    const played1 = style.getPropertyValue('--foreground').trim() || '#111'
    const idle = style.getPropertyValue('--wave-idle').trim() || '#ddd'
    const wave = barsRef.current, n = wave.length, gap = 3
    const bw = (W - gap * (n - 1)) / n
    for (let i = 0; i < n; i++) {
      const h = Math.max(2, wave[i] * (H - 6))
      const x = i * (bw + gap), y = (H - h) / 2
      ctx.fillStyle = (i / n) <= played ? played1 : idle
      const r = Math.min(bw / 2, 2.2)
      ctx.beginPath()
      if (ctx.roundRect) ctx.roundRect(x, y, bw, h, r); else ctx.rect(x, y, bw, h)
      ctx.fill()
    }
  }

  function loop() {
    setCur(audio.current?.currentTime || 0)
    draw(frac())
    raf.current = requestAnimationFrame(loop)
  }
  function onPlay() { setPlaying(true); cancelAnimationFrame(raf.current); loop() }
  function onPause() { setPlaying(false); cancelAnimationFrame(raf.current); draw(frac()) }
  function toggle() { const a = audio.current; if (!a) return; a.paused ? a.play() : a.pause() }
  function seek(e) {
    const a = audio.current; if (!a || !duration) return
    const r = e.currentTarget.getBoundingClientRect()
    a.currentTime = Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)) * duration
    setCur(a.currentTime); draw(frac())
  }

  return (
    <div className="card player-card">
      <audio ref={audio} src={src} preload="none" onPlay={onPlay} onPause={onPause}
        onEnded={onPause} onTimeUpdate={() => setCur(audio.current?.currentTime || 0)} style={{ display: 'none' }} />
      <canvas ref={canvas} className="wave" style={{ height }} onClick={seek} />
      <div className="player-row">
        <button className="play-lg" onClick={toggle} style={height < 90 ? { width: 42, height: 42 } : undefined}>
          {playing ? <Pause size={height < 90 ? 17 : 19} strokeWidth={1.75} /> : <Play size={height < 90 ? 17 : 19} strokeWidth={1.75} />}
        </button>
        <div className="mono" style={{ fontSize: 14 }}>
          {fmtDur(cur)} <span style={{ color: 'var(--muted-foreground)' }}>/ {fmtDur(duration)}</span>
        </div>
        {showMeta && <>
          <div style={{ flex: 1 }} />
          <div className="mono" style={{ fontSize: 13, color: 'var(--muted-foreground)', display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <Waves size={15} strokeWidth={1.75} />{fmtSampleRate(sampleRate)}
          </div>
        </>}
      </div>
    </div>
  )
}
