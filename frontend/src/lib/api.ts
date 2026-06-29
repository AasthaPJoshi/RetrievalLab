// =============================================================================
// RetrievalLab — frontend/src/lib/api.ts
// =============================================================================
// Typed API client for all RetrievalLab backend endpoints.
// Uses axios with interceptors for auth, error handling, and logging.
// =============================================================================

import axios, { type AxiosInstance, type AxiosError } from 'axios';

const BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

// ── Axios instance ────────────────────────────────────────────────────────────
const http: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 60_000,
});

// Response interceptor — normalize errors
http.interceptors.response.use(
  (res) => res,
  (err: AxiosError<{ detail: string }>) => {
    const message = err.response?.data?.detail || err.message || 'Unknown error';
    return Promise.reject(new Error(message));
  }
);

// ── Types ─────────────────────────────────────────────────────────────────────

export interface Corpus {
  corpus_id:        string;
  name:             string;
  domain:           string;
  version:          string;
  status:           'pending' | 'ingesting' | 'chunking' | 'embedding' | 'ready' | 'failed';
  doc_count:        number;
  chunk_count:      number;
  total_tokens:     number;
  avg_chunk_tokens: number | null;
  chunk_strategy:   string;
  embedding_model:  string | null;
  fingerprint:      string | null;
  created_at:       string;
  updated_at:       string;
}

export interface Chunk {
  chunk_id:      string;
  text:          string;
  token_count:   number;
  chunk_index:   number;
  source_doc_id: string | null;
  strategy:      string;
}

export interface IngestRequest {
  corpus_id:       string;
  source:          string;
  name?:           string;
  domain?:         string;
  strategy?:       string;
  chunk_size?:     number;
  chunk_overlap?:  number;
  embedding_model?: string;
  force_reingest?: boolean;
}

export interface IngestResponse {
  corpus_id: string;
  status:    string;
  message:   string;
}

export interface RetrieveRequest {
  query:     string;
  corpus_id: string;
  mode?:     'sparse' | 'dense' | 'hybrid';
  top_k?:    number;
}

export interface RetrieveResultItem {
  chunk_id:       string;
  text:           string;
  score:          number;
  rank:           number;
  source_doc:     string;
  retrieval_mode: string;
  latency_ms:     number;
  metadata:       Record<string, unknown>;
}

export interface RetrieveResponse {
  query:         string;
  corpus_id:     string;
  mode:          string;
  total_results: number;
  latency_ms:    number;
  results:       RetrieveResultItem[];
}

export interface AgentRequest {
  query_text:  string;
  corpus_id:   string;
  mode?:       string;
  top_k?:      number;
  rerank?:     boolean;
  synthesize?: boolean;
}

export interface AgentResponse {
  query_id:         string;
  query_text:       string;
  answer:           string;
  sources:          RetrieveResultItem[];
  confidence:       number;
  citations:        string[];
  query_type:       string;
  detected_domain:  string;
  expanded_query:   string;
  total_latency_ms: number;
  trace:            string[];
  error:            string | null;
}

export interface EvalScoreRequest {
  retrieved_ids: string[];
  relevant_ids:  Record<string, number>;
  query?:        string;
}

export interface EvalScoreResponse {
  query:   string;
  metrics: Record<string, number>;
}

export interface HealthComponent {
  name:       string;
  status:     'healthy' | 'degraded' | 'unhealthy';
  latency_ms: number | null;
  detail:     string | null;
}

export interface HealthResponse {
  status:     string;
  version:    string;
  components: HealthComponent[];
  uptime_s:   number;
}

// ── API Functions ─────────────────────────────────────────────────────────────

// Corpus
export const api = {
  corpus: {
    list:    (params?: { domain?: string; status?: string; limit?: number }) =>
      http.get<Corpus[]>('/corpus/', { params }).then(r => r.data),

    get:     (corpusId: string) =>
      http.get<Corpus>(`/corpus/${corpusId}`).then(r => r.data),

    ingest:  (body: IngestRequest) =>
      http.post<IngestResponse>('/corpus/ingest', body).then(r => r.data),

    delete:  (corpusId: string) =>
      http.delete(`/corpus/${corpusId}`).then(r => r.data),

    chunks:  (corpusId: string, params?: { limit?: number; offset?: number }) =>
      http.get<Chunk[]>(`/corpus/${corpusId}/chunks`, { params }).then(r => r.data),
  },

  retrieve: {
    query:  (body: RetrieveRequest) =>
      http.post<RetrieveResponse>('/retrieve/', body).then(r => r.data),

    batch:  (queries: string[], corpus_id: string, mode = 'hybrid') =>
      http.post<RetrieveResponse[]>('/retrieve/batch', { queries, corpus_id, mode }).then(r => r.data),

    modes:  () =>
      http.get('/retrieve/modes').then(r => r.data),
  },

  agent: {
    query:  (body: AgentRequest) =>
      http.post<AgentResponse>('/agent/query', body).then(r => r.data),

    status: () =>
      http.get('/agent/status').then(r => r.data),
  },

  eval: {
    score:  (body: EvalScoreRequest) =>
      http.post<EvalScoreResponse>('/eval/score', body).then(r => r.data),

    metrics: () =>
      http.get('/eval/metrics').then(r => r.data),
  },

  health: {
    full:  () => http.get<HealthResponse>('/health').then(r => r.data),
    live:  () => http.get('/health/live').then(r => r.data),
    ready: () => http.get('/health/ready').then(r => r.data),
  },
};

export default api;
