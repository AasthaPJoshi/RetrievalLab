import { Link, useLocation } from 'react-router-dom';
import {
  LayoutDashboard, Database, Search, FlaskConical,
  Shield, Activity, Brain, BookOpen,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import logo from '@/assets/logo.svg';

const NAV = [
  { label: 'CORE', items: [
    { path: '/',            label: 'Dashboard',   icon: LayoutDashboard, badge: null },
    { path: '/corpus',      label: 'Corpora',     icon: Database,        badge: null },
    { path: '/retrieve',    label: 'Retrieval',   icon: Search,          badge: null },
    { path: '/agent',       label: 'AI Agent',    icon: Brain,           badge: 'NEW' },
  ]},
  { label: 'EVALUATION', items: [
    { path: '/eval',        label: 'Eval Engine', icon: FlaskConical,    badge: null },
    { path: '/adversarial', label: 'Adversarial', icon: Shield,          badge: null },
  ]},
  { label: 'OBSERVE', items: [
    { path: '/metrics',     label: 'Metrics',     icon: Activity,        badge: null },
    { path: '/docs',        label: 'API Docs',    icon: BookOpen,        badge: null },
  ]},
];

export function Sidebar() {
  const { pathname } = useLocation();

  return (
    <aside className="fixed left-0 top-0 h-screen w-64 z-40 flex flex-col border-r"
      style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>

      {/* Logo */}
      <div className="px-5 pt-6 pb-5 border-b" style={{ borderColor: 'var(--border)' }}>
        <Link to="/" className="flex items-center gap-3">
          <div className="w-8 h-8 flex items-center justify-center shrink-0 border rounded-sm"
            style={{ borderColor: 'var(--border)' }}>
            <img src={logo} alt="" width={22} height={22} />
          </div>
          <div>
            <div className="text-sm font-semibold text-text-primary font-display">RetrievalLab</div>
            <div className="text-[10px] font-mono tracking-widest uppercase text-text-muted">
              v0.1.0 · research
            </div>
          </div>
        </Link>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-5 overflow-y-auto no-scrollbar space-y-5">
        {NAV.map((section) => (
          <div key={section.label}>
            <div className="px-3 mb-2 text-[10px] font-semibold tracking-widest uppercase text-text-muted">
              {section.label}
            </div>
            <ul className="space-y-0.5">
              {section.items.map((item) => {
                const active = pathname === item.path ||
                  (item.path !== '/' && pathname.startsWith(item.path));
                const Icon = item.icon;
                return (
                  <li key={item.path}>
                    <Link to={item.path} className={cn('nav-item', active && 'active')}>
                      <Icon size={15} className="shrink-0" />
                      <span className="flex-1">{item.label}</span>
                      {item.badge && (
                        <span className="px-1.5 py-0.5 text-[9px] font-semibold rounded-sm"
                          style={{ background: 'rgba(124,58,237,0.15)', color: '#A78BFA' }}>
                          {item.badge}
                        </span>
                      )}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>

      {/* System status */}
      <div className="px-4 py-4 border-t" style={{ borderColor: 'var(--border)' }}>
        <div className="text-[10px] font-semibold tracking-widest uppercase mb-3 text-text-muted">
          System Status
        </div>
        {[
          { label: 'API Server',   ok: true },
          { label: 'PostgreSQL',   ok: true },
          { label: 'Vector Index', ok: true },
        ].map(({ label, ok }) => (
          <div key={label} className="flex items-center justify-between mb-1.5">
            <span className="text-xs text-text-secondary">{label}</span>
            <div className="flex items-center gap-1.5">
              <div className={cn('w-1.5 h-1.5 rounded-full', ok ? 'bg-status-success' : 'bg-status-error')} />
              <span className="text-[10px] font-medium font-mono" style={{ color: ok ? '#22C55E' : '#EF4444' }}>
                {ok ? 'online' : 'offline'}
              </span>
            </div>
          </div>
        ))}
      </div>
    </aside>
  );
}
