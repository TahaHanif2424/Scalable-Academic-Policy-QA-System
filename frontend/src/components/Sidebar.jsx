import {
  Database, BarChart3, Brain, FileText, MessageSquare,
  Zap, Activity, Home, ChevronRight, Settings, HelpCircle
} from 'lucide-react';

const navItems = [
  { icon: Home, label: 'Dashboard', id: 'dashboard' },
  { icon: FileText, label: 'Documents', id: 'documents' },
  { icon: MessageSquare, label: 'Ask AI', id: 'chat' },
];

const bottomItems = [
  { icon: Settings, label: 'Settings', id: 'settings' },
  { icon: HelpCircle, label: 'Help', id: 'help' },
];

export default function Sidebar({ activeTab, onTabChange }) {
  return (
    <aside style={{
      width: 220,
      minHeight: '100vh',
      background: 'rgba(5, 8, 22, 0.95)',
      borderRight: '1px solid var(--border)',
      display: 'flex',
      flexDirection: 'column',
      padding: '24px 0',
      position: 'fixed',
      left: 0, top: 0, bottom: 0,
      zIndex: 100,
      backdropFilter: 'blur(20px)',
    }}>
      {/* Logo */}
      <div style={{ padding: '0 20px 28px', borderBottom: '1px solid var(--border)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            width: 36, height: 36,
            borderRadius: 10,
            background: 'linear-gradient(135deg, #63b3ed, #b794f4)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 0 20px rgba(99,179,237,0.4)',
          }}>
            <Database size={18} color="#fff" />
          </div>
          <div>
            <div style={{ fontFamily: 'var(--heading)', fontWeight: 700, fontSize: 15, color: 'var(--text-primary)', letterSpacing: '-0.3px' }}>DataMind</div>
            <div style={{ fontSize: 10, color: 'var(--text-muted)', letterSpacing: '0.05em', textTransform: 'uppercase' }}>Big Data Analytics</div>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav style={{ flex: 1, padding: '16px 12px', display: 'flex', flexDirection: 'column', gap: 4 }}>
        {navItems.map(({ icon: Icon, label, id }) => {
          const active = activeTab === id;
          return (
            <button
              key={id}
              onClick={() => onTabChange(id)}
              style={{
                display: 'flex', alignItems: 'center', gap: 10,
                padding: '10px 12px', borderRadius: 10,
                border: 'none',
                background: active
                  ? 'linear-gradient(135deg, rgba(99,179,237,0.15), rgba(183,148,244,0.1))'
                  : 'transparent',
                borderLeft: active ? '2px solid var(--accent-blue)' : '2px solid transparent',
                color: active ? 'var(--accent-blue)' : 'var(--text-secondary)',
                fontSize: 13, fontWeight: active ? 600 : 400,
                cursor: 'pointer',
                transition: 'all 0.2s',
                textAlign: 'left',
                position: 'relative',
                overflow: 'hidden',
              }}
              onMouseEnter={e => { if (!active) e.currentTarget.style.background = 'rgba(99,179,237,0.05)'; e.currentTarget.style.color = '#e2e8f0'; }}
              onMouseLeave={e => { if (!active) { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--text-secondary)'; }}}
            >
              <Icon size={16} />
              <span style={{ flex: 1 }}>{label}</span>
              {active && <ChevronRight size={13} style={{ opacity: 0.6 }} />}
            </button>
          );
        })}
      </nav>

    </aside>
  );
}
