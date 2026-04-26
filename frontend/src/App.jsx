import { useState } from 'react'
import UploadSection from './components/UploadSection'
import ChatSection from './components/ChatSection'
import './App.css'

export default function App() {
  const [files, setFiles] = useState([])
  const hasUploadedFile = files.some(
    (f) => f.type === 'application/pdf' || f.name.toLowerCase().endsWith('.pdf')
  )

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg-primary)', padding: '24px' }}>
      <div style={{ maxWidth: 1100, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 20 }}>
        <div style={{
          borderRadius: 16,
          border: '1px solid var(--border)',
          background: 'var(--bg-card)',
          padding: '20px',
          backdropFilter: 'blur(20px)',
        }}>
          <div style={{ marginBottom: 14 }}>
            <h1 style={{ margin: 0, fontFamily: 'var(--heading)', fontSize: 24, color: 'var(--text-primary)' }}>Policy QA</h1>
            <p style={{ margin: '6px 0 0', fontSize: 12, color: 'var(--text-muted)' }}>
              Upload a PDF to start chatting with your document.
            </p>
          </div>
          <UploadSection
            files={files}
            setFiles={setFiles}
            pastedText=""
            setPastedText={() => {}}
            allowPastedText={false}
          />
        </div>

        {hasUploadedFile ? (
          <div style={{ height: 'calc(100vh - 310px)', minHeight: 460 }}>
            <ChatSection files={files} />
          </div>
        ) : (
          <div style={{
            borderRadius: 14,
            border: '1px dashed var(--border)',
            background: 'rgba(13,18,52,0.35)',
            color: 'var(--text-muted)',
            fontSize: 13,
            padding: '18px',
            textAlign: 'center',
          }}>
            Chat will appear here after you upload a PDF.
          </div>
        )}
      </div>
    </div>
  )
}

