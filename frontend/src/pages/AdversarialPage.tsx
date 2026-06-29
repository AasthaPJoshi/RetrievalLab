// =============================================================================
// RetrievalLab — Adversarial Robustness Page
// 6 attack types: typo noise, synonym substitution, injection, truncation, trap, domain shift
// =============================================================================

import { motion } from 'framer-motion';
import { Shield, Zap, Type, Scissors, AlertTriangle, Globe, Repeat } from 'lucide-react';
import { Header } from '@/components/layout/Header';

const ATTACKS = [
  {
    name: 'Typo Noise',
    icon: Type,
    color: 'text-purple-300',
    bg: 'bg-purple-500/10',
    border: 'border-purple-500/20',
    description: 'Injects character-level typos (15% error rate). Tests robustness to OCR errors, fast typing, and mobile autocorrect failures.',
    example_in:  '"cardiac arrest symptoms"',
    example_out: '"cadriac arresst symptons"',
    metric: 'NDCG@10 retention',
    typical: '~92% retention',
  },
  {
    name: 'Synonym Substitution',
    icon: Repeat,
    color: 'text-purple-400',
    bg: 'bg-purple-500/10',
    border: 'border-purple-500/20',
    description: 'Replaces key content words with synonyms. Tests vocabulary mismatch handling and semantic coverage of dense retrieval.',
    example_in:  '"blood pressure treatment"',
    example_out: '"hypertension therapy"',
    metric: 'NDCG@10 retention',
    typical: '~88% retention',
  },
  {
    name: 'Irrelevant Injection',
    icon: Zap,
    color: 'text-amber-400',
    bg: 'bg-amber-500/10',
    border: 'border-amber-500/20',
    description: 'Injects off-topic text into queries. Simulates chatbot users including irrelevant context alongside their actual question.',
    example_in:  '"diabetes diagnosis"',
    example_out: '"BTW my cat is sick. diabetes diagnosis"',
    metric: 'Precision@10 retention',
    typical: '~85% retention',
  },
  {
    name: 'Query Truncation',
    icon: Scissors,
    color: 'text-green-400',
    bg: 'bg-green-500/10',
    border: 'border-green-500/20',
    description: 'Cuts query at 50% of length. Simulates autocomplete submissions, voice cutoffs, and time-pressured Enter presses.',
    example_in:  '"What are the first-line treatments for type 2 diabetes?"',
    example_out: '"What are the first-line"',
    metric: 'Recall@10 retention',
    typical: '~78% retention',
  },
  {
    name: 'Semantic Trap',
    icon: AlertTriangle,
    color: 'text-red-400',
    bg: 'bg-red-500/10',
    border: 'border-red-500/20',
    description: 'Creates plausibly related but topically wrong queries. Tests false positive rate and precision under adversarial conditions.',
    example_in:  '"how to treat diabetes"',
    example_out: '"how NOT to treat diabetes complications"',
    metric: 'Precision@10 retention',
    typical: '~71% retention',
  },
  {
    name: 'Domain Shift',
    icon: Globe,
    color: 'text-pink-400',
    bg: 'bg-pink-500/10',
    border: 'border-pink-500/20',
    description: 'Shifts query to different domain vocabulary. Tests cross-domain retrieval robustness and graceful degradation.',
    example_in:  '"diabetes diagnosis"',
    example_out: '"Per SEC regulation, in a court of law, diabetes diagnosis"',
    metric: 'NDCG@10 retention',
    typical: '~82% retention',
  },
];

