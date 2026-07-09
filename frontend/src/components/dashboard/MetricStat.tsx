import { CountUp } from '@/components/ui/CountUp';

interface MetricStatProps {
  label: string;
  value: number;
  decimals?: number;
  prefix?: string;
  suffix?: string;
  sub?: string;
  accent?: boolean;
}

export function MetricStat({ label, value, decimals = 0, prefix = '', suffix = '', sub, accent }: MetricStatProps) {
  return (
    <div className="card p-5">
      <div className="text-[10px] font-medium tracking-widest uppercase text-text-muted mb-2">
        {label}
      </div>
      <div className={`tabular-mono text-3xl font-semibold ${accent ? 'text-accent-400' : 'text-text-primary'}`}>
        <CountUp value={value} decimals={decimals} prefix={prefix} suffix={suffix} />
      </div>
      {sub && <div className="text-xs text-text-muted mt-1.5">{sub}</div>}
    </div>
  );
}
