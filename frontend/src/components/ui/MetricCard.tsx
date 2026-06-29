import { motion } from 'framer-motion';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { cn, formatNumber } from '@/lib/utils';

interface MetricCardProps {
  label:      string;
  value:      number | string;
  subtitle?:  string;
  trend?:     number;
  isScore?:   boolean;
  icon?:      React.ReactNode;
  delay?:     number;
  size?:      'sm' | 'md' | 'lg';
  accent?:    'purple' | 'amber' | 'emerald';
}

const ACCENT_MAP = {
  purple: {
    value:  'text-purple-300',
    glow:   'rgba(124,58,237,0.2)',
    border: 'rgba(124,58,237,0.2)',
    bar:    'linear-gradient(90deg, #F59E0B 0%, #8B5CF6 60%, #7C3AED 100%)',
    icon:   'bg-purple-500/10 border-purple-500/20 text-purple-300',
    orb:    'rgba(124,58,237,0.15)',
  },
  amber: {
    value:  'text-amber-400',
    glow:   'rgba(245,158,11,0.2)',
    border: 'rgba(245,158,11,0.2)',
    bar:    'linear-gradient(90deg, #F59E0B, #FBBF24)',
    icon:   'bg-amber-500/10 border-amber-500/20 text-amber-400',
    orb:    'rgba(245,158,11,0.1)',
  },
  emerald: {
    value:  'text-emerald-400',
    glow:   'rgba(16,185,129,0.15)',
    border: 'rgba(16,185,129,0.2)',
    bar:    'linear-gradient(90deg, #10B981, #34D399)',
    icon:   'bg-emerald-500/10 border-emerald-500/20 text-emerald-400',
    orb:    'rgba(16,185,129,0.1)',
  },
};

export function MetricCard({
  label, value, subtitle, trend, isScore = false,
  icon, delay = 0, size = 'md', accent = 'purple'
}: MetricCardProps) {
  const numValue = typeof value === 'number' ? value : null;
  const displayValue = numValue !== null
    ? (isScore ? formatNumber(numValue) : numValue.toLocaleString())
    : value;

  const a = ACCENT_MAP[accent];

  return (
    <motion.div
      initial={{ opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.5, ease: [0.16,1,0.3,1] }}
      whileHover={{ y: -2, transition: { duration: 0.2 } }}
      className="glass-card p-5 group relative overflow-hidden"
      style={{ '--accent-border': a.border } as any}
    >
      {/* Corner orb */}
      <div className="absolute top-0 right-0 w-28 h-28 pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity duration-500 rounded-full"
        style={{
          background: `radial-gradient(circle at top right, ${a.orb} 0%, transparent 70%)`,
          filter: 'blur(20px)',
        }} />

      {/* Hover border glow */}
      <div className="absolute inset-0 rounded-xl opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none"
        style={{ boxShadow: `inset 0 0 0 1px ${a.border}` }} />

      <div className="relative z-10">
        {/* Label + icon */}
        <div className="flex items-center justify-between mb-3">
          <span className="text-[10px] font-semibold tracking-widest uppercase"
            style={{ color: 'rgba(139,92,246,0.55)' }}>
            {label}
          </span>
          {icon && (
            <div className={cn(
              'w-7 h-7 flex items-center justify-center rounded-lg border',
              a.icon
            )}>
              {icon}
            </div>
          )}
        </div>

        {/* Value */}
        <div className={cn(
          'font-bold tracking-tight tabular-nums',
          a.value,
          size === 'lg' ? 'text-4xl' : size === 'md' ? 'text-3xl' : 'text-2xl'
        )}>
          {displayValue}
        </div>

        {/* Subtitle + trend */}
        <div className="flex items-center justify-between mt-2">
          {subtitle && (
            <span className="text-xs" style={{ color: 'rgba(139,92,246,0.5)' }}>{subtitle}</span>
          )}
          {trend !== undefined && <TrendBadge value={trend} />}
        </div>

        {/* Score progress bar */}
        {isScore && numValue !== null && (
          <motion.div className="mt-3 h-1 rounded-full overflow-hidden bg-white/5">
            <motion.div
              className="h-full rounded-full"
              style={{ background: a.bar }}
              initial={{ width: 0 }}
              animate={{ width: `${Math.min(numValue * 100, 100)}%` }}
              transition={{ delay: delay + 0.25, duration: 0.9, ease: [0.16,1,0.3,1] }}
            />
          </motion.div>
        )}
      </div>
    </motion.div>
  );
}

function TrendBadge({ value }: { value: number }) {
  const isUp   = value > 0;
  const isFlat = value === 0;
  const Icon   = isFlat ? Minus : isUp ? TrendingUp : TrendingDown;
  const color  = isFlat ? 'rgba(139,92,246,0.5)' : isUp ? '#10B981' : '#EF4444';
  const bg     = isFlat ? 'rgba(124,58,237,0.08)' : isUp ? 'rgba(16,185,129,0.1)' : 'rgba(239,68,68,0.1)';

  return (
    <span className="flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium"
      style={{ background: bg, color }}>
      <Icon size={9} />
      {Math.abs(value).toFixed(1)}%
    </span>
  );
}

export function MetricCardSkeleton() {
  return (
    <div className="glass-card p-5 space-y-3">
      <div className="flex justify-between">
        <div className="skeleton h-2.5 w-16 rounded" />
        <div className="skeleton h-6 w-6 rounded-lg" />
      </div>
      <div className="skeleton h-9 w-24 rounded" />
      <div className="skeleton h-1 w-full rounded-full" />
    </div>
  );
}
