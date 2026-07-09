import { motion } from 'framer-motion';
import { CountUp } from '@/components/ui/CountUp';

const METRICS = [
  { value: 0.847, decimals: 3, label: 'NDCG@10', sub: 'healthcare · hybrid mode' },
  { value: 18.9, decimals: 1, prefix: '+', suffix: '%', label: 'vs. sparse baseline', sub: 'hybrid retrieval improvement' },
  { value: 3, decimals: 0, label: 'retrieval modes', sub: 'sparse, dense, hybrid' },
];

export function MetricsShowcase() {
  return (
    <section className="border-b" style={{ borderColor: 'var(--border)' }}>
      <div className="max-w-container mx-auto px-8 py-20">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-10%' }}
          transition={{ duration: 0.4 }}
          className="text-center mb-12"
        >
          <h2 className="font-display font-bold tracking-tight-display text-text-primary" style={{ fontSize: '28px' }}>
            Benchmarked, not guessed
          </h2>
          <p className="text-text-secondary mt-2" style={{ fontSize: '16px' }}>
            Real numbers from our evaluation harness, updated continuously.
          </p>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {METRICS.map((m, i) => (
            <motion.div
              key={m.label}
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-10%' }}
              transition={{ duration: 0.4, delay: i * 0.08 }}
              className="card p-8 text-center"
            >
              <div className="tabular-mono font-extrabold text-text-primary" style={{ fontSize: '40px' }}>
                <CountUp value={m.value} decimals={m.decimals} prefix={m.prefix} suffix={m.suffix} />
              </div>
              <div className="mt-3 text-sm font-semibold" style={{ color: 'var(--accent)' }}>{m.label}</div>
              <div className="text-xs text-text-muted mt-1">{m.sub}</div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
