import { useState, useRef, useCallback } from 'react';
import {
  Upload, FileText, X, CheckCircle, AlertCircle,
  FileType, Loader2, Type, Plus
} from 'lucide-react';

function FileCard({ file, onRemove }) {
  const ext = file.name.split('.').pop().toUpperCase();
  const size = file.size < 1024 * 1024
    ? `${(file.size / 1024).toFixed(1)} KB`
    : `${(file.size / (1024 * 1024)).toFixed(2)} MB`;

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 12,
      padding: '12px 16px',
      background: 'rgba(99,179,237,0.05)',
      border: '1px solid var(--border)',
      borderRadius: 10,
      animation: 'slideIn 0.3s ease',
    }}>
      <div style={{
        width: 38, height: 38, borderRadius: 8, flexShrink: 0,
        background: ext === 'PDF'
          ? 'linear-gradient(135deg, rgba(246,135,179,0.2), rgba(246,135,179,0.05))'
          : 'linear-gradient(135deg, rgba(99,179,237,0.2), rgba(99,179,237,0.05))',
        border: `1px solid ${ext === 'PDF' ? 'rgba(246,135,179,0.3)' : 'rgba(99,179,237,0.3)'}`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 9, fontWeight: 700, letterSpacing: '0.05em',
        color: ext === 'PDF' ? 'var(--accent-pink)' : 'var(--accent-blue)',
      }}>{ext}</div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{file.name}</div>
        <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{size}</div>
      </div>
      <CheckCircle size={15} style={{ color: 'var(--accent-green)', flexShrink: 0 }} />
      <button onClick={() => onRemove(file.name)} style={{
        background: 'transparent', border: 'none', color: 'var(--text-muted)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        borderRadius: 6, padding: 4, flexShrink: 0,
        transition: 'color 0.2s',
      }}
        onMouseEnter={e => e.currentTarget.style.color = 'var(--accent-pink)'}
        onMouseLeave={e => e.currentTarget.style.color = 'var(--text-muted)'}
      >
        <X size={14} />
      </button>
    </div>
  );
}

export default function UploadSection({ files, setFiles, pastedText, setPastedText }) {
  const [dragging, setDragging] = useState(false);
  const [showTextInput, setShowTextInput] = useState(false);
  const fileInputRef = useRef(null);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setDragging(false);
    const dropped = Array.from(e.dataTransfer.files).filter(f =>
      f.type === 'application/pdf' || f.type === 'text/plain' || f.name.endsWith('.txt') || f.name.endsWith('.pdf')
    );
    setFiles(prev => {
      const names = new Set(prev.map(f => f.name));
      return [...prev, ...dropped.filter(f => !names.has(f.name))];
    });
  }, [setFiles]);

  const handleFileInput = (e) => {
    const selected = Array.from(e.target.files);
    setFiles(prev => {
      const names = new Set(prev.map(f => f.name));
      return [...prev, ...selected.filter(f => !names.has(f.name))];
    });
  };

  const removeFile = (name) => setFiles(prev => prev.filter(f => f.name !== name));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Drop Zone */}
      <div
        onDragOver={e => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current.click()}
        style={{
          borderRadius: 16,
          border: `2px dashed ${dragging ? 'var(--accent-blue)' : 'var(--border)'}`,
          background: dragging
            ? 'rgba(99,179,237,0.08)'
            : 'rgba(255,255,255,0.02)',
          padding: '36px 24px',
          textAlign: 'center',
          cursor: 'pointer',
          transition: 'all 0.25s',
          boxShadow: dragging ? '0 0 30px rgba(99,179,237,0.15) inset' : 'none',
        }}
      >
        <div style={{
          width: 56, height: 56, borderRadius: 16,
          background: 'linear-gradient(135deg, rgba(99,179,237,0.15), rgba(183,148,244,0.1))',
          border: '1px solid var(--border-bright)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          margin: '0 auto 16px',
          boxShadow: '0 0 24px rgba(99,179,237,0.2)',
        }}>
          <Upload size={24} style={{ color: 'var(--accent-blue)' }} />
        </div>
        <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 6, fontFamily: 'var(--heading)' }}>
          Drop files here or click to upload
        </div>
        <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
          Supports PDF, TXT — up to 100 MB per file
        </div>
        <div style={{
          display: 'inline-flex', alignItems: 'center', gap: 6,
          marginTop: 14, padding: '6px 16px',
          background: 'rgba(99,179,237,0.1)',
          border: '1px solid rgba(99,179,237,0.25)',
          borderRadius: 20, fontSize: 12, color: 'var(--accent-blue)',
        }}>
          <FileType size={12} />
          Browse Files
        </div>
        <input ref={fileInputRef} type="file" accept=".pdf,.txt,text/plain,application/pdf" multiple style={{ display: 'none' }} onChange={handleFileInput} />
      </div>

      {/* Paste Text Toggle */}
      <button
        onClick={() => setShowTextInput(v => !v)}
        style={{
          display: 'flex', alignItems: 'center', gap: 8,
          padding: '10px 16px', borderRadius: 10,
          background: showTextInput ? 'rgba(183,148,244,0.1)' : 'rgba(255,255,255,0.02)',
          border: `1px solid ${showTextInput ? 'rgba(183,148,244,0.35)' : 'var(--border)'}`,
          color: showTextInput ? 'var(--accent-purple)' : 'var(--text-secondary)',
          fontSize: 13, fontWeight: 500, transition: 'all 0.2s',
        }}
      >
        <Type size={14} />
        {showTextInput ? 'Hide text input' : 'Paste large text directly'}
        <Plus size={13} style={{ marginLeft: 'auto', transform: showTextInput ? 'rotate(45deg)' : 'none', transition: 'transform 0.2s' }} />
      </button>

      {showTextInput && (
        <div style={{ animation: 'slideIn 0.3s ease' }}>
          <textarea
            value={pastedText}
            onChange={e => setPastedText(e.target.value)}
            placeholder="Paste your large text, research paper, dataset description, or any content here..."
            style={{
              width: '100%',
              minHeight: 160,
              background: 'rgba(255,255,255,0.02)',
              border: '1px solid var(--border)',
              borderRadius: 12,
              padding: '14px 16px',
              color: 'var(--text-primary)',
              fontSize: 13,
              lineHeight: 1.7,
              resize: 'vertical',
              outline: 'none',
              transition: 'border-color 0.2s',
            }}
            onFocus={e => e.target.style.borderColor = 'rgba(183,148,244,0.4)'}
            onBlur={e => e.target.style.borderColor = 'var(--border)'}
          />
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8, fontSize: 11, color: 'var(--text-muted)' }}>
            <span>{pastedText.length.toLocaleString()} characters</span>
            {pastedText.length > 0 && (
              <button onClick={() => setPastedText('')} style={{ background: 'none', border: 'none', color: 'var(--accent-pink)', fontSize: 11, cursor: 'pointer' }}>
                Clear
              </button>
            )}
          </div>
        </div>
      )}

      {/* File List */}
      {files.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 600, letterSpacing: '0.05em', textTransform: 'uppercase', marginBottom: 4 }}>
            {files.length} document{files.length !== 1 ? 's' : ''} loaded
          </div>
          {files.map(f => <FileCard key={f.name} file={f} onRemove={removeFile} />)}
        </div>
      )}

      <style>{`
        @keyframes slideIn {
          from { opacity: 0; transform: translateY(-8px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
}
