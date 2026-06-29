// =============================================================================
// RetrievalLab — AI Agent Page
// 5-node agentic pipeline: analyze → retrieve → rerank → synthesize → format
// =============================================================================

import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Brain, Send, ChevronDown, Loader2, CheckCircle2,
  Circle, AlertCircle, Quote, Shield, Zap, FileText, ChevronRight
} from 'lucide-react';
import toast from 'react-hot-toast';

import { Header } from '@/components/layout/Header';
import { api, type AgentResponse } from '@/lib/api';
import { cn, confidenceLabel, formatMs } from '@/lib/utils';

const PIPELINE_NODES = [
  { id: 1, name: 'Query Analyzer',   desc: 'Classify + expand query',         icon: Brain },
  { id: 2, name: 'Multi-Retriever',  desc: 'Sparse + dense + hybrid',          icon: Zap },
  { id: 3, name: 'RankForge',        desc: 'Cross-encoder reranking + MMR',    icon: Shield },
  { id: 4, name: 'Synthesizer',      desc: 'LLM answer with grounding',         icon: Quote },
  { id: 5, name: 'Output Formatter', desc: 'Citations + confidence scoring',   icon: FileText },
];

export default function AgentPage() {
  const [query,    setQuery]    = useState('');
  const [corpusId, setCorpusId] = useState('');
  const [mode,     setMode]     = useState('hybrid');
  const [result,   setResult]   = useState<AgentResponse | null>(null);
  const [activeNode, setActiveNode] = useState(0);

  const { data: corpora = [] } = useQuery({
    queryKey: ['corpora'],
    queryFn:  () => api.corpus.list({ status: 'ready' }),
  });

  const agentMut = useMutation({
    mutationFn: () => api.agent.query({ query_text: query, corpus_id: corpusId, mode, top_k: 10 }),
    onMutate: () => {
      setResult(null);
      setActiveNode(1);
      // Simulate node progression
      const timings = [400, 900, 1500, 2500, 3200];
      timings.forEach((ms, i) => {
        setTimeout(() => setActiveNode(i + 2), ms);
      });
    },
    onSuccess: (data) => {
      setResult(data);
      setActiveNode(0);
    },
    onError: (err: Error) => {
      toast.error(err.message);
      setActiveNode(0);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return toast.error('Enter a query');
    if (!corpusId)     return toast.error('Select a corpus');
    agentMut.mutate();
  };

  const isPending = agentMut.isPending;

  return (
    <div className="min-h-screen">
      <Header
        title="AI Agent"
        subtitle="5-node LangGraph pipeline: analyze → retrieve → rerank → synthesize → format"
      />

      <main className="p-8 max-w-5xl mx-auto space-y-6">
        {/* Pipeline visualization */}
        <PipelineViz activeNode={activeNode} />

        {/* Query form */}
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
          className="glass-card p-6">
          <form onSubmit={handleSubmit} className="space-y-4">
            <textarea
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="What are the diagnostic criteria and first-line treatments for type 2 diabetes mellitus?"
              rows={3}
              className="input-field resize-none"
            />

            <div className="flex gap-3 items-center">
              <div className="relative flex-1">
                <select value={corpusId} onChange={e => setCorpusId(e.target.value)}
                  className="input-field appearance-none pr-8 cursor-pointer">
                  <option value="">Select corpus…</option>
                  {corpora.map(c => (
                    <option key={c.corpus_id} value={c.corpus_id}>{c.corpus_id}</option>
                  ))}
                </select>
                <ChevronDown size={13} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none" />
              </div>

              <div className="relative">
                <select value={mode} onChange={e => setMode(e.target.value)}
                  className="input-field appearance-none pr-8 cursor-pointer">
                  <option value="hybrid">Hybrid (RRF)</option>
                  <option value="dense">Dense (Vector)</option>
                  <option value="sparse">Sparse (BM25)</option>
                </select>
                <ChevronDown size={13} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none" />
              </div>

              <button type="submit" disabled={isPending} className="btn-primary whitespace-nowrap">
                {isPending
                  ? <><Loader2 size={14} className="animate-spin" /> Processing…</>
                  : <><Send size={14} /> Run Agent</>
                }
              </button>
            </div>
          </form>
        </motion.div>

        {/* Result */}
        <AnimatePresence mode="wait">
          {result && !isPending && (
            <motion.div key="result" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
              className="space-y-4">
              {/* Answer card */}
              <div className="glass-card p-6">
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-center gap-2">
                    <div className="w-6 h-6 rounded-full flex items-center justify-center"
                      style={{ background: 'rgba(124,58,237,0.15)', border: '1px solid rgba(124,58,237,0.3)' }}>
                      <Brain size={12} className="text-purple-300" />
                    </div>
                    <span className="text-sm font-semibold text-white">AI Answer</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <ConfidenceBadge score={result.confidence} />
                    <span className="text-xs text-slate-500">{formatMs(result.total_latency_ms)}</span>
                  </div>
                </div>

                {/* Answer text */}
                <div className="prose prose-invert prose-sm max-w-none">
                  <p className="text-slate-200 leading-relaxed text-sm whitespace-pre-wrap">
                    {result.answer}
                  </p>
                </div>

                {/* Query metadata */}
                <div className="mt-4 pt-4 border-t flex gap-4 text-xs text-slate-500"
                  style={{ borderColor: 'rgba(124,58,237,0.08)' }}>
                  <span>Type: <span className="text-slate-400 capitalize">{result.query_type}</span></span>
                  <span>Domain: <span className="text-slate-400 capitalize">{result.detected_domain}</span></span>
                  <span>Sources: <span className="text-slate-400">{result.sources.length}</span></span>
                </div>
              </div>

              {/* Sources */}
              {result.sources.length > 0 && (
                <div className="glass-card p-6">
                  <h3 className="text-sm font-semibold text-white mb-4">
                    Sources <span className="text-slate-600 font-normal">({result.sources.length})</span>
                  </h3>
                  <div className="space-y-3">
                    {result.sources.slice(0, 5).map((src: any, i) => (
                      <SourceItem key={src.chunk_id} source={src} index={i + 1} />
                    ))}
                  </div>
                </div>
              )}

              {/* Agent trace */}
              {result.trace.length > 0 && (
                <TracePanel trace={result.trace} />
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </main>
    </div>
  );
}

function PipelineViz({ activeNode }: { activeNode: number }) {
  return (
    <div className="glass-card p-5">
      <div className="flex items-center justify-between">
        {PIPELINE_NODES.map((node, i) => {
          const Icon = node.icon;
          const isActive   = activeNode === node.id;
          const isComplete = activeNode > node.id;
          const isPending  = activeNode === 0;

          return (
            <div key={node.id} className="flex items-center">
              <motion.div
                animate={isActive ? { scale: [1, 1.1, 1] } : {}}
                transition={{ repeat: Infinity, duration: 1 }}
                className="flex flex-col items-center gap-1.5"
              >
                <div className={cn(
                  'w-10 h-10 rounded-xl flex items-center justify-center transition-all duration-300',
                  isActive   ? 'bg-purple-500/20 border-2 border-purple-500' :
                  isComplete ? 'bg-emerald-400/15 border border-accent-green/40' :
                               'bg-white/5 border border-white/8'
                )}>
                  {isComplete
                    ? <CheckCircle2 size={16} className="text-emerald-400" />
                    : isActive
                    ? <Loader2 size={16} className="text-purple-300 animate-spin" />
                    : <Icon size={14} className={isPending ? 'text-slate-600' : 'text-slate-500'} />
                  }
                </div>
                <div className="text-center">
                  <div className={cn('text-[10px] font-medium whitespace-nowrap',
                    isActive ? 'text-purple-300' : isComplete ? 'text-emerald-400' : 'text-slate-600'
                  )}>
                    {node.name}
                  </div>
                </div>
              </motion.div>

              {i < PIPELINE_NODES.length - 1 && (
                <div className={cn(
                  'w-8 h-px mx-2 transition-all duration-500',
                  isComplete ? 'bg-emerald-400/40' : 'bg-white/8'
                )} />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function ConfidenceBadge({ score }: { score: number }) {
  const { label, color } = confidenceLabel(score);
  const bg = label === 'High' ? 'bg-emerald-400/10 border-accent-green/20'
           : label === 'Medium' ? 'bg-accent-amber/10 border-accent-amber/20'
           : 'bg-red-400/10 border-accent-red/20';

  return (
    <div className={cn('flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-xs font-medium', bg, color)}>
      <div className={cn('w-1.5 h-1.5 rounded-full', color.replace('text-', 'bg-'))} />
      {label} Confidence · {(score * 100).toFixed(0)}%
    </div>
  );
}

function SourceItem({ source, index }: { source: any; index: number }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="border rounded-lg overflow-hidden transition-all"
      style={{ borderColor: 'rgba(124,58,237,0.08)' }}>
      <button onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-white/3 transition-colors">
        <span className="w-5 h-5 rounded text-[10px] font-bold flex items-center justify-center shrink-0"
          style={{ background: 'rgba(124,58,237,0.1)', color: '#8B5CF6' }}>
          {index}
        </span>
        <span className="text-xs text-slate-400 font-mono truncate flex-1">
          {source.source_doc || source.chunk_id}
        </span>
        <span className="font-mono text-xs text-purple-300 shrink-0">{source.score?.toFixed(4)}</span>
        <ChevronRight size={12} className={cn('text-slate-600 transition-transform', open && 'rotate-90')} />
      </button>
      <AnimatePresence>
        {open && (
          <motion.div initial={{ height: 0 }} animate={{ height: 'auto' }} exit={{ height: 0 }}
            className="overflow-hidden">
            <p className="px-4 py-3 text-xs text-slate-400 leading-relaxed border-t"
              style={{ borderColor: 'rgba(255,255,255,0.04)' }}>
              {source.text}
            </p>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function TracePanel({ trace }: { trace: string[] }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="glass-card overflow-hidden">
      <button onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-5 py-3 text-sm hover:bg-white/3 transition-colors">
        <span className="text-slate-400">Agent Trace ({trace.length} steps)</span>
        <ChevronDown size={14} className={cn('text-slate-600 transition-transform', open && 'rotate-180')} />
      </button>
      <AnimatePresence>
        {open && (
          <motion.div initial={{ height: 0 }} animate={{ height: 'auto' }} exit={{ height: 0 }}
            className="overflow-hidden">
            <div className="px-5 py-4 border-t space-y-1.5"
              style={{ borderColor: 'rgba(124,58,237,0.06)' }}>
              {trace.map((line, i) => (
                <div key={i} className="flex gap-3 text-xs font-mono">
                  <span className="text-slate-700 shrink-0">{String(i).padStart(2, '0')}</span>
                  <span className="text-slate-400">{line}</span>
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
