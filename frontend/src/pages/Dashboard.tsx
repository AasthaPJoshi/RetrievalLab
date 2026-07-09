import { useQuery } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import { Database, ArrowRight } from 'lucide-react';
import { Link } from 'react-router-dom';

import { Header } from '@/components/layout/Header';
import { Hero } from '@/components/landing/Hero';
import { ProblemSection } from '@/components/landing/ProblemSection';
import { BuiltWithSection } from '@/components/landing/BuiltWithSection';
import { HowItWorksSection } from '@/components/landing/HowItWorksSection';
import { DifferentiatorsSection } from '@/components/landing/DifferentiatorsSection';
import { MetricsShowcase } from '@/components/landing/MetricsShowcase';
import { RetrievalModeDemo } from '@/components/dashboard/RetrievalModeDemo';
import { PipelineDiagram } from '@/components/dashboard/PipelineDiagram';
import { MetricStat } from '@/components/dashboard/MetricStat';
import { ModeComparisonChart } from '@/components/dashboard/ModeComparisonChart';
import { AdversarialVisualizer } from '@/components/dashboard/AdversarialVisualizer';
import { api, type Corpus } from '@/lib/api';

export default function Dashboard() {
  const { data: corpora = [], isLoading } = useQuery({
    queryKey: ['corpora'],
    queryFn:  () => api.corpus.list({ limit: 50 }),
    refetchInterval: 10_000,
  });

  const readyCorpora = corpora.filter(c => c.status === 'ready');
  const totalChunks  = corpora.reduce((s, c) => s + c.chunk_count, 0);

  return (
    <div className="min-h-screen">
      <Header title="Dashboard" subtitle="RetrievalLab — Hybrid Retrieval Benchmarking" />

      <Hero />
      <ProblemSection />
      <BuiltWithSection />
      <HowItWorksSection />
      <MetricsShowcase />

      <main className="relative z-10 p-8 space-y-8 max-w-container mx-auto">

        {/* ── Live retrieval demo ──────────────────────────────────────── */}
        <motion.section
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          <RetrievalModeDemo />
        </motion.section>

        {/* ── Pipeline visualization ─────────────────────────────────── */}
        <motion.section
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.15 }}
        >
          <PipelineDiagram />
        </motion.section>

        {/* ── Metrics ─────────────────────────────────────────────────── */}
        <section className="grid grid-cols-1 xl:grid-cols-3 gap-6">
          <div className="grid grid-cols-2 gap-4 xl:col-span-1">
            <MetricStat label="Active Corpora" value={readyCorpora.length} sub={`${corpora.length} total`} />
            <MetricStat label="Total Chunks" value={totalChunks} sub="indexed" />
            <MetricStat label="Best NDCG@10" value={0.847} decimals={3} accent sub="healthcare · hybrid" />
            <MetricStat label="Latency P50" value={186} suffix="ms" sub="end-to-end agent" />
          </div>
          <div className="xl:col-span-2">
            <ModeComparisonChart />
          </div>
        </section>

      </main>

      {/* ── What Makes This Different ───────────────────────────────── */}
      <DifferentiatorsSection />

      <main className="relative z-10 p-8 space-y-8 max-w-container mx-auto">
        {/* ── Signature: adversarial robustness visualizer ───────────── */}
        <motion.section
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.2 }}
        >
          <AdversarialVisualizer />
        </motion.section>

        {/* ── Corpora table ───────────────────────────────────────────── */}
        <section className="card overflow-hidden">
          <div className="flex items-center justify-between px-6 py-4 border-b" style={{ borderColor: 'var(--border)' }}>
            <h3 className="text-sm font-semibold text-text-primary font-display">Corpora</h3>
            <Link to="/corpus" className="btn-ghost text-xs">View all <ArrowRight size={11} /></Link>
          </div>
          {isLoading ? (
            <div className="p-6 space-y-3">
              {[1, 2, 3].map(i => (
                <div key={i} className="flex gap-4">
                  <div className="skeleton h-4 w-32" />
                  <div className="skeleton h-4 w-20" />
                  <div className="skeleton h-4 w-16" />
                </div>
              ))}
            </div>
          ) : corpora.length === 0 ? (
            <div className="py-16 text-center">
              <Database size={24} className="mx-auto mb-3 text-text-muted" />
              <p className="text-sm text-text-muted">No corpora yet</p>
              <Link to="/corpus" className="btn-primary mt-4 inline-flex text-xs">
                <Database size={12} /> Ingest Corpus
              </Link>
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Corpus</th><th>Domain</th><th>Status</th>
                  <th className="text-right">Chunks</th><th>Updated</th>
                </tr>
              </thead>
              <tbody>
                {corpora.slice(0, 8).map(corpus => (
                  <CorpusRow key={corpus.corpus_id} corpus={corpus} />
                ))}
              </tbody>
            </table>
          )}
        </section>
      </main>
    </div>
  );
}

const STATUS_COLOR: Record<string, string> = {
  ready: 'text-status-success', ingesting: 'text-status-warning',
  chunking: 'text-accent-400', pending: 'text-text-muted', failed: 'text-status-error',
};

function CorpusRow({ corpus }: { corpus: Corpus }) {
  return (
    <tr>
      <td>
        <Link to={`/corpus/${corpus.corpus_id}`} className="text-text-primary hover:text-accent-400 transition-colors">
          {corpus.corpus_id}
          <span className="block text-[10px] text-text-muted normal-case">{corpus.chunk_strategy}</span>
        </Link>
      </td>
      <td className="text-text-secondary capitalize">{corpus.domain}</td>
      <td className={STATUS_COLOR[corpus.status] || 'text-text-muted'}>{corpus.status}</td>
      <td className="text-right text-text-secondary">{corpus.chunk_count.toLocaleString()}</td>
      <td className="text-text-muted">{new Date(corpus.updated_at).toLocaleDateString()}</td>
    </tr>
  );
}
