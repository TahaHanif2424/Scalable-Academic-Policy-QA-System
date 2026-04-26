import { useState } from 'react'
import AnimatedBackground from './components/AnimatedBackground'
import Sidebar from './components/Sidebar'
import Header from './components/Header'
import UploadSection from './components/UploadSection'
import ChatSection from './components/ChatSection'
import InsightsSection from './components/InsightsSection'
import './App.css'

export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard')
  const [files, setFiles] = useState([])
  const [pastedText, setPastedText] = useState('')

  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: 'var(--bg-primary)', position: 'relative' }}>
      <AnimatedBackground />

      {/* Gradient blobs */}
      <div style={{
        position: 'fixed', top: -200, left: -200, width: 600, height: 600,
        borderRadius: '50%',
        background: 'radial-gradient(circle, rgba(99,179,237,0.06) 0%, transparent 70%)',
        pointerEvents: 'none', zIndex: 0,
      }} />
      <div style={{
        position: 'fixed', bottom: -200, right: -200, width: 700, height: 700,
        borderRadius: '50%',
        background: 'radial-gradient(circle, rgba(183,148,244,0.06) 0%, transparent 70%)',
        pointerEvents: 'none', zIndex: 0,
      }} />

      {/* Sidebar */}
      <Sidebar activeTab={activeTab} onTabChange={setActiveTab} />

      {/* Main Content */}
      <div style={{ marginLeft: 220, flex: 1, display: 'flex', flexDirection: 'column', position: 'relative', zIndex: 1 }}>
        <Header activeTab={activeTab} />

        <main style={{ flex: 1, padding: '24px 28px', overflowY: 'auto' }}>

          {/* ── DASHBOARD ── */}
          {activeTab === 'dashboard' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
              {/* Hero Banner */}
              <div style={{
                borderRadius: 20,
                background: 'linear-gradient(135deg, rgba(13,18,52,0.9) 0%, rgba(20,10,40,0.9) 100%)',
                border: '1px solid var(--border)',
                padding: '32px 36px',
                position: 'relative', overflow: 'hidden',
                backdropFilter: 'blur(20px)',
              }}>
                {/* Glow orbs */}
                <div style={{ position: 'absolute', top: -60, right: 60, width: 200, height: 200, borderRadius: '50%', background: 'radial-gradient(circle, rgba(99,179,237,0.15) 0%, transparent 70%)', pointerEvents: 'none' }} />
                <div style={{ position: 'absolute', bottom: -60, right: 200, width: 150, height: 150, borderRadius: '50%', background: 'radial-gradient(circle, rgba(183,148,244,0.15) 0%, transparent 70%)', pointerEvents: 'none' }} />

                <div style={{ position: 'relative', zIndex: 1, maxWidth: 640 }}>
                  <div style={{
                    display: 'inline-flex', alignItems: 'center', gap: 6,
                    padding: '4px 12px', borderRadius: 20, marginBottom: 16,
                    background: 'rgba(99,179,237,0.1)', border: '1px solid rgba(99,179,237,0.25)',
                    fontSize: 11, color: 'var(--accent-blue)', fontWeight: 600, letterSpacing: '0.06em',
                  }}>
                    ✦ BIG DATA ANALYTICS PLATFORM
                  </div>
                  <h1 style={{
                    fontFamily: 'var(--heading)', fontSize: 32, fontWeight: 700,
                    color: 'var(--text-primary)', margin: '0 0 12px',
                    letterSpacing: '-0.6px', lineHeight: 1.2,
                    background: 'linear-gradient(135deg, #e2e8f0 0%, #63b3ed 50%, #b794f4 100%)',
                    WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
                  }}>
                    Unlock Intelligence<br />from Your Data
                  </h1>
                  <p style={{ fontSize: 14, color: 'var(--text-secondary)', lineHeight: 1.7, margin: '0 0 24px' }}>
                    Upload PDFs, paste large datasets, and ask natural language questions.
                    Powered by AI to surface insights, patterns, and answers in seconds.
                  </p>
                  <div style={{ display: 'flex', gap: 10 }}>
                    <button onClick={() => setActiveTab('documents')} style={{
                      padding: '10px 22px', borderRadius: 10, border: 'none',
                      background: 'linear-gradient(135deg, #63b3ed, #b794f4)',
                      color: '#fff', fontWeight: 600, fontSize: 13,
                      boxShadow: '0 0 25px rgba(99,179,237,0.4)', cursor: 'pointer',
                      transition: 'transform 0.2s, box-shadow 0.2s',
                    }}
                      onMouseEnter={e => { e.currentTarget.style.transform = 'translateY(-1px)'; e.currentTarget.style.boxShadow = '0 0 35px rgba(99,179,237,0.55)'; }}
                      onMouseLeave={e => { e.currentTarget.style.transform = 'none'; e.currentTarget.style.boxShadow = '0 0 25px rgba(99,179,237,0.4)'; }}
                    >
                      Upload Documents →
                    </button>
                    <button onClick={() => setActiveTab('chat')} style={{
                      padding: '10px 22px', borderRadius: 10,
                      background: 'rgba(255,255,255,0.05)', border: '1px solid var(--border)',
                      color: 'var(--text-primary)', fontWeight: 600, fontSize: 13, cursor: 'pointer',
                      transition: 'all 0.2s',
                    }}
                      onMouseEnter={e => { e.currentTarget.style.background = 'rgba(99,179,237,0.1)'; e.currentTarget.style.borderColor = 'rgba(99,179,237,0.3)'; }}
                      onMouseLeave={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.05)'; e.currentTarget.style.borderColor = 'var(--border)'; }}
                    >
                      Ask AI Now
                    </button>
                  </div>
                </div>
              </div>

            </div>
          )}

          {/* ── DOCUMENTS ── */}
          {activeTab === 'documents' && (
            <div style={{ maxWidth: 720 }}>
              <div style={{
                padding: '24px', borderRadius: 20,
                background: 'var(--bg-card)', border: '1px solid var(--border)',
                backdropFilter: 'blur(20px)',
              }}>
                <div style={{ marginBottom: 20 }}>
                  <h2 style={{ fontFamily: 'var(--heading)', fontSize: 18, fontWeight: 700, color: 'var(--text-primary)', margin: '0 0 4px' }}>Document Library</h2>
                  <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>Upload PDFs or paste text to build your analytics corpus</p>
                </div>
                <UploadSection
                  files={files} setFiles={setFiles}
                  pastedText={pastedText} setPastedText={setPastedText}
                />
              </div>
            </div>
          )}

          {/* ── CHAT / ASK AI ── */}
          {activeTab === 'chat' && (
            <div style={{ display: 'grid', gridTemplateColumns: '300px 1fr', gap: 20, height: 'calc(100vh - 130px)' }}>
              {/* Left Panel: Upload */}
              <div style={{
                borderRadius: 16, border: '1px solid var(--border)',
                background: 'var(--bg-card)', backdropFilter: 'blur(20px)',
                padding: '18px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 16,
              }}>
                <div>
                  <h3 style={{ fontFamily: 'var(--heading)', fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', margin: '0 0 4px' }}>Data Sources</h3>
                  <p style={{ fontSize: 11, color: 'var(--text-muted)' }}>Add context for the AI</p>
                </div>
                <UploadSection
                  files={files} setFiles={setFiles}
                  pastedText={pastedText} setPastedText={setPastedText}
                />
              </div>
              {/* Right Panel: Chat */}
              <ChatSection files={files} pastedText={pastedText} />
            </div>
          )}

          {/* ── INSIGHTS ── */}
          {activeTab === 'insights' && (
            <InsightsSection files={files} pastedText={pastedText} />
          )}

          {/* ── ANALYTICS ── */}
          {activeTab === 'analytics' && (
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              minHeight: 400, flexDirection: 'column', gap: 16,
              borderRadius: 20, border: '1px dashed var(--border)',
              background: 'rgba(5,8,22,0.4)',
            }}>
              <div style={{
                width: 64, height: 64, borderRadius: 18,
                background: 'linear-gradient(135deg, rgba(99,179,237,0.15), rgba(183,148,244,0.1))',
                border: '1px solid var(--border-bright)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <span style={{ fontSize: 28 }}>📊</span>
              </div>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontFamily: 'var(--heading)', fontSize: 18, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 6 }}>Advanced Analytics</div>
                <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>Connect your backend to render live charts, heatmaps, and deep-dive visualizations.</div>
              </div>
              <button onClick={() => setActiveTab('documents')} style={{
                padding: '9px 20px', borderRadius: 10, border: '1px solid var(--border-bright)',
                background: 'rgba(99,179,237,0.08)', color: 'var(--accent-blue)',
                fontSize: 13, fontWeight: 600, cursor: 'pointer',
              }}>Upload Data First</button>
            </div>
          )}

        </main>
      </div>
    </div>
  )
}

