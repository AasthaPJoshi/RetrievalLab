import { motion } from 'framer-motion';

export function ProblemSection() {
  return (
    <section className="py-section max-w-4xl mx-auto px-8">
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: '-10%' }}
        transition={{ duration: 0.4 }}
      >
        <h2 className="font-display font-bold text-text-primary mb-4" style={{ fontSize: '36px', letterSpacing: '-0.02em' }}>
          Retrieval quality is usually guessed, not measured
        </h2>
        <p className="text-text-secondary leading-relaxed" style={{ fontSize: '18px' }}>
          Most RAG systems pick sparse, dense, or hybrid retrieval based on intuition,
          not evidence. RetrievalLab makes the tradeoffs measurable: benchmark retrieval
          modes head-to-head, stress-test them against real-world query corruption, and
          quantify exactly where and why quality degrades in production.
        </p>
      </motion.div>
    </section>
  );
}
