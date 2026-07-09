import { motion } from 'framer-motion';
import { ArrowRight } from 'lucide-react';

const STEPS = [
  { step: '01', name: 'Analyze',    desc: 'Classify query type & domain' },
  { step: '02', name: 'Retrieve',   desc: 'Sparse + dense + hybrid search' },
  { step: '03', name: 'Rerank',     desc: 'Cross-encoder reordering' },
  { step: '04', name: 'Synthesize', desc: 'LLM answer generation' },
  { step: '05', name: 'Format',     desc: 'Structured output + confidence' },
];

export function HowItWorksSection() {
  return (
    <section className="py-section max-w-container mx-auto px-8">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: '-10%' }}
        transition={{ duration: 0.4 }}
        className="text-center mb-12"
      >
        <h2 className="font-display font-bold text-text-primary mb-2" style={{ fontSize: '24px' }}>
          How It Works
        </h2>
        <p className="text-text-secondary">Every query runs through a 5-node LangGraph pipeline</p>
      </motion.div>

      <div className="flex items-stretch justify-between overflow-x-auto gap-2">
        {STEPS.map((node, i) => (
          <motion.div
            key={node.step}
            initial={{ opacity: 0, y: 12 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-10%' }}
            transition={{ duration: 0.3, delay: i * 0.08 }}
            className="flex items-center flex-shrink-0"
          >
            <div className="card p-4 w-40">
              <div className="font-mono text-xs mb-1" style={{ color: 'var(--accent)' }}>{node.step}</div>
              <div className="font-semibold text-text-primary">{node.name}</div>
              <div className="text-text-secondary text-xs mt-1">{node.desc}</div>
            </div>
            {i < STEPS.length - 1 && (
              <ArrowRight size={16} className="mx-2 text-text-muted shrink-0" />
            )}
          </motion.div>
        ))}
      </div>
    </section>
  );
}
