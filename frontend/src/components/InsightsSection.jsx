import { TrendingUp, TrendingDown, Activity, Database, FileText, Zap, BarChart2, PieChart, ArrowUpRight } from 'lucide-react';

const stats = [
  { icon: Database, label: 'Data Points', value: '2.4M', change: '+12.5%', up: true, color: '#63b3ed' },
  { icon: FileText, label: 'Documents', value: '0', change: 'none loaded', up: null, color: '#b794f4' },
  { icon: Activity, label: 'Queries Run', value: '0', change: 'Start asking!', up: null, color: '#76e4f7' },
  { icon: Zap, label: 'Avg Response', value: '1.4s', change: '-0.3s', up: true, color: '#68d391' },
];

const insights = [
  { title: 'Data Density Analysis', desc: 'Upload documents to detect high-density information clusters automatically.', tag: 'Pattern Recognition', color: '#63b3ed' },
  { title: 'Sentiment Distribution', desc: 'NLP sentiment analysis will map positive, neutral, and negative signals across your corpus.', tag: 'NLP', color: '#b794f4' },
  { title: 'Keyword Extraction', desc: 'Top-N keywords, bigrams, and named entities will surface once your data is loaded.', tag: 'Text Mining', color: '#76e4f7' },
  { title: 'Statistical Summary', desc: 'Auto-generated descriptive stats: mean, median, std deviation on any numeric data.', tag: 'Statistics', color: '#68d391' },
];

const activities = [
  { text: 'System initialized', time: 'just now', color: '#68d391' },
  { text: 'AI model loaded', time: '2s ago', color: '#63b3ed' },
  { text: 'Awaiting document upload', time: '', color: '#b794f4' },
];

function StatCard({ icon: Icon, label, value, change, up, color }) {
  return (
    <div style={{
      padding: '20px', borderRadius: 16,
      background: 'var(--bg-card)',
      border: '1px solid var(--border)',
      backdropFilter: 'blur(10px)',
      display: 'flex', flexDirection: 'column', gap: 12,
      transition: 'transform 0.2s, box-shadow 0.2s',
      cursor: 'default',
    }}
      onMouseEnter={e => { e.currentTarget.style.transform = 'translateY(-2px)'; e.currentTarget.style.boxShadow = `0 8px 30px ${color}20`; }}
      onMouseLeave={e => { e.currentTarget.style.transform = 'translateY(0)'; e.currentTarget.style.boxShadow = 'none'; }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div style={{
          width: 38, height: 38, borderRadius: 10,
          background: `${color}18`,
          border: `1px solid ${color}30`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Icon size={17} style={{ color }} />
        </div>
        {up !== null && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 3,
            fontSize: 11, color: up ? '#68d391' : '#fc8181', fontWeight: 600,
          }}>
            {up ? <TrendingUp size={11} /> : <TrendingDown size={11} />}
            {change}
          </div>
        )}
      </div>
      <div>
        <div style={{ fontSize: 26, fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'var(--heading)', letterSpacing: '-0.5px' }}>{value}</div>
        <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>{label}</div>
        {up === null && <div style={{ fontSize: 10, color: color, marginTop: 3 }}>{change}</div>}
      </div>
    </div>
  );
}

function InsightCard({ title, desc, tag, color }) {
  return (
    <div style={{
      padding: '18px', borderRadius: 14,
      background: 'rgba(13,18,52,0.6)',
      border: '1px solid var(--border)',
      display: 'flex', flexDirection: 'column', gap: 10,
      transition: 'all 0.2s', cursor: 'default',
    }}
      onMouseEnter={e => { e.currentTarget.style.borderColor = `${color}40`; e.currentTarget.style.background = `rgba(13,18,52,0.85)`; }}
      onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.background = 'rgba(13,18,52,0.6)'; }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{
          fontSize: 10, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase',
          color, padding: '3px 8px', borderRadius: 20,
          background: `${color}12`, border: `1px solid ${color}25`,
        }}>{tag}</span>
        <ArrowUpRight size={13} style={{ color: 'var(--text-muted)' }} />
      </div>
      <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'var(--heading)' }}>{title}</div>
      <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6 }}>{desc}</div>
    </div>
  );
}

