import { motion } from 'framer-motion';
import { Shield, Gauge, GitCompare } from 'lucide-react';

const DIFFERENTIATORS = [
  {
    icon: Shield,
    title: 'Adversarial Robustness',
    desc: 'Standard benchmarks test clean queries. Real users send typos, truncated text, and off-topic noise. RetrievalLab quantifies the "production gap" across 6 real-world attack types.',
  },
  {
    icon: Gauge,
    title: 'Grounded Confidence',
    desc: "Instead of trusting an LLM's self-reported certainty, confidence is computed from retrieval signal — top-1 score, score gap, and reranker agreement — to flag hallucination risk.",
  },
  {
    icon: GitCompare,
    title: 'Mode-Level Attribution',
    desc: 'See exactly how much hybrid retrieval improves over sparse or dense alone, per query — not just an aggregate score, but where and why it wins.',
  },
];

export function DifferentiatorsSection() {
  return (
    <section className="py-section border-y" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
      <div className="max-w-container mx-auto px-8">
        <motion.h2
          initial={{ opacity: 0, y: 12 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-10%' }}
          transition={{ duration: 0.4 }}
          className="font-display font-bold text-text-primary mb-12 text-center"
          style={{ fontSize: '24px' }}
        >
          Three Things Most RAG Tools Don't Measure
        </motion.h2>
        <div className="grid md:grid-cols-3 gap-8">
          {DIFFERENTIATORS.map((d, i) => {
            const Icon = d.icon;
            return (
              <motion.div
                key={d.title}
                initial={{ opacity: 0, y: 16 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: '-10%' }}
                transition={{ duration: 0.4, delay: i * 0.1 }}
                className="card p-6"
              >
                <div className="w-10 h-10 flex items-center justify-center border mb-4"
                  style={{ borderColor: 'var(--border)', borderRadius: '8px', background: 'var(--accent-yellow)' }}>
                  <Icon size={18} className="text-black" />
                </div>
                <h3 className="font-semibold text-text-primary mb-2">{d.title}</h3>
                <p className="text-text-secondary text-sm leading-relaxed">{d.desc}</p>
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
