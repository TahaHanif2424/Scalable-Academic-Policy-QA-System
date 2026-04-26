import { useState, useRef, useEffect } from 'react';
import {
  Send, Bot, User, Sparkles, Copy, ThumbsUp, ThumbsDown,
  RotateCcw, Lightbulb, Loader2
} from 'lucide-react';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const SUGGESTED_QUESTIONS = [
  'What is the minimum GPA requirement?', 
  'What happens if a student fails a course?', 
  'What is the attendance policy?', 
  'How many times can a course be repeated?',
];

function MessageBubble({ msg, onOpenChunks }) {
  const isUser = msg.role === 'user';
  const [copied, setCopied] = useState(false);
  const hasTopChunks = !isUser && Array.isArray(msg.topChunks) && msg.topChunks.length > 0;

  const copy = () => {
    navigator.clipboard.writeText(msg.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div style={{
      display: 'flex',
      flexDirection: isUser ? 'row-reverse' : 'row',
      gap: 10, alignItems: 'flex-start',
      animation: 'msgIn 0.3s ease',
    }}>
      {/* Avatar */}
      <div style={{
        width: 32, height: 32, borderRadius: '50%', flexShrink: 0,
        background: isUser
          ? 'linear-gradient(135deg, #63b3ed, #b794f4)'
          : 'linear-gradient(135deg, #0a0f2e, #1a1f52)',
        border: isUser ? 'none' : '1px solid var(--border-bright)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        boxShadow: isUser ? '0 0 12px rgba(99,179,237,0.3)' : '0 0 12px rgba(183,148,244,0.2)',
      }}>
        {isUser ? <User size={15} color="#fff" /> : <Bot size={15} color="var(--accent-purple)" />}
      </div>

      <div style={{ maxWidth: '75%', display: 'flex', flexDirection: 'column', gap: 6, alignItems: isUser ? 'flex-end' : 'flex-start' }}>
        <div style={{
          padding: '12px 16px',
          borderRadius: isUser ? '18px 18px 4px 18px' : '18px 18px 18px 4px',
          background: isUser
            ? 'linear-gradient(135deg, rgba(99,179,237,0.2), rgba(183,148,244,0.15))'
            : 'rgba(13,18,52,0.9)',
          border: `1px solid ${isUser ? 'rgba(99,179,237,0.3)' : 'var(--border)'}`,
          fontSize: 13.5, lineHeight: 1.7, color: 'var(--text-primary)',
          whiteSpace: 'pre-wrap',
          boxShadow: isUser ? '0 4px 20px rgba(99,179,237,0.1)' : '0 4px 20px rgba(0,0,0,0.2)',
          cursor: hasTopChunks ? 'pointer' : 'default',
        }}
          onClick={() => {
            if (hasTopChunks) {
              onOpenChunks(msg.topChunks, msg.topK || msg.topChunks.length);
            }
          }}
          title={hasTopChunks ? 'Click to view top chunks' : ''}
        >
          {msg.loading ? (
            <div style={{ display: 'flex', gap: 6, alignItems: 'center', padding: '2px 0' }}>
              {[0, 1, 2].map(i => (
                <div key={i} style={{
                  width: 7, height: 7, borderRadius: '50%',
                  background: 'var(--accent-purple)',
                  animation: `bounce 1.2s ${i * 0.2}s infinite`,
                }} />
              ))}
            </div>
          ) : msg.content}
        </div>

        {/* Actions */}
        {!isUser && !msg.loading && (
          <div style={{ display: 'flex', gap: 4 }}>
            {hasTopChunks && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onOpenChunks(msg.topChunks, msg.topK || msg.topChunks.length);
                }}
                title="View top chunks"
                style={{
                  display: 'flex', alignItems: 'center', gap: 4,
                  padding: '3px 8px', borderRadius: 6,
                  background: 'transparent', border: '1px solid var(--border)',
                  color: 'var(--text-muted)', fontSize: 10, cursor: 'pointer',
                  transition: 'all 0.2s',
                }}
                onMouseEnter={e => { e.currentTarget.style.background = 'rgba(99,179,237,0.08)'; e.currentTarget.style.color = 'var(--accent-blue)'; }}
                onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--text-muted)'; }}
              >
                Top chunks
              </button>
            )}
            {[
              { icon: Copy, label: copied ? 'Copied!' : 'Copy', action: copy },
              { icon: ThumbsUp, label: 'Good', action: () => {} },
              { icon: ThumbsDown, label: 'Bad', action: () => {} },
            ].map(({ icon: Icon, label, action }) => (
              <button
                key={label}
                onClick={(e) => {
                  e.stopPropagation();
                  action();
                }}
                title={label}
                style={{
                display: 'flex', alignItems: 'center', gap: 4,
                padding: '3px 8px', borderRadius: 6,
                background: 'transparent', border: '1px solid var(--border)',
                color: 'var(--text-muted)', fontSize: 10, cursor: 'pointer',
                transition: 'all 0.2s',
              }}
                onMouseEnter={e => { e.currentTarget.style.background = 'rgba(99,179,237,0.08)'; e.currentTarget.style.color = 'var(--accent-blue)'; }}
                onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--text-muted)'; }}
              >
                <Icon size={10} />
                {label}
              </button>
            ))}
          </div>
        )}
      </div>

      <style>{`
        @keyframes msgIn {
          from { opacity: 0; transform: translateY(10px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes bounce {
          0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
          40%            { transform: scale(1);   opacity: 1; }
        }
      `}</style>
    </div>
  );
}

