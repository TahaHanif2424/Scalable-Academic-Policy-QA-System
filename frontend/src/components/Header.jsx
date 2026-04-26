import { Bell, Search, Zap } from 'lucide-react';

const tabTitles = {
  dashboard: { title: 'Dashboard', sub: 'Overview of your analytics workspace' },
  documents: { title: 'Documents', sub: 'Manage uploaded files and datasets' },
  chat: { title: 'Ask AI', sub: 'Query your data with natural language' },
  insights: { title: 'Insights', sub: 'Auto-generated analytics and patterns' },
  analytics: { title: 'Analytics', sub: 'Deep-dive visualizations and reports' },
};

export default function Header({ activeTab }) {
  const { title, sub } = tabTitles[activeTab] || tabTitles.dashboard;

  return (
    <header style={{
      height: 64,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '0 28px',
      borderBottom: '1px solid var(--border)',
      background: 'rgba(5,8,22,0.8)',
      backdropFilter: 'blur(20px)',
      position: 'sticky',
      top: 0,
      zIndex: 50,
    }}>
      {/* Left */}
      <div>
        <h1 style={{
          fontFamily: 'var(--heading)', fontSize: 18, fontWeight: 700,
          color: 'var(--text-primary)', letterSpacing: '-0.3px',
          margin: 0,
        }}>{title}</h1>
        <p style={{ fontSize: 11, color: 'var(--text-muted)', margin: 0 }}>{sub}</p>
      </div>

      {/* Right */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        {/* Search Bar */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8,
          padding: '7px 14px',
          background: 'rgba(255,255,255,0.03)',
          border: '1px solid var(--border)',
          borderRadius: 10,
          width: 220,
          transition: 'all 0.2s',
        }}>
          <Search size={13} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
          <input
            placeholder="Search documents..."
            style={{
              background: 'transparent', border: 'none', outline: 'none',
              color: 'var(--text-primary)', fontSize: 13, width: '100%',
            }}
          />
        </div>

        {/* AI Status */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: 6,
          padding: '5px 12px', borderRadius: 20,
          background: 'rgba(99,179,237,0.1)',
          border: '1px solid rgba(99,179,237,0.25)',
          fontSize: 11, color: 'var(--accent-blue)', fontWeight: 600,
        }}>
          <Zap size={11} />
          AI Ready
        </div>

        {/* Bell */}
        <button style={{
          width: 34, height: 34, borderRadius: '50%',
          background: 'rgba(255,255,255,0.04)',
          border: '1px solid var(--border)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: 'var(--text-secondary)',
          position: 'relative',
        }}>
          <Bell size={15} />
          <span style={{
            position: 'absolute', top: 6, right: 6,
            width: 6, height: 6, borderRadius: '50%',
            background: 'var(--accent-pink)',
            boxShadow: '0 0 8px var(--accent-pink)',
          }} />
        </button>
      </div>

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.5; transform: scale(0.8); }
        }
      `}</style>
    </header>
  );
}
