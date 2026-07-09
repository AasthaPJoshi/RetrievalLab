// =============================================================================
// RetrievalLab — Corpus Management Page
// =============================================================================

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Database, Plus, Trash2, RefreshCw, ChevronDown,
  FileText, Layers, Clock, Cpu, X, Loader2, AlertCircle
} from 'lucide-react';
import toast from 'react-hot-toast';

import { Header } from '@/components/layout/Header';
import { api, type Corpus } from '@/lib/api';
import { cn, domainIcon, statusBadge, timeAgo, formatTokens, statusColor } from '@/lib/utils';

const DOMAINS   = ['general','healthcare','finance','legal','manufacturing','education','ecommerce','cybersecurity'];
const STRATEGIES = ['recursive','semantic','sentence_window','document_structure','fixed','table_aware','propositional'];

export default function CorpusPage() {
  const [showIngest, setShowIngest] = useState(false);
  const qc = useQueryClient();

  const { data: corpora = [], isLoading } = useQuery({
    queryKey: ['corpora'],
    queryFn:  () => api.corpus.list({ limit: 100 }),
    refetchInterval: 5_000,
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => api.corpus.delete(id),
    onSuccess:  () => { toast.success('Corpus deleted'); qc.invalidateQueries({ queryKey: ['corpora'] }); },
    onError:    (e: Error) => toast.error(e.message),
  });

  return (
    <div className="min-h-screen">
      <Header title="Corpora" subtitle="Manage document collections for retrieval experiments" />

      <main className="p-8 space-y-6">
        {/* Toolbar */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 text-sm text-slate-700">
              <Database size={14} />
              <span>{corpora.length} corpora</span>
              <span className="text-text-secondary">·</span>
              <span className="text-emerald-400">{corpora.filter(c => c.status === 'ready').length} ready</span>
            </div>
          </div>
          <button onClick={() => setShowIngest(true)} className="btn-primary">
            <Plus size={14} />
            Ingest Corpus
          </button>
        </div>

        {/* Corpus Grid */}
        {isLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {[1,2,3].map(i => <CorpusCardSkeleton key={i} />)}
          </div>
        ) : corpora.length === 0 ? (
          <EmptyState onIngest={() => setShowIngest(true)} />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            <AnimatePresence>
              {corpora.map((corpus, i) => (
                <CorpusCard
                  key={corpus.corpus_id}
                  corpus={corpus}
                  index={i}
                  onDelete={() => {
                    if (confirm(`Delete ${corpus.corpus_id}?`)) deleteMut.mutate(corpus.corpus_id);
                  }}
                />
              ))}
            </AnimatePresence>
          </div>
        )}
      </main>

      {/* Ingest Modal */}
      <AnimatePresence>
        {showIngest && (
          <IngestModal onClose={() => setShowIngest(false)} />
        )}
      </AnimatePresence>
    </div>
  );
}

function CorpusCard({ corpus, index, onDelete }: { corpus: Corpus; index: number; onDelete: () => void }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.95 }}
      transition={{ delay: index * 0.04 }}
      className="card p-5 group relative overflow-hidden"
    >
      {/* Domain accent corner */}
      <div className="absolute top-0 right-0 w-24 h-24 opacity-10 pointer-events-none"
        style={{ background: 'radial-gradient(circle at top right, #0EA5E9, transparent 70%)' }} />

      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center text-xl"
            style={{ background: 'rgba(15,23,42,0.035)', border: '1px solid rgba(15,23,42,0.035)' }}>
            {domainIcon(corpus.domain)}
          </div>
          <div>
            <div className="text-sm font-semibold text-text-primary leading-snug">{corpus.corpus_id}</div>
            <div className="text-[10px] text-slate-700 capitalize mt-0.5">{corpus.domain} · {corpus.version}</div>
          </div>
        </div>
        <span className={cn('badge text-[10px]', statusBadge(corpus.status))}>
          {corpus.status}
        </span>
      </div>

      {/* Metrics grid */}
      <div className="grid grid-cols-3 gap-2 mb-4">
        {[
          { label: 'Docs',    value: corpus.doc_count },
          { label: 'Chunks',  value: corpus.chunk_count.toLocaleString() },
          { label: 'Tokens',  value: formatTokens(corpus.total_tokens) },
        ].map(({ label, value }) => (
          <div key={label} className="rounded-lg p-2.5 text-center"
            style={{ background: 'rgba(15,23,42,0.035)', border: '1px solid rgba(15,23,42,0.035)' }}>
            <div className="text-sm font-bold text-text-primary">{value}</div>
            <div className="text-[9px] text-text-secondary uppercase tracking-wider mt-0.5">{label}</div>
          </div>
        ))}
      </div>

      {/* Strategy + timing */}
      <div className="flex items-center justify-between text-xs text-text-secondary">
        <span className="flex items-center gap-1">
          <Layers size={10} />
          {corpus.chunk_strategy}
        </span>
        <span className="flex items-center gap-1">
          <Clock size={10} />
          {timeAgo(corpus.updated_at)}
        </span>
      </div>

      {/* Delete button */}
      <button onClick={onDelete}
        className="absolute top-3 right-3 opacity-0 group-hover:opacity-100 transition-opacity
                   w-7 h-7 flex items-center justify-center rounded-lg
                   text-text-secondary hover:text-red-400 hover:bg-red-400/10 transition-colors">
        <Trash2 size={13} />
      </button>
    </motion.div>
  );
}

function IngestModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const [form, setForm] = useState({
    corpus_id: '', source: '', name: '',
    domain: 'general', strategy: 'recursive',
    chunk_size: 512, chunk_overlap: 64,
  });

  const ingestMut = useMutation({
    mutationFn: () => api.corpus.ingest(form),
    onSuccess: (data) => {
      toast.success(data.message);
      qc.invalidateQueries({ queryKey: ['corpora'] });
      onClose();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const set = (key: string, value: any) => setForm(f => ({ ...f, [key]: value }));

  return (
    <motion.div
      initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(4px)' }}
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <motion.div
        initial={{ scale: 0.9, y: 20 }} animate={{ scale: 1, y: 0 }} exit={{ scale: 0.9, y: 20 }}
        className="card w-full max-w-lg p-6"
        style={{ border: '1px solid rgba(14,165,233,0.2)' }}
      >
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-semibold text-text-primary">Ingest Corpus</h2>
          <button onClick={onClose} className="btn-ghost p-1.5"><X size={16} /></button>
        </div>

        <div className="space-y-4">
          <Field label="Corpus ID *" placeholder="healthcare_pubmed_v1"
            value={form.corpus_id} onChange={v => set('corpus_id', v)} />
          <Field label="Source Path *" placeholder="/data/documents/ or data/seeds/healthcare/"
            value={form.source} onChange={v => set('source', v)} />
          <Field label="Display Name" placeholder="Healthcare PubMed Corpus"
            value={form.name} onChange={v => set('name', v)} />

          <div className="grid grid-cols-2 gap-4">
            <SelectField label="Domain" value={form.domain} onChange={v => set('domain', v)} options={DOMAINS} />
            <SelectField label="Strategy" value={form.strategy} onChange={v => set('strategy', v)} options={STRATEGIES} />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-slate-700 mb-1.5">Chunk Size (tokens)</label>
              <input type="number" value={form.chunk_size} min={64} max={2048}
                onChange={e => set('chunk_size', Number(e.target.value))}
                className="input-field" />
            </div>
            <div>
              <label className="block text-xs text-slate-700 mb-1.5">Overlap (tokens)</label>
              <input type="number" value={form.chunk_overlap} min={0} max={512}
                onChange={e => set('chunk_overlap', Number(e.target.value))}
                className="input-field" />
            </div>
          </div>

          <div className="flex items-start gap-2 p-3 rounded-lg text-xs"
            style={{ background: 'rgba(14,165,233,0.05)', border: '1px solid rgba(14,165,233,0.1)' }}>
            <AlertCircle size={13} className="text-accent-500 shrink-0 mt-0.5" />
            <span className="text-slate-700">
              Ingestion runs in the background. Refresh the corpus list to check status.
              Large corpora may take several minutes.
            </span>
          </div>

          <div className="flex gap-3 pt-2">
            <button onClick={onClose} className="btn-ghost flex-1 justify-center border border-white/10">
              Cancel
            </button>
            <button
              onClick={() => ingestMut.mutate()}
              disabled={!form.corpus_id || !form.source || ingestMut.isPending}
              className="btn-primary flex-1 justify-center">
              {ingestMut.isPending
                ? <><Loader2 size={13} className="animate-spin" /> Queuing…</>
                : <><Database size={13} /> Ingest</>
              }
            </button>
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
}

function Field({ label, placeholder, value, onChange }: { label: string; placeholder: string; value: string; onChange: (v: string) => void }) {
  return (
    <div>
      <label className="block text-xs text-slate-700 mb-1.5">{label}</label>
      <input type="text" value={value} onChange={e => onChange(e.target.value)}
        placeholder={placeholder} className="input-field" />
    </div>
  );
}

function SelectField({ label, value, onChange, options }: { label: string; value: string; onChange: (v: string) => void; options: string[] }) {
  return (
    <div>
      <label className="block text-xs text-slate-700 mb-1.5">{label}</label>
      <div className="relative">
        <select value={value} onChange={e => onChange(e.target.value)}
          className="input-field appearance-none pr-8 cursor-pointer capitalize">
          {options.map(o => <option key={o} value={o}>{o}</option>)}
        </select>
        <ChevronDown size={13} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-700 pointer-events-none" />
      </div>
    </div>
  );
}

function CorpusCardSkeleton() {
  return (
    <div className="card p-5 space-y-4">
      <div className="flex gap-3">
        <div className="skeleton w-10 h-10 rounded-xl" />
        <div className="space-y-1.5 flex-1">
          <div className="skeleton h-4 w-32 rounded" />
          <div className="skeleton h-3 w-20 rounded" />
        </div>
      </div>
      <div className="grid grid-cols-3 gap-2">
        {[1,2,3].map(i => <div key={i} className="skeleton h-12 rounded-lg" />)}
      </div>
    </div>
  );
}

function EmptyState({ onIngest }: { onIngest: () => void }) {
  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}
      className="card p-16 text-center">
      <Database size={40} className="mx-auto text-slate-700 mb-4" />
      <h3 className="text-lg font-semibold text-slate-300 mb-2">No corpora yet</h3>
      <p className="text-sm text-slate-700 max-w-sm mx-auto mb-6">
        Ingest your first document collection to start building and evaluating retrieval systems.
      </p>
      <button onClick={onIngest} className="btn-primary">
        <Plus size={14} /> Ingest Your First Corpus
      </button>
    </motion.div>
  );
}