export default function AdversarialPage() {
  return (
    <div className="min-h-screen">
      <Header
        title="Adversarial Robustness"
        subtitle="Stress-test your retrieval system with 6 real-world attack types"
      />

      <main className="p-8 space-y-8 max-w-6xl mx-auto">
        {/* Hero explanation */}
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
          className="glass-card p-6">
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 rounded-xl flex items-center justify-center shrink-0"
              style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.2)' }}>
              <Shield size={22} className="text-red-400" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-white mb-1">Why Adversarial Testing Matters</h2>
              <p className="text-sm text-slate-400 leading-relaxed max-w-3xl">
                Standard benchmarks (BEIR, MIRACL) test clean, expert-crafted queries.
                Real users send noisy, incomplete, off-topic queries — and your system needs to handle them gracefully.
                A system scoring 0.85 NDCG@10 on BEIR may score 0.60 on real queries.
                The adversarial harness quantifies this <span className="text-purple-300 font-medium">"production gap"</span> across 6 attack dimensions.
              </p>
            </div>
          </div>
        </motion.div>

        {/* Attack Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {ATTACKS.map((attack, i) => (
            <AttackCard key={attack.name} attack={attack} index={i} />
          ))}
        </div>

        {/* Robustness formula */}
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="glass-card p-6">
          <h3 className="text-sm font-semibold text-white mb-4">Overall Robustness Score Formula</h3>
          <div className="font-mono text-sm text-purple-300 p-4 rounded-lg mb-4"
            style={{ background: 'rgba(124,58,237,0.05)', border: '1px solid rgba(124,58,237,0.1)' }}>
            robustness = mean(attacked_NDCG) / baseline_NDCG × 100
          </div>
          <div className="grid grid-cols-3 gap-4 text-xs">
            {[
              { range: '≥ 90%', label: 'Excellent',  desc: 'Production-ready robustness', color: 'text-emerald-400' },
              { range: '75-90%', label: 'Good',      desc: 'Minor hardening needed',       color: 'text-purple-300' },
              { range: '< 75%', label: 'Fragile',    desc: 'Significant improvements required', color: 'text-red-400' },
            ].map(({ range, label, desc, color }) => (
              <div key={label} className="p-3 rounded-lg" style={{ background: 'rgba(255,255,255,0.03)' }}>
                <div className={cn('text-lg font-bold font-mono', color)}>{range}</div>
                <div className="text-white text-xs font-medium mt-0.5">{label}</div>
                <div className="text-slate-500 mt-0.5">{desc}</div>
              </div>
            ))}
          </div>
          <p className="text-xs text-slate-500 mt-4">
            Run the adversarial harness via CLI:{' '}
            <code className="font-mono text-purple-300 bg-white/5 px-2 py-0.5 rounded">
              python -m eval.adversarial.harness --corpus-id healthcare_v1 --mode hybrid
            </code>
          </p>
        </motion.div>
      </main>
    </div>
  );
}

function AttackCard({ attack, index }: { attack: typeof ATTACKS[0]; index: number }) {
  const Icon = attack.icon;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.06 }}
      className="glass-card p-5 group"
    >
      <div className="flex items-center gap-3 mb-3">
        <div className={cn('w-9 h-9 rounded-xl flex items-center justify-center shrink-0', attack.bg, `border ${attack.border}`)}>
          <Icon size={16} className={attack.color} />
        </div>
        <div>
          <div className="text-sm font-semibold text-white">{attack.name}</div>
          <div className={cn('text-[10px] font-medium', attack.color)}>{attack.typical}</div>
        </div>
      </div>

      <p className="text-xs text-slate-400 leading-relaxed mb-4">{attack.description}</p>

      <div className="space-y-2 p-3 rounded-lg" style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.04)' }}>
        <div>
          <div className="text-[10px] text-slate-600 uppercase tracking-wider mb-0.5">Original</div>
          <div className="text-xs font-mono text-slate-300">{attack.example_in}</div>
        </div>
        <div className="h-px bg-white/5" />
        <div>
          <div className="text-[10px] text-slate-600 uppercase tracking-wider mb-0.5">Attacked</div>
          <div className={cn('text-xs font-mono', attack.color)}>{attack.example_out}</div>
        </div>
      </div>

      <div className="mt-3 text-[10px] text-slate-600">
        Measures: <span className="text-slate-500">{attack.metric}</span>
      </div>
    </motion.div>
  );
}

function cn(...classes: (string | undefined | false)[]) {
  return classes.filter(Boolean).join(' ');
}
