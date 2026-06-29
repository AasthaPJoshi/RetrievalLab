import { useQuery } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import {
  Database, Search, FlaskConical, Shield,
  TrendingUp, Layers, Cpu, Clock, ArrowRight, Zap, Brain
} from 'lucide-react';
import { Link } from 'react-router-dom';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, BarChart, Bar, Cell
} from 'recharts';

import { Header } from '@/components/layout/Header';
import { MetricCard, MetricCardSkeleton } from '@/components/ui/MetricCard';
import { api, type Corpus } from '@/lib/api';
import { cn, domainIcon, statusBadge, timeAgo, formatTokens } from '@/lib/utils';

const NDCG_HISTORY = [
  { day: 'Mon', hybrid: 0.723, dense: 0.685, sparse: 0.612 },
  { day: 'Tue', hybrid: 0.741, dense: 0.702, sparse: 0.625 },
  { day: 'Wed', hybrid: 0.768, dense: 0.718, sparse: 0.640 },
  { day: 'Thu', hybrid: 0.752, dense: 0.709, sparse: 0.631 },
  { day: 'Fri', hybrid: 0.801, dense: 0.745, sparse: 0.658 },
  { day: 'Sat', hybrid: 0.824, dense: 0.771, sparse: 0.672 },
  { day: 'Sun', hybrid: 0.847, dense: 0.801, sparse: 0.698 },
];

const DOMAIN_DATA = [
  { domain: 'Healthcare', ndcg: 0.847 },
  { domain: 'Finance',    ndcg: 0.812 },
  { domain: 'Legal',      ndcg: 0.779 },
];

const TIP = {
  backgroundColor: '#100C2E',
  border: '1px solid rgba(124,58,237,0.25)',
  borderRadius: '10px',
  color: '#DDD6FE',
  fontSize: '11px',
  boxShadow: '0 8px 32px rgba(0,0,0,0.6)',
};

