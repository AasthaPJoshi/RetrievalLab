// =============================================================================
// RetrievalLab — Retrieval Playground Page
// Live search interface: query → results with score visualization
// =============================================================================

import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, Sliders, ChevronDown, Clock, BarChart2, FileText, Loader2 } from 'lucide-react';
import toast from 'react-hot-toast';

import { Header } from '@/components/layout/Header';
import { api, type RetrieveResultItem } from '@/lib/api';
import { cn, formatMs, truncate, scoreColor } from '@/lib/utils';

const MODES = ['hybrid', 'dense', 'sparse'] as const;
type Mode = typeof MODES[number];

const MODE_LABELS: Record<Mode, { label: string; desc: string; color: string }> = {
  hybrid: { label: 'Hybrid',  desc: 'RRF fusion of sparse + dense',    color: 'text-accent-500' },
  dense:  { label: 'Dense',   desc: 'Vector similarity (cosine)',       color: 'text-accent-500' },
  sparse: { label: 'Sparse',  desc: 'BM25 keyword matching',           color: 'text-amber-400' },
};

export default function RetrievalPage() {
  const [query,     setQuery]     = useState('');
  const [corpusId,  setCorpusId]  = useState('');
  const [mode,      setMode]      = useState<Mode>('hybrid');
  const [topK,      setTopK]      = useState(10);
  const [showOpts,  setShowOpts]  = useState(false);
  const [results,   setResults]   = useState<RetrieveResultItem[]>([]);
  const [meta,      setMeta]      = useState<{ latency: number; total: number } | null>(null);

  const { data: corpora = [] } = useQuery({
    queryKey: ['corpora'],
    queryFn:  () => api.corpus.list({ status: 'ready' }),
  });

  const searchMut = useMutation({
    mutationFn: () => api.retrieve.query({ query, corpus_id: corpusId, mode, top_k: topK }),
    onSuccess: (data) => {
      setResults(data.results);
      setMeta({ latency: data.latency_ms, total: data.total_results });
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim())    return toast.error('Enter a query');
    if (!corpusId)        return toast.error('Select a corpus');
    searchMut.mutate();
  };

  return (
    <div className="min-h-screen">
      <Header title="Retrieval Playground" subtitle="Test sparse · dense · hybrid retrieval modes" />

      <main className="p-8 max-w-5xl mx-auto space-y-6">
        {/* Search Form */}
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
          className="card p-6">

          <form onSubmit={handleSearch} className="space-y-4">
            {/* Query input */}
            <div className="relative">
              <Search size={16} className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-700" />
              <input
                value={query}
                onChange={e => setQuery(e.target.value)}
                placeholder="What are the diagnostic criteria for type 2 diabetes?"
                className="input-field pl-11 pr-4 py-4 text-base"
              />
            </div>

            {/* Controls row */}
            <div className="flex flex-wrap gap-3 items-center">
              {/* Corpus selector */}
              <div className="relative flex-1 min-w-48">
                <select
                  value={corpusId}
                  onChange={e => setCorpusId(e.target.value)}
                  className="input-field appearance-none pr-8 cursor-pointer"
                >
                  <option value="">Select corpus…</option>
                  {corpora.map(c => (
                    <option key={c.corpus_id} value={c.corpus_id}>
                      {c.corpus_id} ({c.chunk_count} chunks)
                    </option>
                  ))}
                </select>
                <ChevronDown size={14} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-700 pointer-events-none" />
              </div>

              {/* Mode selector */}
              <div className="flex rounded-lg overflow-hidden border" style={{ borderColor: 'rgba(14,165,233,0.15)' }}>
                {MODES.map(m => (
                  <button key={m} type="button"
                    onClick={() => setMode(m)}
                    className={cn(
                      'px-4 py-2.5 text-xs font-medium transition-all duration-150',
                      mode === m
                        ? 'bg-purple-500/15 text-accent-500 border-r border-purple-500/20'
                        : 'text-slate-700 hover:text-text-primary hover:bg-white/5 border-r border-white/5'
                    )}
                  >
                    {MODE_LABELS[m].label}
                  </button>
                ))}
              </div>

              {/* Options toggle */}
              <button type="button" onClick={() => setShowOpts(!showOpts)}
                className={cn('btn-ghost border border-white/8', showOpts && 'border-purple-500/30 text-accent-500')}>
                <Sliders size={13} />
                Options
              </button>

              {/* Submit */}
              <button type="submit" disabled={searchMut.isPending}
                className="btn-primary">
                {searchMut.isPending ? <Loader2 size={14} className="animate-spin" /> : <Search size={14} />}
                {searchMut.isPending ? 'Searching…' : 'Search'}
              </button>
            </div>

            {/* Options panel */}
            <AnimatePresence>
              {showOpts && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  className="overflow-hidden"
                >
                  <div className="pt-4 border-t flex gap-6 items-center"
                    style={{ borderColor: 'rgba(14,165,233,0.08)' }}>
                    <div className="flex items-center gap-3">
                      <label className="text-xs text-slate-700 whitespace-nowrap">Top K:</label>
                      <input
                        type="range" min={1} max={50} value={topK}
                        onChange={e => setTopK(Number(e.target.value))}
                        className="w-32 accent-cyan-500"
                      />
                      <span className="text-xs font-mono text-accent-500 w-6 text-center">{topK}</span>
                    </div>
                    <div className="text-xs text-slate-700">
                      Mode: <span className={cn('font-medium', MODE_LABELS[mode].color)}>
                        {MODE_LABELS[mode].desc}
                      </span>
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </form>
        </motion.div>

        {/* Results */}
        <AnimatePresence mode="wait">
          {searchMut.isPending && (
            <motion.div key="loading" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              className="space-y-3">
              {Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="card p-5 space-y-2">
                  <div className="flex gap-4">
                    <div className="skeleton h-4 w-8 rounded" />
                    <div className="skeleton h-4 flex-1 rounded" />
                    <div className="skeleton h-4 w-20 rounded" />
                  </div>
                  <div className="skeleton h-12 w-full rounded" />
                </div>
              ))}
            </motion.div>
          )}

          {!searchMut.isPending && results.length > 0 && (
            <motion.div key="results" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
              {/* Meta bar */}
              {meta && (
                <div className="flex items-center gap-4 mb-4 text-xs text-slate-700">
                  <span className="flex items-center gap-1.5">
                    <BarChart2 size={12} />
                    {meta.total} results
                  </span>
                  <span className="flex items-center gap-1.5">
                    <Clock size={12} />
                    {formatMs(meta.latency)}
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className={cn('font-medium', MODE_LABELS[mode].color)}>
                      {MODE_LABELS[mode].label}
                    </span>
                    retrieval
                  </span>
                </div>
              )}

              <div className="space-y-3">
                {results.map((result, i) => (
                  <ResultCard key={result.chunk_id} result={result} rank={i + 1} />
                ))}
              </div>
            </motion.div>
          )}

          {!searchMut.isPending && searchMut.isSuccess && results.length === 0 && (
            <motion.div key="empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }}
              className="card p-12 text-center">
              <Search size={32} className="mx-auto text-slate-700 mb-3" />
              <p className="text-slate-700 text-sm">No results found</p>
              <p className="text-text-secondary text-xs mt-1">Try a different query or switch to hybrid mode</p>
            </motion.div>
          )}
        </AnimatePresence>
      </main>
    </div>
  );
}

