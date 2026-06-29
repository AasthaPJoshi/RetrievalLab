import { Link, useLocation } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  LayoutDashboard, Database, Search, FlaskConical,
  Shield, Activity, Brain, Zap, BarChart3, BookOpen, ChevronRight
} from 'lucide-react';
import { cn } from '@/lib/utils';

const NAV = [
  { label: 'CORE', items: [
    { path: '/',            label: 'Dashboard',   icon: LayoutDashboard, badge: null },
    { path: '/corpus',      label: 'Corpora',     icon: Database,        badge: null },
    { path: '/retrieve',    label: 'Retrieval',   icon: Search,          badge: null },
    { path: '/agent',       label: 'AI Agent',    icon: Brain,           badge: 'NEW' },
  ]},
  { label: 'EVALUATION', items: [
    { path: '/eval',        label: 'Eval Engine', icon: FlaskConical,    badge: null },
    { path: '/benchmarks',  label: 'Benchmarks',  icon: BarChart3,       badge: null },
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
    <aside className="fixed left-0 top-0 h-screen w-64 z-40 flex flex-col"
      style={{
        background: 'linear-gradient(180deg, #1E1450 0%, #130D2E 100%)',
        borderRight: '1px solid rgba(167,139,250,0.15)',
      }}>

      {/* Grid overlay */}
      <div className="absolute inset-0 pointer-events-none opacity-30"
        style={{
          backgroundImage: 'radial-gradient(circle, rgba(196,181,253,0.15) 1px, transparent 1px)',
          backgroundSize: '28px 28px',
        }} />

      {/* Top shimmer line — amber to purple */}
      <div className="absolute top-0 left-0 right-0 h-px"
        style={{ background: 'linear-gradient(90deg, transparent, #F59E0B, #9D6EF8, transparent)' }} />

      {/* Purple glow orb */}
      <div className="absolute top-0 left-0 w-48 h-48 rounded-full pointer-events-none opacity-40"
        style={{
          background: 'radial-gradient(circle, rgba(124,58,237,0.3) 0%, transparent 70%)',
          filter: 'blur(30px)',
          animation: 'orb-move 10s ease-in-out infinite alternate',
        }} />

      {/* Logo */}
      <div className="relative z-10 px-5 pt-6 pb-5"
        style={{ borderBottom: '1px solid rgba(167,139,250,0.12)' }}>
        <Link to="/" className="flex items-center gap-3">
          <div className="relative w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
            style={{
              background: 'linear-gradient(135deg, rgba(124,58,237,0.35), rgba(91,33,182,0.2))',
              border: '1px solid rgba(167,139,250,0.4)',
              boxShadow: '0 0 20px rgba(124,58,237,0.4)',
            }}>
            <Zap size={18} style={{ color: '#C4B5FD' }} />
          </div>
          <div>
            <div className="text-sm font-bold text-white">RetrievalLab</div>
            <div className="text-[10px] font-mono tracking-widest uppercase"
              style={{ color: '#F59E0B' }}>
              v0.1.0 · Research
            </div>
          </div>
        </Link>
      </div>

      {/* Nav */}
      <nav className="relative z-10 flex-1 px-3 py-5 overflow-y-auto no-scrollbar space-y-5">
        {NAV.map((section) => (
          <div key={section.label}>
            <div className="px-3 mb-2 text-[10px] font-bold tracking-widest uppercase"
              style={{ color: 'rgba(167,139,250,0.4)' }}>
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
                      {active && (
                        <motion.div layoutId="nav-pill"
                          className="absolute inset-0 rounded-xl"
                          style={{ background: 'rgba(124,58,237,0.15)' }}
                          transition={{ type: 'spring', bounce: 0.2, duration: 0.4 }} />
                      )}
                      <Icon size={15} className="shrink-0 relative"
                        style={{ color: active ? '#C4B5FD' : 'rgba(167,139,250,0.45)' }} />
                      <span className="relative flex-1">{item.label}</span>
                      {item.badge && (
                        <span className="relative px-1.5 py-0.5 text-[10px] font-bold rounded-md"
                          style={{ background: 'linear-gradient(135deg,#F59E0B,#D97706)', color: '#1a0f3d' }}>
                          {item.badge}
                        </span>
                      )}
                      {active && <ChevronRight size={11} className="relative" style={{ color: '#9D6EF8' }} />}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>

      {/* System status */}
      <div className="relative z-10 px-4 py-4"
        style={{ borderTop: '1px solid rgba(167,139,250,0.1)' }}>
        <div className="text-[10px] font-bold tracking-widest uppercase mb-3"
          style={{ color: 'rgba(167,139,250,0.4)' }}>System Status</div>
        {[
          { label: 'API Server',   ok: true },
          { label: 'PostgreSQL',   ok: true },
          { label: 'Vector Index', ok: true },
        ].map(({ label, ok }) => (
          <div key={label} className="flex items-center justify-between mb-1.5">
            <span className="text-xs" style={{ color: 'rgba(167,139,250,0.5)' }}>{label}</span>
            <div className="flex items-center gap-1.5">
              <div className={cn('w-1.5 h-1.5 rounded-full', ok ? 'bg-emerald-400 animate-pulse' : 'bg-red-400')} />
              <span className="text-[10px] font-medium" style={{ color: ok ? '#34D399' : '#F87171' }}>
                {ok ? 'online' : 'offline'}
              </span>
            </div>
          </div>
        ))}
        {/* Amber sparkle line */}
        <div className="mt-3 h-px"
          style={{ background: 'linear-gradient(90deg, transparent, rgba(245,158,11,0.4), transparent)' }} />
      </div>
    </aside>
  );
}