export default function Dashboard() {
  const { data: corpora = [], isLoading } = useQuery({
    queryKey: ['corpora'],
    queryFn:  () => api.corpus.list({ limit: 50 }),
    refetchInterval: 10_000,
  });

  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn:  api.health.full,
    refetchInterval: 30_000,
  });

  const readyCorpora  = corpora.filter(c => c.status === 'ready');
  const totalChunks   = corpora.reduce((s, c) => s + c.chunk_count, 0);
  const totalTokens   = corpora.reduce((s, c) => s + c.total_tokens, 0);

  return (
    <div className="min-h-screen">
      <Header title="Dashboard" subtitle="RetrievalLab Research Command Center" />

      <main className="relative z-10 p-8 space-y-8">

        {/* Hero banner */}
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: [0.16,1,0.3,1] }}
          className="relative rounded-2xl overflow-hidden p-8"
          style={{
            background: 'linear-gradient(135deg, #100C2E 0%, #1B1545 50%, #100C2E 100%)',
            border: '1px solid rgba(124,58,237,0.2)',
          }}
        >
          {/* Constellation grid */}
          <div className="absolute inset-0 opacity-60"
            style={{
              backgroundImage: 'radial-gradient(circle, rgba(124,58,237,0.1) 1px, transparent 1px)',
              backgroundSize: '32px 32px',
            }} />

          {/* Purple orb top-left */}
          <div className="absolute -top-20 -left-20 w-72 h-72 rounded-full pointer-events-none"
            style={{ background: 'radial-gradient(circle, rgba(124,58,237,0.2) 0%, transparent 70%)', filter: 'blur(50px)', animation: 'orb-move 10s ease-in-out infinite alternate' }} />

          {/* Amber orb bottom-right */}
          <div className="absolute -bottom-16 -right-16 w-56 h-56 rounded-full pointer-events-none"
            style={{ background: 'radial-gradient(circle, rgba(245,158,11,0.12) 0%, transparent 70%)', filter: 'blur(40px)', animation: 'orb-move 14s ease-in-out infinite alternate-reverse' }} />

          {/* Top border — amber to purple */}
          <div className="absolute top-0 left-0 right-0 h-px"
            style={{ background: 'linear-gradient(90deg, transparent, rgba(245,158,11,0.7), rgba(124,58,237,0.7), transparent)' }} />

          <div className="relative z-10 flex items-start justify-between gap-8">
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-4">
                <span className="badge-purple text-[10px] tracking-widest uppercase">Production Ready</span>
                {health?.status === 'healthy' && (
                  <span className="badge-green text-[10px]">All Systems Operational</span>
                )}
              </div>
              <h2 className="text-3xl font-bold mb-3">
                <span className="text-white">Cross-Industry </span>
                <span className="text-gradient-amber-purple">Retrieval Research</span>
              </h2>
              <p className="text-sm leading-relaxed max-w-lg" style={{ color: 'rgba(167,139,250,0.7)' }}>
                Benchmark, stress-test, and advance RAG retrieval across 8 industry domains
                with 7 chunking strategies, 3 retrieval modes, and a 5-node agentic pipeline.
              </p>
              <div className="flex gap-3 mt-6">
                <Link to="/agent" className="btn-primary">
                  <Brain size={14} />
                  Ask AI Agent
                </Link>
                <Link to="/retrieve">
                  <button className="btn-ghost border"
                    style={{ borderColor: 'rgba(124,58,237,0.2)' }}>
                    <Search size={14} />
                    Search Corpus
                  </button>
                </Link>
              </div>
            </div>

            {/* Right stat pills */}
            <div className="hidden xl:flex flex-col gap-3 shrink-0">
              {[
                { v: readyCorpora.length, l: 'Active Corpora', accent: '#7C3AED' },
                { v: totalChunks.toLocaleString(), l: 'Total Chunks', accent: '#F59E0B' },
                { v: '7', l: 'Chunk Strategies', accent: '#D946EF' },
              ].map(({ v, l, accent }) => (
                <motion.div key={l}
                  whileHover={{ scale: 1.03, x: -2 }}
                  transition={{ type: 'spring', bounce: 0.4 }}
                  className="glass-card px-5 py-3 text-right min-w-[140px]"
                  style={{ borderColor: `${accent}25` }}>
                  <div className="text-2xl font-bold tabular-nums" style={{ color: accent }}>{v}</div>
                  <div className="text-[10px] mt-0.5" style={{ color: 'rgba(139,92,246,0.5)' }}>{l}</div>
                </motion.div>
              ))}
            </div>
          </div>
        </motion.div>

        {/* Metrics row */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {isLoading ? (
            Array.from({ length: 4 }).map((_, i) => <MetricCardSkeleton key={i} />)
          ) : (
            <>
              <MetricCard label="Active Corpora" value={readyCorpora.length}
                subtitle={`${corpora.length} total`} icon={<Database size={13} />}
                accent="purple" delay={0} />
              <MetricCard label="Total Chunks" value={formatTokens(totalChunks)}
                subtitle="indexed" icon={<Layers size={13} />}
                accent="amber" delay={0.06} />
              <MetricCard label="Total Tokens" value={formatTokens(totalTokens)}
                subtitle="content" icon={<Cpu size={13} />}
                accent="purple" delay={0.12} />
              <MetricCard label="Best NDCG@10" value={0.847}
                subtitle="healthcare · hybrid" isScore
                icon={<TrendingUp size={13} />} accent="amber" delay={0.18} />
            </>
          )}
        </div>

        {/* Charts + corpus table */}
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
          {/* NDCG trend */}
          <div className="xl:col-span-2 glass-card p-6">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h3 className="text-sm font-semibold text-white">NDCG@10 Trend</h3>
                <p className="text-xs mt-0.5" style={{ color: 'rgba(139,92,246,0.5)' }}>7-day retrieval quality by mode</p>
              </div>
              <div className="flex gap-4 text-xs" style={{ color: 'rgba(139,92,246,0.5)' }}>
                {[
                  { l: 'Hybrid', c: '#8B5CF6' },
                  { l: 'Dense',  c: '#F59E0B' },
                  { l: 'Sparse', c: '#D946EF' },
                ].map(({ l, c }) => (
                  <span key={l} className="flex items-center gap-1.5">
                    <span className="w-3 h-0.5 rounded inline-block" style={{ background: c }} />
                    {l}
                  </span>
                ))}
              </div>
            </div>
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={NDCG_HISTORY} margin={{ top: 5, right: 5, bottom: 0, left: -24 }}>
                <defs>
                  <linearGradient id="g1" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%"   stopColor="#8B5CF6" stopOpacity={0.25} />
                    <stop offset="100%" stopColor="#8B5CF6" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="g2" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%"   stopColor="#F59E0B" stopOpacity={0.2} />
                    <stop offset="100%" stopColor="#F59E0B" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(124,58,237,0.06)" />
                <XAxis dataKey="day" tick={{ fill: '#8B7CB8', fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis domain={[0.5,1.0]} tick={{ fill: '#8B7CB8', fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={TIP} />
                <Area type="monotone" dataKey="hybrid" stroke="#8B5CF6" strokeWidth={2.5} fill="url(#g1)" />
                <Area type="monotone" dataKey="dense"  stroke="#F59E0B" strokeWidth={1.5} fill="url(#g2)" />
                <Area type="monotone" dataKey="sparse" stroke="#D946EF" strokeWidth={1.5} fill="none" strokeDasharray="4 2" />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          {/* Domain bars */}
          <div className="glass-card p-6">
            <h3 className="text-sm font-semibold text-white mb-1">Domain Performance</h3>
            <p className="text-xs mb-5" style={{ color: 'rgba(139,92,246,0.5)' }}>NDCG@10 by industry</p>
            <div className="space-y-4">
              {DOMAIN_DATA.map(({ domain, ndcg }, i) => (
                <div key={domain}>
                  <div className="flex justify-between text-xs mb-1.5">
                    <span style={{ color: 'rgba(167,139,250,0.8)' }}>{domain}</span>
                    <span className="font-mono font-bold" style={{ color: i === 0 ? '#F59E0B' : '#8B5CF6' }}>
                      {ndcg.toFixed(3)}
                    </span>
                  </div>
                  <div className="score-bar">
                    <motion.div
                      className="h-full rounded-full"
                      style={{ background: i === 0
                        ? 'linear-gradient(90deg, #F59E0B, #D97706)'
                        : 'linear-gradient(90deg, #7C3AED, #8B5CF6)'
                      }}
                      initial={{ width: 0 }}
                      animate={{ width: `${ndcg * 100}%` }}
                      transition={{ delay: 0.4 + i * 0.1, duration: 0.9, ease: [0.16,1,0.3,1] }}
                    />
                  </div>
                </div>
              ))}
            </div>

            {/* System health mini */}
            {health && (
              <div className="mt-6 pt-4 border-t space-y-2" style={{ borderColor: 'rgba(124,58,237,0.1)' }}>
                <div className="text-[10px] font-semibold tracking-widest uppercase mb-2"
                  style={{ color: 'rgba(139,92,246,0.4)' }}>
                  Infrastructure
                </div>
                {health.components.map(c => (
                  <div key={c.name} className="flex items-center justify-between">
                    <span className="text-xs" style={{ color: 'rgba(139,92,246,0.55)' }}>{c.name}</span>
                    <div className="flex items-center gap-1.5">
                      {c.latency_ms && (
                        <span className="text-[10px] font-mono" style={{ color: 'rgba(139,92,246,0.35)' }}>
                          {c.latency_ms}ms
                        </span>
                      )}
                      <div className={cn(
                        'w-1.5 h-1.5 rounded-full',
                        c.status === 'healthy' ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'
                      )} />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Corpora + quick actions */}
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
          <div className="xl:col-span-2 glass-card overflow-hidden">
            <div className="flex items-center justify-between px-6 py-4 border-b"
              style={{ borderColor: 'rgba(124,58,237,0.1)' }}>
              <h3 className="text-sm font-semibold text-white">Corpora</h3>
              <Link to="/corpus">
                <button className="btn-ghost text-xs">View all <ArrowRight size={11} /></button>
              </Link>
            </div>
            {isLoading ? (
              <div className="p-6 space-y-3">
                {[1,2,3].map(i => (
                  <div key={i} className="flex gap-4">
                    <div className="skeleton h-4 w-32 rounded" />
                    <div className="skeleton h-4 w-20 rounded" />
                    <div className="skeleton h-4 w-16 rounded" />
                  </div>
                ))}
              </div>
            ) : corpora.length === 0 ? (
              <div className="py-16 text-center">
                <Database size={28} className="mx-auto mb-3" style={{ color: 'rgba(124,58,237,0.3)' }} />
                <p className="text-sm" style={{ color: 'rgba(139,92,246,0.5)' }}>No corpora yet</p>
                <Link to="/corpus">
                  <button className="btn-primary mt-4 text-xs">
                    <Database size={12} /> Ingest Corpus
                  </button>
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
                  {corpora.slice(0, 8).map((corpus, i) => (
                    <CorpusRow key={corpus.corpus_id} corpus={corpus} index={i} />
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {/* Quick actions */}
          <div className="glass-card p-6">
            <h3 className="text-sm font-semibold text-white mb-5">Quick Actions</h3>
            <div className="space-y-2">
              {[
                { to:'/agent',       label:'Ask AI Agent',    icon:Brain,       color:'#8B5CF6', desc:'5-node pipeline' },
                { to:'/retrieve',    label:'Search Corpus',   icon:Search,      color:'#F59E0B', desc:'Hybrid retrieval' },
                { to:'/eval',        label:'Run Evaluation',  icon:FlaskConical,color:'#D946EF', desc:'NDCG · MRR · MAP' },
                { to:'/adversarial', label:'Stress Test',     icon:Shield,      color:'#EF4444', desc:'6 attack types' },
              ].map(({ to, label, icon: Icon, color, desc }) => (
                <Link key={to} to={to}>
                  <motion.div
                    whileHover={{ x: 3, transition: { duration: 0.15 } }}
                    className="flex items-center gap-3 p-3 rounded-xl group cursor-pointer transition-all"
                    style={{ border: '1px solid transparent' }}
                    onMouseEnter={e => (e.currentTarget.style.borderColor = `${color}20`)}
                    onMouseLeave={e => (e.currentTarget.style.borderColor = 'transparent')}
                  >
                    <div className="w-8 h-8 flex items-center justify-center rounded-lg shrink-0"
                      style={{ background: `${color}15`, border: `1px solid ${color}20` }}>
                      <Icon size={14} style={{ color }} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-white">{label}</div>
                      <div className="text-xs mt-0.5" style={{ color: 'rgba(139,92,246,0.45)' }}>{desc}</div>
                    </div>
                    <ArrowRight size={12} className="text-purple-600 group-hover:text-purple-400 group-hover:translate-x-1 transition-all" />
                  </motion.div>
                </Link>
              ))}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

function CorpusRow({ corpus, index }: { corpus: Corpus; index: number }) {
  const statusColor: Record<string, string> = {
    ready: '#10B981', ingesting: '#F59E0B', chunking: '#8B5CF6',
    pending: '#8B7CB8', failed: '#EF4444',
  };

  return (
    <motion.tr
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.04 }}
      className="group"
    >
      <td>
        <Link to={`/corpus/${corpus.corpus_id}`} className="flex items-center gap-2">
          <span className="text-base">{domainIcon(corpus.domain)}</span>
          <div>
            <div className="text-sm font-medium text-white group-hover:text-purple-300 transition-colors">
              {corpus.corpus_id}
            </div>
            <div className="text-xs" style={{ color: 'rgba(139,92,246,0.45)' }}>{corpus.chunk_strategy}</div>
          </div>
        </Link>
      </td>
      <td className="text-xs capitalize" style={{ color: 'rgba(167,139,250,0.6)' }}>{corpus.domain}</td>
      <td>
        <div className="flex items-center gap-1.5">
          <div className="w-1.5 h-1.5 rounded-full animate-pulse"
            style={{ background: statusColor[corpus.status] || '#8B7CB8' }} />
          <span className="text-xs capitalize" style={{ color: statusColor[corpus.status] || '#8B7CB8' }}>
            {corpus.status}
          </span>
        </div>
      </td>
      <td className="text-right font-mono text-xs" style={{ color: '#F59E0B' }}>
        {corpus.chunk_count.toLocaleString()}
      </td>
      <td className="text-xs" style={{ color: 'rgba(139,92,246,0.35)' }}>{timeAgo(corpus.updated_at)}</td>
    </motion.tr>
  );
}
