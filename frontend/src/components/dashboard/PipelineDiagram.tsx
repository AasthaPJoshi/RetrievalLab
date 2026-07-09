import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Brain, Zap, Shield, Quote, FileText, Check } from 'lucide-react';

const NODES = [
  { id: 1, name: 'Analyze',    desc: 'Classify + expand query',      icon: Brain,     latencyMs: 42 },
  { id: 2, name: 'Retrieve',   desc: 'Sparse + dense + hybrid',      icon: Zap,       latencyMs: 118 },
  { id: 3, name: 'Rerank',     desc: 'Cross-encoder + MMR',          icon: Shield,    latencyMs: 76 },
  { id: 4, name: 'Synthesize', desc: 'LLM answer with grounding',    icon: Quote,     latencyMs: 890 },
  { id: 5, name: 'Format',     desc: 'Citations + confidence score', icon: FileText,  latencyMs: 14 },
];

const TOTAL_MS = NODES.reduce((s, n) => s + n.latencyMs, 0);
const CYCLE_MS = 4200;

export function PipelineDiagram() {
  const [activeId, setActiveId] = useState(0);

  useEffect(() => {
    let cancelled = false;
    let timeouts: ReturnType<typeof setTimeout>[] = [];

    const run = () => {
      if (cancelled) return;
      setActiveId(0);
      let elapsed = 200;
      NODES.forEach((node, i) => {
        timeouts.push(setTimeout(() => setActiveId(node.id), elapsed));
        elapsed += 500 + i * 40;
      });
      timeouts.push(setTimeout(() => setActiveId(-1), elapsed));
      timeouts.push(setTimeout(run, CYCLE_MS));
    };
    run();

    return () => { cancelled = true; timeouts.forEach(clearTimeout); };
  }, []);

  return (
    <div className="card p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-sm font-semibold text-text-primary font-display">Agent Pipeline</h3>
          <p className="text-xs mt-0.5 text-text-muted">LangGraph · 5-node execution trace</p>
        </div>
        <div className="text-right">
          <div className="tabular-mono text-xs text-text-muted">total latency</div>
          <div className="tabular-mono text-sm text-accent-400 font-semibold">{TOTAL_MS}ms</div>
        </div>
      </div>

      <div className="flex items-stretch gap-0">
        {NODES.map((node, i) => {
          const Icon = node.icon;
          const isActive = activeId === node.id;
          const isComplete = activeId > node.id || activeId === -1;
          return (
            <div key={node.id} className="flex items-stretch flex-1">
              <div className="flex flex-col items-center flex-1 gap-2">
                <div className={`pipeline-node ${isActive ? 'active' : isComplete ? 'complete' : ''}`}>
                  {isComplete && !isActive ? (
                    <Check size={16} className="text-status-success" />
                  ) : (
                    <Icon size={16} className={isActive ? 'text-accent-400' : 'text-text-muted'} />
                  )}
                </div>
                <div className="text-center">
                  <div className={`text-xs font-medium font-mono ${isActive ? 'text-text-primary' : 'text-text-secondary'}`}>
                    {node.name}
                  </div>
                  <div className="text-[10px] text-text-muted mt-0.5 max-w-[100px] leading-tight">
                    {node.desc}
                  </div>
                  <div className="tabular-mono text-[10px] mt-1 text-text-muted">
                    {node.latencyMs}ms
                  </div>
                </div>
              </div>
              {i < NODES.length - 1 && (
                <div className="flex items-center px-1" style={{ marginTop: '20px' }}>
                  <div className="w-6 h-px relative overflow-hidden" style={{ background: 'var(--border)' }}>
                    {isComplete && (
                      <motion.div
                        className="absolute inset-0"
                        style={{ background: 'var(--accent)' }}
                        initial={{ scaleX: 0 }}
                        animate={{ scaleX: 1 }}
                        transition={{ duration: 0.3 }}
                      />
                    )}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
