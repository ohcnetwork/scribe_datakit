import { useEffect, useState } from 'react'
import { NavLink, Route, Routes, useNavigate } from 'react-router-dom'
import { AudioLines, ListMusic, Layers, Download, Scale, GitBranch, Upload, CheckCircle2, Sun, Moon } from 'lucide-react'
import { StoreProvider, useStore } from './store'
import { Button } from './ui'
import { CollectionList, ClipDetail, EditView, CategoryBrowse, DatasetDownload } from './pages'

const TAGLINE = 'An open collection of scribing audio and transcripts'

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
  const { doc, error, editCount, exportCorrections, showToast } = useStore()
  const [theme, toggleTheme] = useTheme()
  const nav = useNavigate()

  function contribute() {
    if (editCount > 0) { exportCorrections(); showToast(`Exported ${editCount} correction${editCount > 1 ? 's' : ''}`) }
    else { nav('/download') }
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-logo"><AudioLines size={19} strokeWidth={1.75} /></div>
          <div style={{ minWidth: 0 }}>
            <div className="brand-name">OpenScribe</div>
            <div className="brand-sub">Open speech corpus</div>
          </div>
        </div>
        <nav className="nav">
          <NavLink to="/" end><ListMusic size={17} strokeWidth={1.75} /><span>Browse</span></NavLink>
          <NavLink to="/categories"><Layers size={17} strokeWidth={1.75} /><span>Categories</span></NavLink>
          <NavLink to="/download"><Download size={17} strokeWidth={1.75} /><span>Download</span></NavLink>
        </nav>
        <div className="sidebar-foot">
          <div className="lic"><Scale size={14} strokeWidth={1.75} /><span>Open dataset · contributor-corrected</span></div>
          <div className="ver">corpus v1 · {doc ? doc.clip_count : '—'} clips</div>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div className="tagline">{TAGLINE}</div>
          <div className="spacer" />
          <a className="replink" href="#" onClick={(e) => { e.preventDefault(); showToast('Repository link not configured in this build') }}>
            <GitBranch size={15} strokeWidth={1.75} />Repository
          </a>
          <button className="icon-btn" onClick={toggleTheme} title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}>
            {theme === 'dark' ? <Sun size={17} strokeWidth={1.75} /> : <Moon size={17} strokeWidth={1.75} />}
          </button>
          <Button icon={Upload} onClick={contribute}>
            {editCount > 0 ? `Export ${editCount} edit${editCount > 1 ? 's' : ''}` : 'Contribute'}
          </Button>
        </header>

        <div className="scroll">
          {error
            ? <div className="page" style={{ maxWidth: 900 }}><p style={{ color: 'var(--destructive)' }}>Failed to load metadata.json: {error}</p></div>
            : (
              <Routes>
                <Route path="/" element={<CollectionList />} />
                <Route path="/clip/:id" element={<ClipDetail />} />
                <Route path="/clip/:id/edit" element={<EditView />} />
                <Route path="/categories" element={<CategoryBrowse />} />
                <Route path="/download" element={<DatasetDownload />} />
              </Routes>
            )}
        </div>
      </main>

      <Toast />
    </div>
  )
}

function Toast() {
  const { toast } = useStore()
  if (!toast) return null
  return <div className="toast"><CheckCircle2 size={16} strokeWidth={1.75} />{toast}</div>
}

export default function App() {
  return <StoreProvider><Shell /></StoreProvider>
}
