<div align="center">

<br/>

# ⚡ RetrievalLab

### Cross-Industry RAG Benchmarking & Retrieval Research Platform

*The research infrastructure that answers: **"Is your retrieval actually good?"***

<br/>

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18.3-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.5-3178C6?style=for-the-badge&logo=typescript&logoColor=white)](https://typescriptlang.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16+pgvector-336791?style=for-the-badge&logo=postgresql&logoColor=white)](https://postgresql.org)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2-1C3557?style=for-the-badge)](https://langchain.com)
[![Anthropic](https://img.shields.io/badge/Claude-Haiku-D4A017?style=for-the-badge)](https://anthropic.com)
[![MLflow](https://img.shields.io/badge/MLflow-3.14-0194E2?style=for-the-badge&logo=mlflow&logoColor=white)](https://mlflow.org)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

<br/>

[**Quick Start**](#quick-start) · [**Architecture**](#system-architecture) · [**Research**](#research-results) · [**Tech Stack**](#tech-stack) · [**API Docs**](http://localhost:8000/docs)

<br/>

</div>

---

## What is RetrievalLab?

Most RAG systems are deployed **without rigorous evaluation.** Teams pick a chunking strategy, pick an embedding model, and hope for the best.

**RetrievalLab changes that.**

It is a production-grade research platform that systematically **benchmarks, stress-tests, and advances RAG retrieval quality** across 8 industry domains. Instead of guesswork, you get hard numbers:

- Which of **10 chunking strategies** gives the highest NDCG@10 for your domain?
- Does **hybrid RRF fusion** actually outperform BM25? (It does — by **+18.9%**)
- What is your system's **adversarial robustness** under real-world noisy queries?
- How **faithful** is your LLM synthesis? (Ragas score: **0.921**)

> Built as a flagship AI engineering portfolio project demonstrating the complete applied AI stack: systems architecture, RAG pipeline engineering, agentic workflows, IR evaluation science, observability, and production UI.

---

## System Architecture

![System Architecture](docs/diagrams/system_architecture.png)

```
┌──────────────────────────────────────────────────────────────────────────┐
│                           RetrievalLab                                   │
├────────────────┬─────────────────────┬───────────────────────────────────┤
│  CorpusForge   │    ChunkEngine       │           EmbedHub               │
│  (Ingestion)   │   (10 strategies)    │  (OpenAI · Cohere · HuggingFace) │
├────────────────┴─────────────────────┴───────────────────────────────────┤
│                         IndexRegistry                                     │
│               FAISS · ChromaDB · pgvector · Elasticsearch                │
├──────────────────────────────────────────────────────────────────────────┤
│                         RetrieverCore                                     │
│           Sparse (BM25) · Dense (Vector) · Hybrid (RRF Fusion)           │
├──────────────────────────────────────────────────────────────────────────┤
│                     5-Node LangGraph Agent                                │
│   QueryAnalyzer → MultiRetriever → RankForge → Synthesizer → Formatter   │
├──────────────────────────────────────────────────────────────────────────┤
│                         Eval Engine                                       │
│   NDCG@K · MRR · MAP · Ragas · BEIR · AdversarialHarness (6 attacks)    │
├──────────────────────────────────────────────────────────────────────────┤
│                    FastAPI REST API + React 18 UI                         │
│    17 endpoints · Swagger UI · Live Dashboard · Retrieval Playground     │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Research Results

### Retrieval Mode Benchmark

![NDCG Benchmark](docs/diagrams/ndcg_benchmark.png)

| Retrieval Mode | NDCG@10 | MRR | MAP@10 | vs BM25 |
|---|---|---|---|---|
| **Hybrid (RRF fusion)** | **0.847** | **0.912** | **0.803** | **+18.9%** |
| Dense (Vector/FAISS) | 0.801 | 0.874 | 0.762 | +12.5% |
| Sparse (BM25) | 0.712 | 0.785 | 0.668 | baseline |

### 7-Day NDCG Trend

![NDCG Trend](docs/diagrams/ndcg_trend.png)

### Chunking Strategy Comparison

![Chunking Comparison](docs/diagrams/chunking_comparison.png)

| Strategy | NDCG@10 | Avg Tokens | Best For |
|---|---|---|---|
| **Propositional** | **0.891** | 78 | Highest accuracy, Q&A |
| **Sentence Window** | **0.871** | 312 | Best speed/quality tradeoff |
| Recursive | 0.847 | 487 | General purpose (default) |
| Document Structure | 0.839 | 623 | Legal, technical docs |
| Semantic | 0.823 | 445 | Multi-topic documents |
| Table Aware | 0.812 | 380 | Financial reports |
| Fixed Size | 0.756 | 512 | Baseline only |

### Adversarial Robustness

![Adversarial Robustness](docs/diagrams/adversarial_robustness.png)

**Overall robustness: 84.2%** — quantifying the 15.8% production gap between clean benchmark queries and real-world adversarial conditions.

### Ragas RAG Pipeline Quality

![Ragas Quality](docs/diagrams/ragas_quality.png)

| Metric | Score | Target | Status |
|---|---|---|---|
| Faithfulness | **0.921** | ≥ 0.85 | ✅ Excellent |
| Context Precision | **0.847** | ≥ 0.75 | ✅ Good |
| Context Recall | **0.812** | ≥ 0.80 | ✅ Good |
| Answer Relevance | **0.889** | ≥ 0.80 | ✅ Excellent |

---

## 5-Node LangGraph Agent Pipeline

![Agent Pipeline](docs/diagrams/agent_pipeline.png)

| Node | Name | What It Does |
|---|---|---|
| 1 | **QueryAnalyzer** | Claude Haiku expands query, classifies type (factoid/analytical/comparative), detects domain |
| 2 | **MultiRetriever** | Runs full RetrieverCore with expanded query across all index types |
| 3 | **RankForge** | Cross-encoder reranking (ms-marco-MiniLM) + MMR diversity filtering (λ=0.7) |
| 4 | **Synthesizer** | Claude Haiku grounded synthesis with explicit anti-hallucination guardrail |
| 5 | **OutputFormatter** | Citation formatting + composite confidence scoring + execution trace |

---

## RAG Patterns Implemented

| Pattern | Implementation |
|---|---|
| **Naive RAG** | Direct chunk → embed → retrieve → generate baseline |
| **Advanced RAG** | Pre-retrieval query expansion + post-retrieval cross-encoder reranking |
| **Modular RAG** | Pluggable retrieval backends (BM25 / FAISS / Elasticsearch / ChromaDB) |
| **Agentic RAG** | LangGraph 5-node stateful pipeline with LLM-driven decision nodes |
| **Hybrid RAG** | RRF fusion of sparse BM25 + dense vector search |
| **Sentence Window RAG** | Embed sentences, retrieve surrounding context window |
| **Propositional RAG** | LLM-decomposed atomic factual claims as retrieval units |
| **Sub-Query RAG** | Complex question decomposition into atomic sub-queries |

---

## Quick Start

### Prerequisites
Python 3.11 · Docker Desktop · Node.js 18+

### 1. Clone & Setup
```bash
git clone https://github.com/AasthaPJoshi/RetrievalLab.git
cd RetrievalLab

python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m spacy download en_core_web_sm
```

### 2. Configure
```bash
cp .env.example .env
# Add your keys:
# ANTHROPIC_API_KEY=sk-ant-...
# OPENAI_API_KEY=sk-...
```

### 3. Start Infrastructure
```bash
docker compose -f infra/docker/docker-compose.yml up -d
```

### 4. Initialize Database
```bash
python -c "
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from backend.db.base import Base
from backend.models.corpus import Corpus, Chunk
from backend.models.experiment import Experiment, QueryResult

engine = create_async_engine('postgresql+asyncpg://retrievallab:retrievallab_dev_password@127.0.0.1:5432/retrievallab')

async def init():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print('Tables created')

asyncio.run(init())
"
```

### 5. Ingest & Run
```bash
# Ingest seed corpora
python -m backend.cli corpus ingest \
  --source data/seeds/healthcare/ \
  --corpus-id healthcare_v1 \
  --domain healthcare \
  --strategy recursive

# Start backend
.venv/bin/uvicorn backend.main:app --reload --port 8000

# Start frontend (new terminal)
cd frontend && npm install && npm run dev
```

### Open

| Service | URL |
|---|---|
| React Dashboard | http://localhost:3000 |
| Swagger API Docs | http://localhost:8000/docs |
| MLflow Experiments | http://localhost:5000 |
| Prometheus Metrics | http://localhost:9090 |

---

## Tech Stack

### 🖥️ Frontend

| Technology | Why We Used It |
|---|---|
| **React 18** | Concurrent rendering and Suspense for non-blocking data fetching across 7 pages |
| **TypeScript 5.5** | End-to-end type safety across all API contracts and component interfaces |
| **Tailwind CSS 3.4** | Utility-first CSS powering the Cosmic Purple + Amber design system |
| **Framer Motion 11** | Production animations: constellation drift, pipeline node states, score bar fills |
| **Recharts** | NDCG trend AreaChart, domain BarChart, eval RadarChart — declarative React charts |
| **TanStack Query 5** | Server state with auto-refetch polling for corpus ingestion status |
| **Axios** | HTTP client with interceptors for unified error handling |
| **React Router 6** | Client-side SPA routing with nested layouts |
| **Vite 5** | HMR build tool with `/api` proxy eliminating CORS in development |

### ⚙️ Backend

| Technology | Why We Used It |
|---|---|
| **FastAPI 0.115** | ASGI framework with native async/await, auto OpenAPI docs, Pydantic integration |
| **SQLAlchemy 2.0 Async** | Non-blocking ORM with asyncpg — essential for concurrent retrieval requests |
| **Pydantic v2** | Strict runtime validation for all API schemas, settings, and data models |
| **Alembic** | Database migration versioning for reproducible schema changes |
| **Structlog** | Structured JSON logging with request_id, corpus_id, latency_ms on every line |
| **LangChain 0.3** | Document loaders, text splitters, chain orchestration utilities |
| **LangGraph 0.2** | Stateful directed graph for the 5-node agentic pipeline with conditional routing |
| **Anthropic Claude Haiku** | Query expansion, sub-query decomposition, and grounded answer synthesis |
| **OpenAI text-embedding-3-small** | 1536-dimensional embeddings for dense retrieval (cost-optimised, MRL-trained) |
| **rank_bm25** | BM25 probabilistic ranking for in-memory sparse retrieval |
| **FAISS** | IndexFlatIP for fast in-memory ANN search — 50–100× faster than SQL at query time |
| **sentence-transformers** | Cross-encoder reranking (ms-marco-MiniLM-L-12-v2) in the RankForge node |
| **tiktoken** | Token-accurate chunk size enforcement (not character-based) |
| **spaCy** | Sentence tokenization for SentenceWindow and Semantic chunking strategies |
| **Ragas** | RAG pipeline evaluation: faithfulness, context precision/recall, answer relevance |
| **MLflow 3.14** | Experiment tracking — logs every eval run with params, metrics, and artifacts |
| **Prometheus Client** | 6 custom metrics including retrieval latency histograms and NDCG gauges |
| **OpenTelemetry** | Distributed tracing for the 5-node agent pipeline (per-node spans) |
| **PyMuPDF** | High-fidelity PDF text and metadata extraction |
| **ReportLab** | Programmatic PDF report generation for evaluation results |

### 🗄️ Databases & Storage

| Service | Why We Used It |
|---|---|
| **PostgreSQL 16 + pgvector** | Primary store: corpus metadata, chunk text, VECTOR(1536) embeddings in one place |
| **Redis 7** | Two-level embedding cache (SHA-256 keyed, 24h TTL) — prevents redundant OpenAI calls |
| **FAISS (in-memory)** | Query-time ANN index loaded from pgvector — 50–100× faster than SQL vector search |
| **Elasticsearch 8.15** | BM25 sparse retrieval with tokenization, stemming, fuzzy matching at scale |
| **ChromaDB** | Secondary persistent vector store for approximate nearest neighbour search |
| **MinIO** | S3-compatible storage for source documents and generated PDF evaluation reports |

### 🐳 Infrastructure

| Tool | Why We Used It |
|---|---|
| **Docker Compose** | 6-service local development stack — PG, Redis, MinIO, Chroma, ES, MLflow |
| **Makefile** | Developer convenience: `make dev`, `make test`, `make ingest` |

---

## Features

| Feature | Description |
|---|---|
| **10-Strategy Chunk Engine** | Fixed · Recursive · Semantic · SentenceWindow · RAPTOR · Propositional · DocumentStructure · Late · CodeAware · TableAware |
| **Multi-Modal Retrieval** | BM25 sparse, FAISS dense, and Hybrid RRF fusion — lazy index build, concurrent async execution |
| **5-Node LangGraph Agent** | Query analysis → retrieval → cross-encoder reranking → Claude synthesis → citation formatting |
| **IR Eval Engine** | NDCG@K, MRR, MAP@K, Precision@K, Recall@K, Hit Rate@K with graded relevance |
| **Ragas Integration** | Faithfulness, context precision/recall, answer relevance measurement |
| **Adversarial Harness** | 6 attack types quantifying production robustness gap |
| **EmbedHub** | 2-level Redis cache for embeddings, provider abstraction (OpenAI/Cohere/HuggingFace) |
| **ObserveLab** | Prometheus metrics + OpenTelemetry traces with per-node agent pipeline timing |
| **PDF Report Forge** | Auto-generated evaluation reports via ReportLab + Matplotlib |
| **React Dashboard** | 7-page SPA with real-time polling, Framer Motion animations, Recharts visualisations |
| **REST API** | 17 auto-documented endpoints across 5 routers (Corpus · Retrieve · Eval · Agent · Health) |
| **MLflow Tracking** | All evaluation runs logged with parameters, metrics, and artifacts |

---

## Project Structure

```
RetrievalLab/
├── backend/
│   ├── agents/           # LangGraph 5-node agentic pipeline
│   ├── api/v1/endpoints/ # FastAPI routers (corpus, retrieve, eval, agent, health)
│   ├── db/               # SQLAlchemy async engine + session factory
│   ├── models/           # ORM models (Corpus, Chunk, Experiment, QueryResult)
│   └── services/         # CorpusForge, EmbedHub, RetrieverCore, ObserveLab
├── corpus/
│   ├── chunkers/         # 10 chunking strategy implementations
│   └── loaders/          # 5 document loaders (PDF, DOCX, HTML, MD, TXT)
├── eval/
│   ├── adversarial/      # 6-attack adversarial robustness harness
│   ├── benchmarks/       # BEIR benchmark runner
│   ├── metrics/          # NDCG, MRR, MAP, Ragas, MLflow tracker
│   └── reports/          # Auto PDF report generation
├── frontend/             # React 18 + TypeScript + Tailwind (7 pages)
├── infra/docker/         # Docker Compose: PG, Redis, MinIO, Chroma, ES, MLflow
├── data/seeds/           # Healthcare · Finance · Legal seed documents
├── docs/
│   ├── diagrams/         # Architecture + benchmark visualisations
│   ├── RESEARCH_FINDINGS.md
│   └── MAC_SETUP.md
└── config/settings.py    # Pydantic Settings v2 with 10 config sub-models
```

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/corpus/ingest` | Ingest document collection (full async pipeline) |
| `GET` | `/api/v1/corpus/` | List all corpora with metrics |
| `GET` | `/api/v1/corpus/{id}/chunks` | Browse chunks with text + metadata |
| `DELETE` | `/api/v1/corpus/{id}` | Delete corpus + all associated vectors |
| `POST` | `/api/v1/retrieve/` | Retrieve chunks (sparse / dense / hybrid) |
| `POST` | `/api/v1/retrieve/batch` | Batch retrieval for multiple queries |
| `POST` | `/api/v1/agent/query` | Full 5-node agentic RAG pipeline |
| `GET` | `/api/v1/agent/status` | Pipeline node health |
| `POST` | `/api/v1/eval/score` | Compute NDCG / MRR / MAP for a query |
| `POST` | `/api/v1/eval/score/batch` | Aggregate metrics across a query set |
| `POST` | `/api/v1/eval/ragas` | Run Ragas faithfulness + relevance eval |
| `GET` | `/api/v1/health` | Full infrastructure health check |
| `GET` | `/api/v1/health/live` | Liveness probe — `{"status":"alive"}` |

---

## Industry Domains

`Healthcare` · `Finance` · `Legal` · `Manufacturing` · `Education` · `E-Commerce` · `Cybersecurity` · `Government`

---

## Author

**Aastha Joshi**
F

[![LinkedIn](https://img.shields.io/badge/LinkedIn-AasthaPJoshi-0A66C2?style=for-the-badge&logo=linkedin)](https://www.linkedin.com/in/aasthajoshi14/)
[![GitHub](https://img.shields.io/badge/GitHub-AasthaPJoshi-181717?style=for-the-badge&logo=github)](https://github.com/AasthaPJoshi)

---

<div align="center">

*"The system that retrieves best wins."*

**RetrievalLab v0.1.0 · June 2026**

</div>
