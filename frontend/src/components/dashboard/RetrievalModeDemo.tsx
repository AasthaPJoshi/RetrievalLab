import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { CountUp } from '@/components/ui/CountUp';

const SAMPLE_QUERIES = [
  { label: 'cardiac arrest symptoms',        sparse: 0.698, dense: 0.801, hybrid: 0.847 },
  { label: 'first-line treatment for T2 diabetes', sparse: 0.664, dense: 0.762, hybrid: 0.812 },
  { label: 'liability clause termination',    sparse: 0.591, dense: 0.708, hybrid: 0.779 },
];

const MODES: { key: 'sparse' | 'dense' | 'hybrid'; label: string; sub: string }[] = [
  { key: 'sparse', label: 'Sparse',  sub: 'BM25' },
  { key: 'dense',  label: 'Dense',   sub: 'Pinecone' },
  { key: 'hybrid', label: 'Hybrid',  sub: 'BM25 + Pinecone' },
];

export function RetrievalModeDemo() {
  const [queryIdx, setQueryIdx] = useState(0);
  const [runKey, setRunKey] = useState(0);
  const active = SAMPLE_QUERIES[queryIdx];

  function selectQuery(i: number) {
    setQueryIdx(i);
    setRunKey(k => k + 1);
  }

  return (
    <div className="card p-6">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h3 className="text-sm font-semibold text-text-primary font-display">Live Retrieval Comparison</h3>
          <p className="text-xs mt-0.5 text-text-muted">NDCG@10 by retrieval mode, healthcare corpus</p>
        </div>
        <span className="badge-purple text-[10px]">live demo</span>
      </div>

      {/* Query selector */}
      <div className="flex flex-wrap gap-2 mb-6">
        {SAMPLE_QUERIES.map((q, i) => (
          <button
            key={q.label}
            onClick={() => selectQuery(i)}
            className={`px-3 py-1.5 rounded-sm text-xs font-mono border transition-colors ${
              i === queryIdx
                ? 'border-accent-500 text-text-primary bg-accent-500/10'
                : 'border-transparent text-text-muted hover:text-text-secondary'
            }`}
            style={{ borderColor: i === queryIdx ? 'var(--accent)' : 'var(--border)' }}
          >
            "{q.label}"
          </button>
        ))}
      </div>

      {/* Mode comparison bars */}
      <AnimatePresence mode="wait">
        <motion.div
          key={runKey}
          className="space-y-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
        >
          {MODES.map((mode, i) => {
            const score = active[mode.key];
            const isBest = mode.key === 'hybrid';
            return (
              <div key={mode.key}>
                <div className="flex items-baseline justify-between mb-1.5">
                  <div className="flex items-baseline gap-2">
                    <span className="text-xs font-medium text-text-secondary">{mode.label}</span>
                    <span className="text-[10px] text-text-muted font-mono">{mode.sub}</span>
                  </div>
                  <span className={`tabular-mono text-sm font-semibold ${isBest ? 'text-accent-400' : 'text-text-secondary'}`}>
                    <CountUp value={score} decimals={3} duration={900} />
                  </span>
                </div>
                <div className="score-bar">
                  <motion.div
                    className="score-bar-fill"
                    style={{ background: isBest ? 'var(--accent)' : 'rgba(255,255,255,0.18)' }}
                    initial={{ width: 0 }}
                    animate={{ width: `${score * 100}%` }}
                    transition={{ delay: 0.1 + i * 0.08, duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
                  />
                </div>
              </div>
            );
          })}
        </motion.div>
      </AnimatePresence>

      <div className="mt-5 pt-4 border-t flex items-baseline gap-2" style={{ borderColor: 'var(--border)' }}>
        <span className="text-xs text-text-muted">Hybrid improvement over sparse baseline:</span>
        <span className="tabular-mono text-sm font-semibold text-status-success">
          +<CountUp value={((active.hybrid - active.sparse) / active.sparse) * 100} decimals={1} duration={800} />%
        </span>
      </div>
    </div>
  );
}