export default function ChatSection({ files }) {
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: "Hello! I'm your Big Data AI assistant. Upload documents or paste text above, then ask me anything about your data. I can summarize, analyze patterns, extract insights, and answer questions based on your content.",
    }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [showSuggestions, setShowSuggestions] = useState(true);
  const [indexedFileKey, setIndexedFileKey] = useState(null);
  const [chunkPopup, setChunkPopup] = useState({ open: false, chunks: [], topK: 0 });
  const bottomRef = useRef(null);
  const textareaRef = useRef(null);
  const hasContent = files.length > 0;

  const currentPdf = files.find((f) => f.type === 'application/pdf' || f.name.toLowerCase().endsWith('.pdf'));
  const currentPdfKey = currentPdf ? `${currentPdf.name}:${currentPdf.size}:${currentPdf.lastModified || 0}` : null;

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const sendMessage = async (text) => {
    const q = (text || input).trim();
    if (!q || isLoading) return;

    if (!currentPdf && !indexedFileKey) {
      setMessages(prev => [
        ...prev,
        { role: 'user', content: q },
        {
          role: 'assistant',
          content: 'Please upload a PDF first. Follow-up questions will work without re-upload once the first PDF is indexed.',
        }
      ]);
      setInput('');
      setShowSuggestions(false);
      return;
    }

    setInput('');
    setShowSuggestions(false);
    setMessages(prev => [...prev, { role: 'user', content: q }]);
    setIsLoading(true);

    const shouldUploadPdf = !!currentPdf && currentPdfKey !== indexedFileKey;

    try {
      const formData = new FormData();
      formData.append('question', q);
      formData.append('top_k', '5');

      if (shouldUploadPdf) {
        formData.append('file', currentPdf);
      }

      const res = await fetch(`${API_BASE_URL}/process`, {
        method: 'POST',
        body: formData,
      });

      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data?.detail || `Request failed (${res.status})`);
      }

      if (shouldUploadPdf) {
        setIndexedFileKey(currentPdfKey);
      }

      const answerText = (data?.answer || '').trim() || 'No answer returned by backend.';
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: answerText,
          topChunks: Array.isArray(data?.top_chunks) ? data.top_chunks : [],
          topK: data?.top_k || 0,
        }
      ]);
    } catch (err) {
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: `Backend error: ${err.message || 'Unknown error'}`,
        }
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const clearChat = () => {
    setMessages([{
      role: 'assistant',
      content: "Chat cleared. Upload new documents or ask a new question!",
    }]);
    setIndexedFileKey(null);
    setShowSuggestions(true);
  };

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', height: '100%',
      background: 'rgba(5,8,22,0.5)', borderRadius: 16,
      border: '1px solid var(--border)', overflow: 'hidden',
    }}>
      {/* Chat Header */}
      <div style={{
        padding: '14px 20px', borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        background: 'rgba(13,18,52,0.5)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            width: 32, height: 32, borderRadius: 10,
            background: 'linear-gradient(135deg, rgba(183,148,244,0.2), rgba(99,179,237,0.1))',
            border: '1px solid rgba(183,148,244,0.3)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Sparkles size={15} style={{ color: 'var(--accent-purple)' }} />
          </div>
          <div>
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>AI Data Assistant</div>
            <div style={{ fontSize: 10, color: hasContent ? 'var(--accent-green)' : 'var(--text-muted)' }}>
              {hasContent ? `${files.length} file(s) + text loaded • Ready` : 'No data loaded yet'}
            </div>
          </div>
        </div>
        <button onClick={clearChat} style={{
          display: 'flex', alignItems: 'center', gap: 5,
          padding: '5px 10px', borderRadius: 8,
          background: 'transparent', border: '1px solid var(--border)',
          color: 'var(--text-muted)', fontSize: 11, cursor: 'pointer',
          transition: 'all 0.2s',
        }}
          onMouseEnter={e => { e.currentTarget.style.color = 'var(--accent-blue)'; e.currentTarget.style.borderColor = 'rgba(99,179,237,0.3)'; }}
          onMouseLeave={e => { e.currentTarget.style.color = 'var(--text-muted)'; e.currentTarget.style.borderColor = 'var(--border)'; }}
        >
          <RotateCcw size={11} /> Clear
        </button>
      </div>

      {/* Messages */}
      <div style={{
        flex: 1, overflowY: 'auto', padding: '20px',
        display: 'flex', flexDirection: 'column', gap: 16,
      }}>
        {messages.map((msg, i) => (
          <MessageBubble
            key={i}
            msg={msg}
            onOpenChunks={(chunks, topK) => setChunkPopup({ open: true, chunks, topK })}
          />
        ))}
        {isLoading && <MessageBubble msg={{ role: 'assistant', loading: true }} />}
        <div ref={bottomRef} />
      </div>

      {/* Suggested Questions */}
      {showSuggestions && (
        <div style={{ padding: '0 20px 14px' }}>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 5 }}>
            <Lightbulb size={11} /> Suggested questions
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {SUGGESTED_QUESTIONS.map(q => (
              <button key={q} onClick={() => sendMessage(q)} style={{
                padding: '5px 12px', borderRadius: 20,
                background: 'rgba(99,179,237,0.06)',
                border: '1px solid var(--border)',
                color: 'var(--text-secondary)', fontSize: 11,
                cursor: 'pointer', transition: 'all 0.2s',
                textAlign: 'left',
              }}
                onMouseEnter={e => { e.currentTarget.style.background = 'rgba(99,179,237,0.12)'; e.currentTarget.style.color = 'var(--accent-blue)'; e.currentTarget.style.borderColor = 'rgba(99,179,237,0.3)'; }}
                onMouseLeave={e => { e.currentTarget.style.background = 'rgba(99,179,237,0.06)'; e.currentTarget.style.color = 'var(--text-secondary)'; e.currentTarget.style.borderColor = 'var(--border)'; }}
              >{q}</button>
            ))}
          </div>
        </div>
      )}

      {/* Input */}
      <div style={{
        padding: '14px 20px',
        borderTop: '1px solid var(--border)',
        background: 'rgba(5,8,22,0.6)',
      }}>
        {!hasContent && (
          <div style={{
            marginBottom: 10, padding: '8px 12px', borderRadius: 8,
            background: 'rgba(246,135,179,0.08)',
            border: '1px solid rgba(246,135,179,0.2)',
            fontSize: 11, color: 'var(--accent-pink)',
            display: 'flex', alignItems: 'center', gap: 6,
          }}>
            ⚠ Upload a PDF first for context-aware answers.
          </div>
        )}
        <div style={{
          display: 'flex', gap: 10, alignItems: 'flex-end',
          background: 'rgba(13,18,52,0.8)',
          border: '1px solid var(--border)',
          borderRadius: 14, padding: '10px 14px',
          transition: 'border-color 0.2s',
        }}
          onFocusCapture={e => e.currentTarget.style.borderColor = 'rgba(99,179,237,0.4)'}
          onBlurCapture={e => e.currentTarget.style.borderColor = 'var(--border)'}
        >
          <textarea
            ref={textareaRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKey}
            placeholder="Ask anything about your data… (Shift+Enter for new line)"
            rows={1}
            style={{
              flex: 1, background: 'transparent', border: 'none', outline: 'none',
              color: 'var(--text-primary)', fontSize: 13.5, resize: 'none',
              lineHeight: 1.6, maxHeight: 120, overflowY: 'auto',
            }}
          />
          <button
            onClick={() => sendMessage()}
            disabled={!input.trim() || isLoading}
            style={{
              width: 36, height: 36, borderRadius: 10, flexShrink: 0,
              background: input.trim() && !isLoading
                ? 'linear-gradient(135deg, #63b3ed, #b794f4)'
                : 'rgba(255,255,255,0.05)',
              border: 'none',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: '#fff', transition: 'all 0.2s',
              boxShadow: input.trim() ? '0 0 20px rgba(99,179,237,0.35)' : 'none',
              cursor: input.trim() && !isLoading ? 'pointer' : 'not-allowed',
              opacity: input.trim() && !isLoading ? 1 : 0.4,
            }}
          >
            {isLoading ? <Loader2 size={15} style={{ animation: 'spin 1s linear infinite' }} /> : <Send size={15} />}
          </button>
        </div>
        <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 6, textAlign: 'center' }}>
          Press Enter to send • Shift+Enter for new line
        </div>
      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>

      {chunkPopup.open && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.55)',
            zIndex: 1000,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 20,
          }}
          onClick={() => setChunkPopup({ open: false, chunks: [], topK: 0 })}
        >
          <div
            style={{
              width: 'min(960px, 95vw)',
              maxHeight: '85vh',
              overflowY: 'auto',
              background: 'rgba(10,14,38,0.98)',
              border: '1px solid var(--border-bright)',
              borderRadius: 14,
              padding: 16,
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <h3 style={{ margin: 0, color: 'var(--text-primary)', fontSize: 16 }}>
                Top {chunkPopup.topK || chunkPopup.chunks.length} Chunks
              </h3>
              <button
                onClick={() => setChunkPopup({ open: false, chunks: [], topK: 0 })}
                style={{
                  border: '1px solid var(--border)',
                  background: 'transparent',
                  color: 'var(--text-muted)',
                  borderRadius: 8,
                  padding: '6px 10px',
                  cursor: 'pointer',
                }}
              >
                Close
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {chunkPopup.chunks.map((chunk, idx) => (
                <div
                  key={`${chunk.chunk_id || 'chunk'}-${idx}`}
                  style={{
                    border: '1px solid var(--border)',
                    borderRadius: 10,
                    padding: 12,
                    background: 'rgba(255,255,255,0.03)',
                  }}
                >
                  <div style={{ fontSize: 12, color: 'var(--accent-blue)', marginBottom: 6 }}>
                    #{idx + 1} • chunk_id: {String(chunk.chunk_id)} • page: {String(chunk.page_num)} • source: {String(chunk.source)} • score: {Number(chunk.score || 0).toFixed(4)}
                  </div>
                  <div style={{ whiteSpace: 'pre-wrap', fontSize: 13, color: 'var(--text-primary)', lineHeight: 1.6 }}>
                    {chunk.text || '[No text available]'}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