// Fake bar chart visual
function MiniBarChart() {
  const bars = [40, 65, 45, 80, 55, 90, 70, 85, 60, 95, 75, 88];
  return (
    <div style={{
      padding: '20px', borderRadius: 16,
      background: 'var(--bg-card)', border: '1px solid var(--border)',
      backdropFilter: 'blur(10px)',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <div>
          <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'var(--heading)' }}>Data Volume Over Time</div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Simulated — connect real data</div>
        </div>
        <BarChart2 size={16} style={{ color: 'var(--accent-blue)' }} />
      </div>
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 6, height: 80 }}>
        {bars.map((h, i) => (
          <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
            <div style={{
              width: '100%',
              height: `${h}%`,
              borderRadius: '3px 3px 0 0',
              background: `linear-gradient(180deg, ${i % 2 === 0 ? '#63b3ed' : '#b794f4'}, transparent)`,
              transition: 'height 0.4s ease',
            }} />
          </div>
        ))}
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8 }}>
        {['Jan', 'Mar', 'May', 'Jul', 'Sep', 'Nov'].map(m => (
          <span key={m} style={{ fontSize: 9, color: 'var(--text-muted)' }}>{m}</span>
        ))}
      </div>
    </div>
  );
}

// Fake donut chart
function MiniDonut() {
  const segments = [
    { pct: 40, color: '#63b3ed', label: 'Structured' },
    { pct: 35, color: '#b794f4', label: 'Unstructured' },
    { pct: 25, color: '#76e4f7', label: 'Semi-struct.' },
  ];
  return (
    <div style={{
      padding: '20px', borderRadius: 16,
      background: 'var(--bg-card)', border: '1px solid var(--border)',
      backdropFilter: 'blur(10px)',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div>
          <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'var(--heading)' }}>Data Type Distribution</div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>By category</div>
        </div>
        <PieChart size={16} style={{ color: 'var(--accent-purple)' }} />
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
        {/* Fake donut using conic-gradient */}
        <div style={{
          width: 80, height: 80, borderRadius: '50%', flexShrink: 0,
          background: 'conic-gradient(#63b3ed 0% 40%, #b794f4 40% 75%, #76e4f7 75% 100%)',
          boxShadow: '0 0 20px rgba(99,179,237,0.2)',
          position: 'relative',
        }}>
          <div style={{
            position: 'absolute', top: '50%', left: '50%',
            transform: 'translate(-50%,-50%)',
            width: 46, height: 46, borderRadius: '50%',
            background: 'var(--bg-secondary)',
          }} />
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {segments.map(s => (
            <div key={s.label} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div style={{ width: 8, height: 8, borderRadius: 2, background: s.color, flexShrink: 0 }} />
              <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{s.label}</span>
              <span style={{ fontSize: 11, fontWeight: 600, color: s.color, marginLeft: 'auto' }}>{s.pct}%</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function InsightsSection({ files, pastedText }) {
  const fileCount = files.length;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Charts Row */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
        <MiniBarChart />
        <MiniDonut />
      </div>

      {/* Activity Feed */}
      <div style={{
        padding: '18px', borderRadius: 16,
        background: 'var(--bg-card)', border: '1px solid var(--border)',
        backdropFilter: 'blur(10px)',
      }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'var(--heading)', marginBottom: 14, display: 'flex', alignItems: 'center', gap: 6 }}>
          <Activity size={14} style={{ color: 'var(--accent-blue)' }} />
          Live Activity
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {[
            ...activities,
            ...(fileCount > 0 ? [{ text: `${fileCount} file(s) uploaded and indexed`, time: 'just now', color: '#f6ad55' }] : []),
          ].map((a, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div style={{ width: 6, height: 6, borderRadius: '50%', background: a.color, flexShrink: 0, boxShadow: `0 0 8px ${a.color}` }} />
              <span style={{ fontSize: 12, color: 'var(--text-secondary)', flex: 1 }}>{a.text}</span>
              {a.time && <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>{a.time}</span>}
            </div>
          ))}
        </div>
      </div>

      {/* Auto-insights Grid */}
      <div>
        <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'var(--heading)', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
          <Zap size={14} style={{ color: 'var(--accent-purple)' }} />
          Available Analytics Capabilities
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          {insights.map((ins, i) => <InsightCard key={i} {...ins} />)}
        </div>
      </div>
    </div>
  );
}
