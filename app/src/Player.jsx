import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react'
import { Play, Pause } from 'lucide-react'
import { fmtDur } from './store'

// Canvas waveform drawn from precomputed peaks, played through a native <audio>
// element. playRange() lets a segment row play just its part of the recording.
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

export default forwardRef(function Player({ id, src, peaks, duration, height = 92, bars = 56 }, ref) {
  const canvas = useRef(null)
  const audio = useRef(null)
  const barsRef = useRef(null)
  const raf = useRef(0)
  const stopAt = useRef(null)
  const [playing, setPlaying] = useState(false)
  const [cur, setCur] = useState(0)

  useEffect(() => {
    fetch(peaks)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { barsRef.current = downsample(d?.peaks, bars); draw(frac()) })
      .catch(() => { barsRef.current = downsample(null, bars); draw(0) })
    return () => cancelAnimationFrame(raf.current)
  }, [id, peaks, bars])

  useImperativeHandle(ref, () => ({
    playRange(start, end) {
      const a = audio.current; if (!a) return
      stopAt.current = end
      a.currentTime = start
      a.play()
    },
  }))

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
    const a = audio.current
    setCur(a?.currentTime || 0)
    if (a && stopAt.current != null && a.currentTime >= stopAt.current) { stopAt.current = null; a.pause() }
    draw(frac())
    raf.current = requestAnimationFrame(loop)
  }
  function onPlay() { setPlaying(true); cancelAnimationFrame(raf.current); loop() }
  function onPause() { setPlaying(false); cancelAnimationFrame(raf.current); draw(frac()) }
  function toggle() { const a = audio.current; if (!a) return; stopAt.current = null; a.paused ? a.play() : a.pause() }
  function seek(e) {
    const a = audio.current; if (!a || !duration) return
    stopAt.current = null
    const r = e.currentTarget.getBoundingClientRect()
    a.currentTime = Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)) * duration
    setCur(a.currentTime); draw(frac())
  }

  return (
    <div className="card player-card">
      <audio ref={audio} src={src} preload="metadata" onPlay={onPlay} onPause={onPause}
        onEnded={onPause} onTimeUpdate={() => setCur(audio.current?.currentTime || 0)} style={{ display: 'none' }} />
      <canvas ref={canvas} className="wave" style={{ height }} onClick={seek} />
      <div className="player-row">
        <button className="play-lg" aria-label={playing ? 'Pause' : 'Play'} onClick={toggle} style={height < 90 ? { width: 42, height: 42 } : undefined}>
          {playing ? <Pause size={height < 90 ? 17 : 19} strokeWidth={1.75} /> : <Play size={height < 90 ? 17 : 19} strokeWidth={1.75} />}
        </button>
        <div className="mono" style={{ fontSize: 14 }}>
          {fmtDur(cur)} <span style={{ color: 'var(--muted-foreground)' }}>/ {fmtDur(duration)}</span>
        </div>
      </div>
    </div>
  )
})
