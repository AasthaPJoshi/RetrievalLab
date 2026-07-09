export function EvalEngineIntro() {
  return (
    <div className="space-y-8 mb-4">
      {/* Main Intro Section */}
      <div className="card p-8">
        <h2 className="text-2xl font-bold text-text-primary mb-4">
          What is the Eval Engine?
        </h2>

        <p className="text-text-secondary mb-6 leading-relaxed">
          Evaluate your retrieval system's performance against your queries and
          ground-truth relevance judgments. Input a single query, the chunks your
          system retrieved, and which chunks are actually relevant — we'll compute
          comprehensive IR metrics instantly.
        </p>

        {/* Input/Output Cards */}
        <div className="grid md:grid-cols-2 gap-6 mb-8">
          {/* Input Card */}
          <div className="rounded-sm border p-6" style={{ borderColor: 'var(--border)', background: 'var(--bg-surface)' }}>
            <h3 className="font-semibold text-text-primary mb-4 flex items-center gap-2">
              <span className="text-lg">📥</span>
              What You Provide
            </h3>
            <ul className="space-y-3 text-text-secondary text-sm">
              <li className="flex gap-3">
                <span className="font-mono text-accent-600 shrink-0">1</span>
                <span><strong className="text-text-primary">Query:</strong> What you're searching for</span>
              </li>
              <li className="flex gap-3">
                <span className="font-mono text-accent-600 shrink-0">2</span>
                <span><strong className="text-text-primary">Retrieved IDs:</strong> Chunks your system returned (ranked order)</span>
              </li>
              <li className="flex gap-3">
                <span className="font-mono text-accent-600 shrink-0">3</span>
                <span><strong className="text-text-primary">Relevant IDs:</strong> Which chunks are truly relevant + their grade (0.0 to 1.0)</span>
              </li>
            </ul>
          </div>

          {/* Output Card */}
          <div className="rounded-sm border p-6" style={{ borderColor: 'var(--border)', background: 'var(--bg-surface)' }}>
            <h3 className="font-semibold text-text-primary mb-4 flex items-center gap-2">
              <span className="text-lg">📊</span>
              What You Get
            </h3>
            <ul className="space-y-2 text-text-secondary text-sm">
              <li><strong className="text-text-primary font-mono">NDCG@10:</strong> Ranking quality (0 to 1, higher is better)</li>
              <li><strong className="text-text-primary font-mono">MRR:</strong> Position of first relevant result</li>
              <li><strong className="text-text-primary font-mono">MAP:</strong> Average precision across all results</li>
              <li><strong className="text-text-primary font-mono">Precision/Recall:</strong> Coverage of relevant chunks</li>
              <li><strong className="text-text-primary font-mono">Hit Rate:</strong> Was any relevant chunk retrieved?</li>
            </ul>
          </div>
        </div>

        {/* Eval vs Benchmark Explainer */}
        <div className="rounded-sm border p-6" style={{ borderColor: 'rgba(14,165,233,0.25)', background: 'rgba(14,165,233,0.05)' }}>
          <h3 className="font-semibold text-text-primary mb-4 flex items-center gap-2">
            <span className="text-lg">🔄</span>
            Eval vs Benchmark: What's the Difference?
          </h3>

          <div className="grid md:grid-cols-2 gap-6">
            {/* EVAL */}
            <div className="space-y-2">
              <div className="inline-block px-3 py-1 text-white text-xs font-mono rounded-sm" style={{ background: 'var(--accent)' }}>
                EVAL (You Are Here)
              </div>
              <p className="text-text-secondary text-sm">
                <strong className="text-text-primary">Manual evaluation</strong> of individual queries
              </p>
              <ul className="text-text-muted text-xs space-y-1 ml-4">
                <li>✓ You provide: 1 query + retrieval results + ground truth</li>
                <li>✓ Output: 6 metrics for that single evaluation</li>
                <li>✓ Best for: Testing custom queries, debugging your system</li>
              </ul>
            </div>

            {/* BENCHMARK */}
            <div className="space-y-2">
              <div className="inline-block px-3 py-1 text-white text-xs font-mono rounded-sm" style={{ background: '#94A3B8' }}>
                BENCHMARK (Planned)
              </div>
              <p className="text-text-secondary text-sm">
                <strong className="text-text-primary">Systematic evaluation</strong> across standard datasets
              </p>
              <ul className="text-text-muted text-xs space-y-1 ml-4">
                <li>✓ Pre-built datasets: TREC, BEIR, SciFact, etc.</li>
                <li>✓ Output: Metrics across 100+ queries + comparisons</li>
                <li>✓ Best for: Competitive analysis, baseline comparisons</li>
              </ul>
            </div>
          </div>
        </div>
      </div>

      {/* Call-to-Action */}
      <div className="text-center">
        <p className="text-text-primary font-medium">
          👇 Let's evaluate a query:
        </p>
      </div>
    </div>
  );
}
