import { motion } from 'framer-motion';

const STACK = [
  { name: 'LangGraph',   role: '5-node agent pipeline' },
  { name: 'FAISS/Chroma', role: 'Dense vector retrieval' },
  { name: 'rank-bm25',   role: 'Sparse lexical retrieval' },
  { name: 'RRF',         role: 'Hybrid rank fusion' },
  { name: 'PostgreSQL',  role: 'Corpus + eval storage (pgvector)' },
  { name: 'Prometheus',  role: 'Metrics & observability' },
  { name: 'MLflow',      role: 'Experiment tracking' },
  { name: 'FastAPI',     role: 'Backend API' },
];

export function BuiltWithSection() {
  return (
    <section className="py-16 border-y" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
      <div className="max-w-container mx-auto px-8">
        <motion.h2
          initial={{ opacity: 0, y: 12 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-10%' }}
          transition={{ duration: 0.4 }}
          className="font-display font-bold text-text-primary mb-8 text-center"
          style={{ fontSize: '24px' }}
        >
          Built With
        </motion.h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          {STACK.map((tech, i) => (
            <motion.div
              key={tech.name}
              initial={{ opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-10%' }}
              transition={{ duration: 0.3, delay: i * 0.04 }}
              className="card p-4 text-center"
            >
              <div className="font-mono font-semibold text-text-primary text-sm">{tech.name}</div>
              <div className="text-text-secondary text-xs mt-1">{tech.role}</div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
