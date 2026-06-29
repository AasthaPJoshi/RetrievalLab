// =============================================================================
// RetrievalLab — Metrics & Observability Page
// =============================================================================

import { useQuery } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import { Activity, Server, Database, Cpu, Clock, CheckCircle, XCircle, AlertCircle } from 'lucide-react';
import { Header } from '@/components/layout/Header';
import { api } from '@/lib/api';
import { cn, formatMs } from '@/lib/utils';

export default function MetricsPage() {
  const { data: health, isLoading } = useQuery({
    queryKey:       ['health-full'],
    queryFn:        api.health.full,
    refetchInterval: 5_000,
  });

  return (
    <div className="min-h-screen">
      <Header title="Metrics & Observability" subtitle="Infrastructure health · API performance · System telemetry" />

      <main className="p-8 space-y-8 max-w-5xl mx-auto">
        {/* Overall status */}
        {health && (
          <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
            className={cn(
              'glass-card p-6 border-l-4',
              health.status === 'healthy'   ? 'border-accent-green' :
              health.status === 'degraded'  ? 'border-accent-amber' : 'border-accent-red'
            )}>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className={cn(
                  'w-12 h-12 rounded-xl flex items-center justify-center',
                  health.status === 'healthy' ? 'bg-emerald-400/10' : 'bg-accent-amber/10'
                )}>
                  <Activity size={22} className={
                    health.status === 'healthy' ? 'text-emerald-400' : 'text-amber-400'
                  } />
                </div>
                <div>
                  <div className="text-lg font-bold text-white capitalize">
                    System {health.status}
                  </div>
                  <div className="text-xs text-slate-500">
                    {health.components.filter(c => c.status === 'healthy').length} of {health.components.length} components healthy
                    · Uptime {Math.floor(health.uptime_s / 60)}m {Math.floor(health.uptime_s % 60)}s
                  </div>
                </div>
              </div>
              <div className="text-right">
                <div className="text-xs text-slate-500">Version</div>
                <div className="font-mono text-sm text-purple-300">{health.version}</div>
              </div>
            </div>
          </motion.div>
        )}

        {/* Component health cards */}
        <section>
          <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-4">
            Infrastructure Components
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {isLoading ? (
              Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="glass-card p-5 space-y-3">
                  <div className="flex gap-3">
                    <div className="skeleton w-10 h-10 rounded-xl" />
                    <div className="space-y-1.5 flex-1">
                      <div className="skeleton h-4 w-24 rounded" />
                      <div className="skeleton h-3 w-16 rounded" />
                    </div>
                  </div>
                </div>
              ))
            ) : (
              health?.components.map((component, i) => (
                <ComponentCard key={component.name} component={component} index={i} />
              ))
            )}
          </div>
        </section>

        {/* Prometheus info */}
        <section>
          <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-4">
            Metrics Endpoints
          </h2>
          <div className="glass-card overflow-hidden">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Metric</th>
                  <th>Type</th>
                  <th>Labels</th>
                  <th>Description</th>
                </tr>
              </thead>
              <tbody>
                {[
                  { name: 'retrievallab_retrieval_latency_ms', type: 'Histogram', labels: 'corpus_id, mode, strategy', desc: 'End-to-end retrieval latency' },
                  { name: 'retrievallab_requests_total',       type: 'Counter',   labels: 'corpus_id, mode, status',   desc: 'Total retrieval requests' },
                  { name: 'retrievallab_ndcg_at_10',           type: 'Gauge',     labels: 'corpus_id, retriever_mode', desc: 'Latest NDCG@10 score' },
                  { name: 'retrievallab_active_requests',      type: 'Gauge',     labels: '—',                         desc: 'Currently active requests' },
                  { name: 'retrievallab_embed_cache_hits_total', type: 'Counter', labels: 'model',                     desc: 'Embedding cache hits' },
                  { name: 'retrievallab_agent_node_latency_ms', type: 'Histogram',labels: 'node_name',                 desc: 'Agent pipeline node latency' },
                ].map(row => (
                  <tr key={row.name}>
                    <td><code className="font-mono text-xs text-purple-300">{row.name}</code></td>
                    <td><span className="badge-purple text-[10px]">{row.type}</span></td>
                    <td className="text-xs font-mono text-slate-500">{row.labels}</td>
                    <td className="text-xs text-slate-400">{row.desc}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="mt-4 p-4 rounded-lg text-xs text-slate-400"
            style={{ background: 'rgba(124,58,237,0.04)', border: '1px solid rgba(124,58,237,0.1)' }}>
            <span className="text-purple-300 font-medium">Prometheus:</span> Scrape{' '}
            <code className="font-mono text-slate-300 bg-white/5 px-1.5 py-0.5 rounded">http://localhost:9090/metrics</code>
            {' '}· <span className="text-purple-300 font-medium">MLflow:</span>{' '}
            <code className="font-mono text-slate-300 bg-white/5 px-1.5 py-0.5 rounded">http://localhost:5000</code>
          </div>
        </section>
      </main>
    </div>
  );
}

const COMPONENT_ICONS: Record<string, any> = {
  postgresql: Database,
  redis:      Cpu,
  minio:      Server,
  chromadb:   Database,
};

function ComponentCard({ component, index }: { component: any; index: number }) {
  const Icon = COMPONENT_ICONS[component.name.toLowerCase()] || Server;
  const isHealthy  = component.status === 'healthy';
  const isDegraded = component.status === 'degraded';

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.06 }}
      className="glass-card p-5"
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={cn(
            'w-10 h-10 rounded-xl flex items-center justify-center',
            isHealthy  ? 'bg-emerald-400/10' :
            isDegraded ? 'bg-accent-amber/10' : 'bg-red-400/10'
          )}>
            <Icon size={16} className={
              isHealthy  ? 'text-emerald-400' :
              isDegraded ? 'text-amber-400' : 'text-red-400'
            } />
          </div>
          <div>
            <div className="text-sm font-semibold text-white capitalize">{component.name}</div>
            {component.detail && (
              <div className="text-xs text-slate-500 mt-0.5">{component.detail}</div>
            )}
          </div>
        </div>

        <div className="text-right">
          <div className="flex items-center gap-1.5 justify-end mb-1">
            {isHealthy  ? <CheckCircle  size={13} className="text-emerald-400" /> :
             isDegraded ? <AlertCircle  size={13} className="text-amber-400" /> :
                          <XCircle      size={13} className="text-red-400" />}
            <span className={cn('text-xs font-medium capitalize',
              isHealthy ? 'text-emerald-400' : isDegraded ? 'text-amber-400' : 'text-red-400'
            )}>
              {component.status}
            </span>
          </div>
          {component.latency_ms && (
            <div className="flex items-center gap-1 justify-end text-xs text-slate-600">
              <Clock size={10} />
              {formatMs(component.latency_ms)}
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
}
