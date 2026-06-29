import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatNumber(n: number, decimals = 4): string {
  return n.toFixed(decimals);
}

export function formatMs(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

export function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000)     return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

export function scoreColor(score: number): string {
  if (score >= 0.85) return 'text-amber-400';
  if (score >= 0.70) return 'text-purple-300';
  if (score >= 0.55) return 'text-fuchsia-400';
  return 'text-red-400';
}

export function scoreBarColor(score: number): string {
  if (score >= 0.85) return 'bg-amber-400';
  if (score >= 0.70) return 'bg-purple-400';
  if (score >= 0.55) return 'bg-fuchsia-400';
  return 'bg-red-400';
}

export function statusColor(status: string): string {
  const map: Record<string, string> = {
    ready:     'text-accent-green',
    ingesting: 'text-accent-amber',
    chunking:  'text-cyan-400',
    pending:   'text-slate-400',
    failed:    'text-accent-red',
    embedding: 'text-accent-purple',
  };
  return map[status] || 'text-slate-400';
}

export function statusBadge(status: string): string {
  const map: Record<string, string> = {
    ready:     'badge-green',
    ingesting: 'badge-amber',
    chunking:  'badge-purple',
    pending:   'badge',
    failed:    'badge-red',
    embedding: 'badge-fuchsia',
  };
  return map[status] || 'badge';
}

export function domainIcon(domain: string): string {
  const map: Record<string, string> = {
    healthcare:    '🏥',
    finance:       '📈',
    legal:         '⚖️',
    manufacturing: '🏭',
    education:     '🎓',
    ecommerce:     '🛒',
    cybersecurity: '🔒',
    government:    '🏛️',
    general:       '📄',
  };
  return map[domain] || '📄';
}

export function truncate(str: string, len = 120): string {
  if (str.length <= len) return str;
  return str.slice(0, len) + '…';
}

export function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins  = Math.floor(diff / 60_000);
  const hours = Math.floor(diff / 3_600_000);
  const days  = Math.floor(diff / 86_400_000);
  if (mins < 1)    return 'just now';
  if (mins < 60)   return `${mins}m ago`;
  if (hours < 24)  return `${hours}h ago`;
  return `${days}d ago`;
}

export function confidenceLabel(score: number): { label: string; color: string } {
  if (score >= 0.85) return { label: 'High',   color: 'text-accent-green' };
  if (score >= 0.60) return { label: 'Medium', color: 'text-accent-amber' };
  return               { label: 'Low',    color: 'text-accent-red' };
}
