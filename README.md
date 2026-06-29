# RetrievalLab 🔬

**Cross-industry retrieval research platform — benchmark, stress-test, and advance RAG systems**

[![Python](https://img.shields.io/badge/Python-3.11-3776AB)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18.3-61DAFB)](https://react.dev)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16+pgvector-336791)](https://postgresql.org)

## Quick Start

```bash
# Backend
source .venv/bin/activate
docker compose -f infra/docker/docker-compose.yml up -d
.venv/bin/uvicorn backend.main:app --reload --port 8000

# Frontend (new terminal)
cd frontend && npm install && npm run dev
```

**Open:** http://localhost:3000 (UI) · http://localhost:8000/docs (API)

## What's Inside

- **10-strategy chunking engine** (Recursive, Semantic, SentenceWindow, Propositional, ...)
- **3 retrieval modes** — Sparse (BM25), Dense (Vector), Hybrid (RRF fusion)
- **5-node LangGraph agent** — analyze → retrieve → rerank → synthesize → format
- **Full eval stack** — NDCG@K, MRR, MAP, Ragas, BEIR, adversarial (6 attacks)
- **Banking-grade React UI** — dark navy theme, real-time dashboards

## Research Results

| Config | NDCG@10 | vs BM25 Baseline |
|--------|---------|-----------------|
| Hybrid (RRF) | **0.847** | +18.9% |
| Dense (Vector) | 0.801 | +12.5% |
| Sparse (BM25) | 0.712 | baseline |

See [docs/RESEARCH_FINDINGS.md](docs/RESEARCH_FINDINGS.md) for full results.

## Stack

Python 3.11 · FastAPI · PostgreSQL+pgvector · Redis · LangGraph · Anthropic · OpenAI  
React 18 · TypeScript · Tailwind CSS · Framer Motion · FAISS · ChromaDB · Elasticsearch  
Ragas · BEIR · MLflow · Prometheus · OpenTelemetry
