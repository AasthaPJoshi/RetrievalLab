// =============================================================================
// RetrievalLab — Evaluation Engine Page
// NDCG@K · MRR · MAP · Precision · Recall · Hit Rate
// =============================================================================

import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { motion, AnimatePresence } from 'framer-motion';
import { FlaskConical, Play, Loader2, BarChart3, Target, TrendingUp, Info } from 'lucide-react';
import toast from 'react-hot-toast';
import { RadarChart, PolarGrid, PolarAngleAxis, Radar, ResponsiveContainer, Tooltip } from 'recharts';

import { Header } from '@/components/layout/Header';
import { MetricCard } from '@/components/ui/MetricCard';
import { api } from '@/lib/api';
import { cn, scoreColor } from '@/lib/utils';

const CHART_TOOLTIP_STYLE = {
  backgroundColor: '#100C2E',
  border: '1px solid rgba(124,58,237,0.2)',
  borderRadius: '8px',
  color: '#DDD6FE',
  fontSize: '12px',
};

export default function EvalPage() {
  const [retrievedIds, setRetrievedIds] = useState('chunk_a\nchunk_b\nchunk_c\nchunk_d\nchunk_e');
  const [relevantIds,  setRelevantIds]  = useState('chunk_a: 1.0\nchunk_c: 1.0');
  const [query,        setQuery]        = useState('What is the diagnostic criteria?');
  const [result,       setResult]       = useState<Record<string, number> | null>(null);

  const scoreMut = useMutation({
    mutationFn: () => {
      const retrieved_ids = retrievedIds.split('\n').map(s => s.trim()).filter(Boolean);
      const relevant_ids: Record<string, number> = {};
      relevantIds.split('\n').forEach(line => {
        const [id, grade] = line.split(':').map(s => s.trim());
        if (id) relevant_ids[id] = parseFloat(grade) || 1.0;
      });
      return api.eval.score({ retrieved_ids, relevant_ids, query });
    },
    onSuccess: (data) => setResult(data.metrics),
    onError:   (e: Error) => toast.error(e.message),
  });

  // Build radar data
  const radarData = result ? [
    { metric: 'NDCG@10', value: result['ndcg@10'] ?? 0 },
    { metric: 'NDCG@5',  value: result['ndcg@5']  ?? 0 },
    { metric: 'MRR',     value: result['mrr']      ?? 0 },
    { metric: 'MAP@10',  value: result['map@10']   ?? 0 },
    { metric: 'P@10',    value: result['precision@10'] ?? 0 },
    { metric: 'R@10',    value: result['recall@10']    ?? 0 },
  ] : [];

  return (
    <div className="min-h-screen">
      <Header title="Eval Engine" subtitle="Compute NDCG@K · MRR · MAP · Precision · Recall for retrieval results" />

      <main className="p-8 space-y-6 max-w-6xl mx-auto">
        {/* Explainer */}
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
          className="glass-card p-5 flex items-start gap-3">
          <Info size={15} className="text-purple-300 shrink-0 mt-0.5" />
          <div className="text-xs text-slate-400 leading-relaxed">
            <strong className="text-white">How it works:</strong> Enter your retrieved chunk IDs in ranked order (best first),
            then specify which IDs are ground-truth relevant and their relevance grades.
            The engine computes all standard IR metrics instantly.
            <span className="text-purple-300 ml-1">Grade 2.0 = highly relevant, 1.0 = relevant.</span>
          </div>
        </motion.div>

        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          {/* Input panel */}
          <div className="glass-card p-6 space-y-4">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <FlaskConical size={14} className="text-purple-300" />
              Evaluation Input
            </h3>

            <div>
              <label className="block text-xs text-slate-500 mb-2">
                Query Text <span className="text-slate-700">(for context)</span>
              </label>
              <input value={query} onChange={e => setQuery(e.target.value)}
                className="input-field" placeholder="What is the diagnostic criteria?" />
            </div>

            <div>
              <label className="block text-xs text-slate-500 mb-2">
                Retrieved IDs <span className="text-slate-700">(one per line, ranked order)</span>
              </label>
              <textarea value={retrievedIds} onChange={e => setRetrievedIds(e.target.value)}
                rows={6} className="input-field font-mono text-xs resize-none"
                placeholder="chunk_a&#10;chunk_b&#10;chunk_c" />
            </div>

            <div>
              <label className="block text-xs text-slate-500 mb-2">
                Relevant IDs <span className="text-slate-700">(format: id: grade)</span>
              </label>
              <textarea value={relevantIds} onChange={e => setRelevantIds(e.target.value)}
                rows={4} className="input-field font-mono text-xs resize-none"
                placeholder="chunk_a: 1.0&#10;chunk_c: 2.0" />
            </div>

            <button onClick={() => scoreMut.mutate()} disabled={scoreMut.isPending}
              className="btn-primary w-full justify-center">
              {scoreMut.isPending
                ? <><Loader2 size={13} className="animate-spin" /> Computing…</>
                : <><Play size={13} /> Compute Metrics</>
              }
            </button>
          </div>

          {/* Results panel */}
          <div className="space-y-4">
            <AnimatePresence>
              {result && (
                <motion.div key="results" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }}
                  className="space-y-4">
                  {/* Primary metrics */}
                  <div className="grid grid-cols-2 gap-3">
                    <MetricCard label="NDCG@10"  value={result['ndcg@10'] ?? 0}  isScore delay={0}    size="sm" />
                    <MetricCard label="MRR"       value={result['mrr'] ?? 0}       isScore delay={0.05} size="sm" />
                    <MetricCard label="MAP@10"    value={result['map@10'] ?? 0}    isScore delay={0.10} size="sm" />
                    <MetricCard label="Hit Rate"  value={result['hit_rate@10'] ?? 0} isScore delay={0.15} size="sm" />
                  </div>

                  {/* Radar chart */}
                  <div className="glass-card p-5">
                    <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">
                      Metric Radar
                    </h4>
                    <ResponsiveContainer width="100%" height={200}>
                      <RadarChart data={radarData}>
                        <PolarGrid stroke="rgba(255,255,255,0.06)" />
                        <PolarAngleAxis dataKey="metric" tick={{ fill: '#6B7AA0', fontSize: 10 }} />
                        <Radar dataKey="value" stroke="#8B5CF6" fill="#8B5CF6" fillOpacity={0.15} />
                        <Tooltip contentStyle={CHART_TOOLTIP_STYLE} formatter={(v: any) => v.toFixed(4)} />
                      </RadarChart>
                    </ResponsiveContainer>
                  </div>

                  {/* All metrics table */}
                  <div className="glass-card overflow-hidden">
                    <div className="px-5 py-3 border-b" style={{ borderColor: 'rgba(124,58,237,0.08)' }}>
                      <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">All Metrics</h4>
                    </div>
                    <div className="divide-y" style={{ '--tw-divide-opacity': '1' }}>
                      {Object.entries(result).map(([key, val]) => (
                        <div key={key} className="flex items-center justify-between px-5 py-2.5">
                          <span className="text-xs font-mono text-slate-400">{key}</span>
                          <div className="flex items-center gap-3">
                            <div className="w-24 h-1 rounded-full bg-white/5">
                              <div className="h-full rounded-full bg-purple-500/50 transition-all"
                                style={{ width: `${Math.min((val as number) * 100, 100)}%` }} />
                            </div>
                            <span className={cn('text-xs font-mono font-bold', scoreColor(val as number))}>
                              {(val as number).toFixed(4)}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {!result && !scoreMut.isPending && (
              <div className="glass-card p-12 text-center">
                <BarChart3 size={32} className="mx-auto text-slate-700 mb-3" />
                <p className="text-sm text-slate-500">Enter retrieval results and click Compute Metrics</p>
                <p className="text-xs text-slate-700 mt-1">NDCG@10, MRR, MAP, Precision, Recall, Hit Rate</p>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
