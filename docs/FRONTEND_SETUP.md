# RetrievalLab Frontend Setup

## Prerequisites
- Node.js 18+ (`node --version`)
- npm 9+ (`npm --version`)
- Backend API running on port 8000

## Install & Run

```bash
cd frontend
npm install
npm run dev
```

Open: **http://localhost:3000**

## Pages

| Route | Page | Description |
|-------|------|-------------|
| `/` | Dashboard | Metrics overview, corpus list, charts |
| `/corpus` | Corpora | Manage + ingest document collections |
| `/retrieve` | Retrieval Playground | Test sparse/dense/hybrid search |
| `/agent` | AI Agent | 5-node agentic pipeline with synthesis |
| `/eval` | Eval Engine | Compute NDCG/MRR/MAP interactively |
| `/adversarial` | Adversarial | 6-attack robustness documentation |
| `/metrics` | Metrics | System health + Prometheus info |

## Build for Production

```bash
npm run build
# Output in frontend/dist/
# Serve with: npx serve dist
```

## Environment

The frontend proxies `/api/*` to `http://localhost:8000` via Vite proxy config.
To change the API URL, set `VITE_API_URL` in `.env.local`.