function ResultCard({ result, rank }: { result: RetrieveResultItem; rank: number }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <motion.div
      initial={{ opacity: 0, x: -12 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: rank * 0.04 }}
      className="card overflow-hidden group"
    >
      <div className="flex items-start gap-4 p-5">
        {/* Rank badge */}
        <div className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0 font-bold text-sm"
          style={{
            background: rank === 1 ? 'rgba(14,165,233,0.15)' : 'rgba(15,23,42,0.035)',
            color:      rank === 1 ? '#0EA5E9' : '#64748B',
            border:     rank === 1 ? '1px solid rgba(14,165,233,0.25)' : '1px solid rgba(15,23,42,0.035)',
          }}>
          {rank}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 mb-2">
            <FileText size={12} className="text-text-secondary shrink-0" />
            <span className="text-xs text-slate-700 font-mono truncate">
              {result.source_doc || result.chunk_id}
            </span>
            <span className="badge-cyan text-[10px] shrink-0">{result.retrieval_mode}</span>
          </div>

          <p className={cn('text-sm text-slate-300 leading-relaxed', !expanded && 'line-clamp-3')}>
            {result.text}
          </p>

          {result.text.length > 240 && (
            <button onClick={() => setExpanded(!expanded)}
              className="text-xs text-accent-500 hover:text-accent-500 mt-1.5 transition-colors">
              {expanded ? 'Show less' : 'Show more'}
            </button>
          )}
        </div>

        {/* Score */}
        <div className="shrink-0 text-right">
          <div className={cn('text-lg font-bold font-mono', scoreColor(result.score))}>
            {result.score.toFixed(4)}
          </div>
          <div className="text-[10px] text-text-secondary uppercase tracking-wider">score</div>
        </div>
      </div>

      {/* Score bar */}
      <div className="h-0.5 bg-white/3">
        <div className="h-full transition-all duration-700"
          style={{
            width: `${Math.min(result.score * 100, 100)}%`,
            background: 'linear-gradient(90deg, #0EA5E9, #38BDF8)',
          }} />
      </div>
    </motion.div>
  );
}
