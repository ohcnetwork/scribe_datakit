import { useEffect, useState } from 'react'
import { NavLink, Route, Routes } from 'react-router-dom'
import { AudioLines, CheckCircle2, ListMusic, Moon, Sun } from 'lucide-react'
import { ToastProvider, useToast } from './store'
import { Batch, Batches, Clip } from './pages'

// Theme: follow the system until the user picks; then persist their choice.
// CSS keys off :root[data-theme]; unset falls back to prefers-color-scheme.
function useTheme() {
  const [theme, setTheme] = useState(() =>
    localStorage.getItem('scribe-theme') ||
    (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'))
  useEffect(() => {
    document.documentElement.dataset.theme = theme
    localStorage.setItem('scribe-theme', theme)
  }, [theme])
  return [theme, () => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))]
}

function Shell() {
  const [theme, toggleTheme] = useTheme()
  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-logo"><AudioLines size={19} strokeWidth={1.75} /></div>
          <div style={{ minWidth: 0 }}>
            <div className="brand-name">OpenScribe</div>
            <div className="brand-sub">Review tool</div>
          </div>
        </div>
        <nav className="nav">
          <NavLink to="/" end><ListMusic size={17} strokeWidth={1.75} /><span>Batches</span></NavLink>
        </nav>
      </aside>

      <main className="main">
        <header className="topbar">
          <div className="tagline">Review Whisper's text against the audio</div>
          <div className="spacer" />
          <button className="icon-btn" onClick={toggleTheme} title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}>
            {theme === 'dark' ? <Sun size={17} strokeWidth={1.75} /> : <Moon size={17} strokeWidth={1.75} />}
          </button>
        </header>

        <div className="scroll">
          <Routes>
            <Route path="/" element={<Batches />} />
            <Route path="/batch/:batch" element={<Batch />} />
            <Route path="/batch/:batch/clip/:id" element={<Clip />} />
          </Routes>
        </div>
      </main>

      <Toast />
    </div>
  )
}

function Toast() {
  const { toast } = useToast()
  if (!toast) return null
  return <div className="toast" role="status"><CheckCircle2 size={16} strokeWidth={1.75} />{toast}</div>
}

export default function App() {
  return <ToastProvider><Shell /></ToastProvider>
}
