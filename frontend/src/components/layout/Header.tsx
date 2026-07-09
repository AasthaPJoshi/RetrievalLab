import { Bell, Search } from 'lucide-react';

interface HeaderProps {
  title:     string;
  subtitle?: string;
}

export function Header({ title, subtitle }: HeaderProps) {
  return (
    <header className="sticky top-0 z-30 flex items-center justify-between px-8 py-4 border-b"
      style={{ background: 'rgba(255,255,255,0.9)', backdropFilter: 'blur(4px)', borderColor: 'var(--border)' }}>
      <div>
        <h1 className="text-base font-semibold text-text-primary font-display">{title}</h1>
        {subtitle && (
          <p className="text-xs mt-0.5 text-text-muted">{subtitle}</p>
        )}
      </div>

      <div className="flex items-center gap-3">
        <div className="relative hidden md:block">
          <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
          <input
            type="text"
            placeholder="Search…"
            className="pl-8 pr-4 py-2 text-xs rounded-sm text-text-secondary placeholder-text-muted
                       focus:outline-none transition-colors w-48 focus:w-64 focus:border-accent-500 border"
            style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}
          />
        </div>

        <button className="relative w-8 h-8 flex items-center justify-center rounded-sm border transition-colors"
          style={{ borderColor: 'var(--border)' }}>
          <Bell size={14} className="text-text-secondary" />
          <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 rounded-full bg-accent-500" />
        </button>

        <div className="w-8 h-8 rounded-sm flex items-center justify-center text-xs font-bold font-mono"
          style={{ background: 'var(--accent)', color: '#fff' }}>
          RL
        </div>
      </div>
    </header>
  );
}
