import { motion } from 'framer-motion';
import { Bell, Search, HelpCircle } from 'lucide-react';

interface HeaderProps {
  title:     string;
  subtitle?: string;
}

export function Header({ title, subtitle }: HeaderProps) {
  return (
    <header className="sticky top-0 z-30 flex items-center justify-between px-8 py-4 border-b"
      style={{
        background: 'rgba(7,5,26,0.88)',
        borderColor: 'rgba(124,58,237,0.1)',
        backdropFilter: 'blur(24px)',
      }}>
      {/* Amber shimmer line at bottom */}
      <div className="absolute bottom-0 left-0 right-0 h-px"
        style={{ background: 'linear-gradient(90deg, transparent, rgba(245,158,11,0.15), rgba(124,58,237,0.15), transparent)' }} />

      <motion.div
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, ease: [0.16,1,0.3,1] }}
      >
        <h1 className="text-base font-semibold text-white">{title}</h1>
        {subtitle && (
          <p className="text-xs mt-0.5" style={{ color: 'rgba(139,92,246,0.6)' }}>{subtitle}</p>
        )}
      </motion.div>

      <div className="flex items-center gap-3">
        {/* Search */}
        <div className="relative hidden md:block">
          <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-purple-500/60" />
          <input
            type="text"
            placeholder="Search…"
            className="pl-8 pr-4 py-2 text-xs rounded-lg text-purple-200 placeholder-purple-500/40
                       focus:outline-none transition-all w-48 focus:w-64"
            style={{
              background: 'rgba(124,58,237,0.06)',
              border: '1px solid rgba(124,58,237,0.12)',
            }}
            onFocus={e => { e.target.style.borderColor = 'rgba(124,58,237,0.4)'; e.target.style.boxShadow = '0 0 0 3px rgba(124,58,237,0.08)'; }}
            onBlur={e => { e.target.style.borderColor = 'rgba(124,58,237,0.12)'; e.target.style.boxShadow = 'none'; }}
          />
        </div>

        {/* Notification */}
        <button className="relative w-9 h-9 flex items-center justify-center rounded-lg transition-all"
          style={{ background: 'rgba(124,58,237,0.06)', border: '1px solid rgba(124,58,237,0.12)' }}
          onMouseEnter={e => (e.currentTarget.style.borderColor = 'rgba(124,58,237,0.3)')}
          onMouseLeave={e => (e.currentTarget.style.borderColor = 'rgba(124,58,237,0.12)')}>
          <Bell size={14} className="text-purple-400" />
          <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 rounded-full bg-amber-400" />
        </button>

        {/* Help */}
        <button className="w-9 h-9 flex items-center justify-center rounded-lg transition-all"
          style={{ background: 'rgba(124,58,237,0.06)', border: '1px solid rgba(124,58,237,0.12)' }}
          onMouseEnter={e => (e.currentTarget.style.borderColor = 'rgba(124,58,237,0.3)')}
          onMouseLeave={e => (e.currentTarget.style.borderColor = 'rgba(124,58,237,0.12)')}>
          <HelpCircle size={14} className="text-purple-400" />
        </button>

        {/* Avatar */}
        <motion.div
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.97 }}
          className="w-9 h-9 rounded-lg flex items-center justify-center text-xs font-bold cursor-pointer"
          style={{ background: 'linear-gradient(135deg, #7C3AED, #F59E0B)', color: '#07051A' }}>
          RL
        </motion.div>
      </div>
    </header>
  );
}
