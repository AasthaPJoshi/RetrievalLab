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

export function MetricCard({
  label, value, subtitle, trend, isScore = false,
  icon, delay = 0, size = 'md', accent = 'purple'
}: MetricCardProps) {
  const numValue = typeof value === 'number' ? value : null;
  const displayValue = numValue !== null
    ? (isScore ? formatNumber(numValue) : numValue.toLocaleString())
    : value;

  const valueColor = accent === 'amber' ? 'text-status-warning'
    : accent === 'emerald' ? 'text-status-success'
    : 'text-accent-500';

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.4, ease: [0.16,1,0.3,1] }}
      className="card p-5"
    >
      <div className="flex items-center justify-between mb-3">
        <span className="text-[10px] font-semibold tracking-widest uppercase text-text-secondary">
          {label}
        </span>
        {icon && (
          <div className="w-7 h-7 flex items-center justify-center rounded-sm border"
            style={{ borderColor: 'var(--border)', color: 'var(--accent)' }}>
            {icon}
          </div>
        )}
      </div>

      <div className={cn(
        'tabular-mono font-bold tracking-tight',
        valueColor,
        size === 'lg' ? 'text-4xl' : size === 'md' ? 'text-3xl' : 'text-2xl'
      )}>
        {displayValue}
      </div>

      <div className="flex items-center justify-between mt-2">
        {subtitle && <span className="text-xs text-text-muted">{subtitle}</span>}
        {trend !== undefined && <TrendBadge value={trend} />}
      </div>

      {isScore && numValue !== null && (
        <div className="score-bar mt-3">
          <motion.div
            className="score-bar-fill"
            initial={{ width: 0 }}
            animate={{ width: `${Math.min(numValue * 100, 100)}%` }}
            transition={{ delay: delay + 0.2, duration: 0.8, ease: [0.16,1,0.3,1] }}
          />
        </div>
      )}
    </motion.div>
  );
}

function TrendBadge({ value }: { value: number }) {
  const isUp   = value > 0;
  const isFlat = value === 0;
  const Icon   = isFlat ? Minus : isUp ? TrendingUp : TrendingDown;
  const color  = isFlat ? 'text-text-muted' : isUp ? 'text-status-success' : 'text-status-error';

  return (
    <span className={cn('flex items-center gap-1 text-xs font-medium', color)}>
      <Icon size={9} />
      {Math.abs(value).toFixed(1)}%
    </span>
  );
}

export function MetricCardSkeleton() {
  return (
    <div className="card p-5 space-y-3">
      <div className="flex justify-between">
        <div className="skeleton h-2.5 w-16" />
        <div className="skeleton h-6 w-6" />
      </div>
      <div className="skeleton h-9 w-24" />
      <div className="skeleton h-1 w-full" />
    </div>
  );
}
