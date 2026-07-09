import { motion } from 'framer-motion';
import { ArrowRight, PlayCircle } from 'lucide-react';
import { Link } from 'react-router-dom';

export function Hero() {
  return (
    <section className="relative border-b" style={{ borderColor: 'var(--border)' }}>
      {/* Subtle dot grid background */}
      <div className="absolute inset-0 pointer-events-none opacity-60"
        style={{
          backgroundImage: 'radial-gradient(circle, #E5E7EB 1px, transparent 1px)',
          backgroundSize: '28px 28px',
          maskImage: 'linear-gradient(to bottom, rgba(0,0,0,0.6) 0%, transparent 85%)',
        }} />

      <div className="relative max-w-container mx-auto px-8 pt-24 pb-20 text-center">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          <span className="badge-purple text-xs mb-6 inline-flex">Open benchmarking platform</span>

          <h1 className="font-display font-extrabold tracking-tight-display text-text-primary mx-auto max-w-3xl"
            style={{ fontSize: '48px', lineHeight: 1.1 }}>
            RAG Evaluation Platform
          </h1>

          <p className="text-text-secondary mx-auto max-w-xl mt-5" style={{ fontSize: '16px' }}>
            Hybrid BM25 + Dense retrieval comparison, chunking strategy benchmarks, and
            adversarial robustness testing — all in one instrument built for research teams.
          </p>

          <div className="flex items-center justify-center gap-3 mt-8">
            <Link to="/agent" className="btn-primary">
              Get Started <ArrowRight size={16} />
            </Link>
            <Link to="/retrieve" className="btn-secondary">
              <PlayCircle size={16} /> View Demo
            </Link>
          </div>
        </motion.div>

        {/* Screenshot / interactive preview placeholder */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.15 }}
          className="mt-16 card p-2 mx-auto"
          style={{ maxWidth: '1100px' }}
        >
          <div className="rounded-sm overflow-hidden border" style={{ borderColor: 'var(--border)' }}>
            <div className="flex items-center gap-1.5 px-3 py-2.5 border-b" style={{ borderColor: 'var(--border)', background: 'var(--bg-surface)' }}>
              <span className="w-2.5 h-2.5 rounded-full bg-[#E5E7EB]" />
              <span className="w-2.5 h-2.5 rounded-full bg-[#E5E7EB]" />
              <span className="w-2.5 h-2.5 rounded-full bg-[#E5E7EB]" />
            </div>
            <div className="p-10 text-left grid grid-cols-3 gap-4" style={{ background: '#fff' }}>
              {[
                { label: 'Sparse (BM25)', value: '0.698' },
                { label: 'Dense (Pinecone)', value: '0.801' },
                { label: 'Hybrid', value: '0.847', accent: true },
              ].map(m => (
                <div key={m.label} className="border rounded-sm p-4" style={{ borderColor: 'var(--border)' }}>
                  <div className="text-xs text-text-muted mb-2">{m.label}</div>
                  <div className={`tabular-mono text-2xl font-bold ${m.accent ? 'text-accent-500' : 'text-text-primary'}`}>
                    {m.value}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
