import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';

const DATA = [
  { mode: 'Sparse (BM25)',      ndcg: 0.698 },
  { mode: 'Dense (Pinecone)',   ndcg: 0.801 },
  { mode: 'Hybrid',             ndcg: 0.847 },
];

// Sparse = black, Dense = shadow gray, Hybrid = Action Orange (best result, made to pop)
const BAR_COLORS = ['#000000', '#6c6c6c', '#ff5b29'];

const TOOLTIP_STYLE = {
  background: '#FFFFFF',
  border: '1px solid #000000',
  borderRadius: '8px',
  color: '#000000',
  fontSize: '11px',
  fontFamily: 'JetBrains Mono, monospace',
};

export function ModeComparisonChart() {
  return (
    <div className="card p-6">
      <h3 className="text-sm font-semibold text-text-primary font-display mb-1">Mode Comparison</h3>
      <p className="text-xs text-text-secondary mb-5">NDCG@10 — healthcare corpus, 7-day average</p>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={DATA} layout="vertical" margin={{ top: 0, right: 24, bottom: 0, left: 0 }}>
          <CartesianGrid strokeDasharray="2 4" stroke="#E5E5E5" horizontal={false} />
          <XAxis type="number" domain={[0, 1]} tick={{ fill: '#6c6c6c', fontSize: 10 }} axisLine={false} tickLine={false} />
          <YAxis type="category" dataKey="mode" width={120} tick={{ fill: '#000000', fontSize: 11 }} axisLine={false} tickLine={false} />
          <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ fill: 'rgba(0,0,0,0.03)' }} formatter={(v: number) => v.toFixed(3)} />
          <Bar dataKey="ndcg" radius={[0, 4, 4, 0]} barSize={22}>
            {DATA.map((d, i) => (
              <Cell key={d.mode} fill={BAR_COLORS[i]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
