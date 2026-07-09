import { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Type, Repeat, Zap, Scissors, AlertTriangle, Globe } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';

const BASELINE_NDCG = 0.847;

const ATTACKS = [
  { key: 'typo',     name: 'Typo Noise',           icon: Type,          retention: 0.92 },
  { key: 'synonym',  name: 'Synonym Substitution',  icon: Repeat,        retention: 0.88 },
  { key: 'inject',   name: 'Irrelevant Injection',  icon: Zap,           retention: 0.85 },
  { key: 'truncate', name: 'Query Truncation',      icon: Scissors,      retention: 0.78 },
  { key: 'trap',     name: 'Semantic Trap',         icon: AlertTriangle, retention: 0.71 },
  { key: 'domain',   name: 'Domain Shift',          icon: Globe,         retention: 0.82 },
] as const;

type AttackKey = typeof ATTACKS[number]['key'];

// Simulated degradation curve — 8 steps from clean query to fully attacked query
function buildCurve(retention: number) {
  const steps = 8;
  return Array.from({ length: steps + 1 }, (_, i) => {
    const t = i / steps;
    // ease into degradation rather than linear, most attacks bite in the back half
    const eased = Math.pow(t, 1.6);
    const ndcg = BASELINE_NDCG * (1 - eased * (1 - retention));
    return { step: i, ndcg: Number(ndcg.toFixed(4)) };
  });
}

const TOOLTIP_STYLE = {
  background: '#151517',
  border: '1px solid rgba(255,255,255,0.1)',
  borderRadius: '3px',
  color: '#F5F5F5',
  fontSize: '11px',
  fontFamily: 'JetBrains Mono, monospace',
};

export function AdversarialVisualizer() {
  const [selected, setSelected] = useState<AttackKey>('trap');
  const attack = ATTACKS.find(a => a.key === selected)!;
  const curve = useMemo(() => buildCurve(attack.retention), [attack.retention]);
  const finalNdcg = curve[curve.length - 1].ndcg;
  const dropPct = ((BASELINE_NDCG - finalNdcg) / BASELINE_NDCG) * 100;

  return (
    <div className="card p-6">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h3 className="text-sm font-semibold text-text-primary font-display">Adversarial Robustness</h3>
          <p className="text-xs mt-0.5 text-text-muted">Retrieval quality under real-world query corruption</p>
        </div>
        <span className="badge-purple text-[10px]">signature test</span>
      </div>

      {/* Attack selector */}
      <div className="grid grid-cols-3 md:grid-cols-6 gap-2 mb-6">
        {ATTACKS.map(a => {
          const Icon = a.icon;
          const isActive = a.key === selected;
          return (
            <button
              key={a.key}
              onClick={() => setSelected(a.key)}
              className={`flex flex-col items-center gap-1.5 py-3 px-2 rounded-sm border transition-colors text-center`}
              style={{
                borderColor: isActive ? 'var(--accent)' : 'var(--border)',
                background: isActive ? 'rgba(124,58,237,0.08)' : 'transparent',
              }}
            >
              <Icon size={16} className={isActive ? 'text-accent-400' : 'text-text-muted'} />
              <span className={`text-[10px] leading-tight ${isActive ? 'text-text-primary' : 'text-text-muted'}`}>
                {a.name}
              </span>
            </button>
          );
        })}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Live degrading NDCG chart */}
        <div className="lg:col-span-2">
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={curve} margin={{ top: 8, right: 12, bottom: 0, left: -20 }}>
              <CartesianGrid strokeDasharray="2 4" stroke="rgba(255,255,255,0.06)" />
              <XAxis dataKey="step" tick={{ fill: '#6B7280', fontSize: 10 }} axisLine={false} tickLine={false}
                label={{ value: 'attack intensity →', position: 'insideBottom', offset: -2, fill: '#6B7280', fontSize: 10 }} />
              <YAxis domain={[0, 1]} tick={{ fill: '#6B7280', fontSize: 10 }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v: number) => v.toFixed(3)} labelFormatter={() => 'NDCG@10'} />
              <ReferenceLine y={BASELINE_NDCG} stroke="rgba(255,255,255,0.2)" strokeDasharray="3 3"
                label={{ value: 'baseline', position: 'insideTopRight', fill: '#6B7280', fontSize: 9 }} />
              <AnimatePresence>
                <Line
                  key={selected}
                  type="monotone"
                  dataKey="ndcg"
                  stroke="#EF4444"
                  strokeWidth={2}
                  dot={{ r: 2, fill: '#EF4444' }}
                  isAnimationActive
                  animationDuration={900}
                  animationEasing="ease-out"
                />
              </AnimatePresence>
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Stats */}
        <div className="flex flex-col justify-center gap-4">
          <motion.div key={selected + '-final'} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.7 }}>
            <div className="text-[10px] uppercase tracking-widest text-text-muted mb-1">NDCG@10 after attack</div>
            <div className="tabular-mono text-2xl font-semibold text-status-error">{finalNdcg.toFixed(3)}</div>
          </motion.div>
          <motion.div key={selected + '-drop'} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.8 }}>
            <div className="text-[10px] uppercase tracking-widest text-text-muted mb-1">Quality drop</div>
            <div className="tabular-mono text-2xl font-semibold text-text-primary">-{dropPct.toFixed(1)}%</div>
          </motion.div>
          <motion.div key={selected + '-ret'} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.9 }}>
            <div className="text-[10px] uppercase tracking-widest text-text-muted mb-1">Retention rate</div>
            <div className="tabular-mono text-lg font-semibold text-status-success">{(attack.retention * 100).toFixed(0)}%</div>
          </motion.div>
        </div>
      </div>
    </div>
  );
}
