import { useEffect, useState } from 'react'
import { NavLink, Route, Routes } from 'react-router-dom'
import { AudioLines, BookOpen, CheckCircle2, Database, ExternalLink, GitPullRequest, ListMusic, Moon, Network, Sun, Users } from 'lucide-react'
import { ToastProvider, useToast, useConfig, hf } from './store'
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
          <a href="/guide.html" target="_blank" rel="noreferrer"><BookOpen size={17} strokeWidth={1.75} /><span>Reviewer guide</span></a>
          <a href="/how-it-works.html" target="_blank" rel="noreferrer"><Network size={17} strokeWidth={1.75} /><span>How it works</span></a>
        </nav>
        <HubLinks />
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

// Where the shared state lives, so a reviewer can check it on Hugging Face themselves.
function HubLinks() {
  const cfg = useConfig()
  if (!cfg) return null
  const link = (href, Icon, label) => (
    <a href={href} target="_blank" rel="noreferrer"><Icon size={17} strokeWidth={1.75} /><span>{label}</span><ExternalLink size={12} className="ext" /></a>
  )
  return (
    <nav className="nav hub" aria-label="Hugging Face">
      <div className="nav-head">On Hugging Face</div>
      {link(hf.repo(cfg.repo), Database, 'Dataset')}
      {link(hf.prs(cfg.repo), GitPullRequest, 'Claims and submissions')}
      {link(hf.org(cfg.org), Users, cfg.org)}
      <div className="nav-foot mono" title="Set by HF_ORG and HF_DATASET in .env">{cfg.repo}</div>
    </nav>
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
