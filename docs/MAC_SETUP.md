# RetrievalLab — Complete Mac Setup Guide

> **For:** macOS 13 Ventura or later (Apple Silicon M1/M2/M3 or Intel)  
> **Time:** ~25 minutes (first time, mostly waiting for downloads)  
> **What you'll have at the end:** Running FastAPI server + all Docker services + seed corpora ingested

---

## Table of Contents

1. [Prerequisites — Install Core Tools](#1-prerequisites--install-core-tools)
2. [Get the Project](#2-get-the-project)
3. [Python Virtual Environment](#3-python-virtual-environment)
4. [Install Dependencies](#4-install-dependencies)
5. [Configure Environment Variables](#5-configure-environment-variables)
6. [Start Docker Infrastructure](#6-start-docker-infrastructure)
7. [Run Database Migrations](#7-run-database-migrations)
8. [Start the API Server](#8-start-the-api-server)
9. [Verify Everything Works](#9-verify-everything-works)
10. [Ingest Seed Corpora](#10-ingest-seed-corpora)
11. [Common Errors & Fixes](#11-common-errors--fixes)
12. [Daily Development Workflow](#12-daily-development-workflow)

---

## 1. Prerequisites — Install Core Tools

Open **Terminal** (`Cmd + Space` → type "Terminal" → Enter).

### 1a. Install Homebrew (Mac package manager)

```bash
# Check if you already have it
brew --version

# If not installed, run this:
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

> **Apple Silicon (M1/M2/M3) users:** After install, run the two export commands Homebrew tells you to add to your shell profile.

### 1b. Install Python 3.11

RetrievalLab requires Python **3.11** specifically (not 3.12+, not 3.10).

```bash
# Install pyenv to manage Python versions cleanly
brew install pyenv

# Add pyenv to your shell (pick the one matching your shell)
# --- For zsh (default on modern Mac):
echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.zshrc
echo '[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.zshrc
echo 'eval "$(pyenv init -)"' >> ~/.zshrc
source ~/.zshrc

# Install Python 3.11.9
pyenv install 3.11.9
pyenv global 3.11.9

# Verify
python3 --version
# Expected: Python 3.11.9
```

### 1c. Install Docker Desktop

1. Download from: https://www.docker.com/products/docker-desktop/
2. Install the `.dmg` for your chip (Apple Silicon or Intel)
3. Open Docker Desktop from Applications
4. Wait for the whale icon in your menu bar to stop animating (Docker is ready)

```bash
# Verify Docker is running
docker --version
docker compose version
# Expected: Docker version 27.x.x, Docker Compose version v2.x.x
```

> **Important:** Docker Desktop must be **running** (visible in menu bar) whenever you use `make up`.

### 1d. Install Git (if not present)

```bash
git --version
# If not installed, Mac will prompt you to install Xcode Command Line Tools — accept it.
```

---

## 2. Get the Project

### Option A — Unzip the downloaded file

```bash
# Move to your preferred projects directory
cd ~/Projects   # or wherever you keep your code (create with: mkdir -p ~/Projects)

# Unzip the downloaded file
unzip retrievallab.zip

# Enter the project directory
cd retrievallab

# Confirm you're in the right place
ls
# You should see: pyproject.toml  Makefile  backend/  corpus/  eval/  ...
```

### Option B — Clone from Git (if in a repo)

```bash
cd ~/Projects
git clone https://github.com/your-username/retrievallab.git
cd retrievallab
```

---

## 3. Python Virtual Environment

A virtual environment isolates RetrievalLab's dependencies from your system Python.  
**Never skip this step** — it prevents version conflicts with other projects.

```bash
# Make sure you're in the retrievallab directory
pwd
# Expected: /Users/yourname/Projects/retrievallab

# Create the virtual environment using Python 3.11
python3.11 -m venv .venv

# Activate it
source .venv/bin/activate

# Your terminal prompt should now show (.venv) on the left:
# (.venv) yourname@MacBook retrievallab %

# Confirm Python version inside venv
python --version
# Expected: Python 3.11.9

# Upgrade pip to latest (prevents many install errors)
pip install --upgrade pip setuptools wheel
```

> **Every time you open a new terminal for this project**, run `source .venv/bin/activate` again.  
> The `make` commands handle this automatically.

---

## 4. Install Dependencies

This installs ALL Python packages listed in `pyproject.toml` (runtime + dev extras).

```bash
# Make sure venv is active (you see (.venv) in your prompt)
# Then run:
pip install -e ".[dev]"
```

> ⏳ **This takes 5–10 minutes** on first run. It downloads PyTorch, sentence-transformers, LangChain, etc.
> Subsequent runs are instant (packages are cached).

**After pip install, run two more commands:**

```bash
# Download spaCy English model (required by SemanticChunker + SentenceWindowChunker)
python -m spacy download en_core_web_sm

# Download NLTK data (required by BM25 tokenizer)
python -c "import nltk; nltk.download('punkt'); nltk.download('stopwords'); nltk.download('punkt_tab')"
```

**Verify installation:**

```bash
python -c "import fastapi, sqlalchemy, langchain, faiss, chromadb, ragas; print('✓ All core packages installed')"
```

---

## 5. Configure Environment Variables

```bash
# Copy the example .env file
cp .env.example .env

# Open it in your editor
# Option 1: VS Code
code .env

# Option 2: nano (built-in terminal editor)
nano .env

# Option 3: TextEdit (GUI)
open -e .env
```

**Required changes in `.env`:**

```bash
# ── LLM API Keys (at minimum, set one of these) ────────────────────────────
ANTHROPIC_API_KEY=sk-ant-api03-your-actual-key-here    # get from console.anthropic.com
OPENAI_API_KEY=sk-proj-your-actual-key-here            # get from platform.openai.com

# ── Secret key (for JWT auth) ───────────────────────────────────────────────
SECRET_KEY=change_this_to_any_random_string_at_least_32_chars
```

**Everything else can stay as-is** for local development (the Docker defaults match).

> **Where to get API keys:**  
> - Anthropic: https://console.anthropic.com → API Keys  
> - OpenAI: https://platform.openai.com → API Keys  
> At minimum you need ONE of these for LLM-powered features (PropositionalChunker, Ragas eval).

---

## 6. Start Docker Infrastructure

This starts PostgreSQL, Redis, MinIO, ChromaDB, Elasticsearch, and MLflow.

```bash
# Start all services (runs in background with -d)
docker compose -f infra/docker/docker-compose.yml up -d

# Check all services are healthy (takes ~30 seconds for Elasticsearch)
docker compose -f infra/docker/docker-compose.yml ps
```

Expected output (all services should show "healthy" or "running"):

```
NAME               IMAGE                                    STATUS
rl_chromadb        chromadb/chroma:latest                   Up (healthy)
rl_elasticsearch   elasticsearch:8.15.0                     Up (healthy)
rl_minio           minio/minio:latest                       Up (healthy)
rl_mlflow          ghcr.io/mlflow/mlflow:v2.16.0           Up
rl_postgres        pgvector/pgvector:pg16                   Up (healthy)
rl_redis           redis:7-alpine                           Up (healthy)
```

> ⚠️ **If Elasticsearch is "starting" for more than 2 minutes**, it may need more memory.  
> Open Docker Desktop → Settings → Resources → Memory → increase to at least **4 GB**.

---

## 7. Run Database Migrations

Creates the `corpora` and `chunks` tables in PostgreSQL.

```bash
# Make sure venv is active and Docker is running
alembic upgrade head
```

Expected output:
```
INFO  [alembic.runtime.migration] Context impl PostgreSQLImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> a1b2c3d4e5f6, initial schema
```

> If you see "connection refused", PostgreSQL isn't ready yet. Wait 10 seconds and retry.

---

## 8. Start the API Server

```bash
# Start FastAPI with hot-reload (automatically restarts when you edit files)
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Expected output:
```
INFO:     RetrievalLab startup_begin app=RetrievalLab env=development
INFO:     RetrievalLab startup_complete db_healthy=True
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

---

## 9. Verify Everything Works

Open a **new terminal tab** (`Cmd + T`) while the server is running.

### 9a. Health Check

```bash
curl http://localhost:8000/api/v1/health | python3 -m json.tool
```

Expected:
```json
{
    "status": "healthy",
    "version": "0.1.0",
    "components": [
        {"name": "postgresql", "status": "healthy", "latency_ms": 3.2},
        {"name": "redis",      "status": "healthy", "latency_ms": 1.1},
        {"name": "minio",      "status": "healthy", "latency_ms": 8.4},
        {"name": "chromadb",   "status": "healthy", "latency_ms": 5.7}
    ]
}
```

### 9b. Open the API Docs

In your browser, go to:
- **Swagger UI:** http://localhost:8000/docs  
- **ReDoc:** http://localhost:8000/redoc  

You should see all endpoints (corpus, health) with Try It Out buttons.

### 9c. Open MLflow UI

http://localhost:5000 — experiment tracking dashboard

### 9d. Open MinIO Console

http://localhost:9001 — object storage (login: minioadmin / minioadmin)

---

## 10. Ingest Seed Corpora

Create some sample documents to test the pipeline:

```bash
# Create seed data directories
mkdir -p data/seeds/healthcare data/seeds/finance data/seeds/legal

# Create sample healthcare document
cat > data/seeds/healthcare/pubmed_sample.txt << 'EOF'
Cardiovascular disease remains the leading cause of mortality worldwide.
Hypertension, defined as sustained blood pressure above 130/80 mmHg, affects
approximately 1.28 billion adults globally. Risk factors include obesity, 
sedentary lifestyle, sodium-rich diet, smoking, and genetic predisposition.

Type 2 diabetes mellitus is characterized by insulin resistance and relative 
insulin deficiency. Diagnosis requires fasting glucose >= 126 mg/dL on two 
separate occasions. Treatment includes lifestyle modification, metformin as 
first-line pharmacotherapy, and GLP-1 receptor agonists for cardioprotection.

Chronic kidney disease (CKD) staging is based on GFR and albuminuria. 
Stage 3a: GFR 45-59, Stage 3b: GFR 30-44. RAAS inhibitors are first-line 
in CKD with proteinuria. Nephrology referral recommended for GFR < 30.
EOF

# Create sample finance document  
cat > data/seeds/finance/sec_sample.txt << 'EOF'
Revenue for Q3 2024 increased 12% year-over-year to $4.2 billion, driven by
strong performance in cloud services (+34%) and subscription revenue (+18%).
Operating margin expanded 150 basis points to 24.3% on operating leverage.

Free cash flow generation of $892 million represented 21% FCF margin.
The company repurchased $400 million of common stock and declared a quarterly
dividend of $0.25 per share. Net debt stands at $1.2 billion, representing
0.7x EBITDA, well within our target leverage range of 1-2x.

Risk factors include macroeconomic uncertainty, competitive pricing pressure,
foreign exchange headwinds from a stronger US dollar, and potential regulatory
changes in European markets affecting data localization requirements.
EOF

# Create sample legal document
cat > data/seeds/legal/contract_sample.txt << 'EOF'
SECTION 1: DEFINITIONS
"Agreement" means this Master Services Agreement including all exhibits.
"Services" means the professional services described in each Statement of Work.
"Confidential Information" means any non-public information disclosed by either party.

SECTION 2: SCOPE OF SERVICES  
Provider shall perform the Services substantially as described in the applicable
Statement of Work. Provider may subcontract portions of the Services with prior
written consent of Client, not to be unreasonably withheld.

SECTION 3: INTELLECTUAL PROPERTY
Work Product created by Provider specifically for Client under this Agreement
shall be considered work-for-hire and shall vest in Client upon full payment.
Pre-existing intellectual property of either party remains the property of
that party. Provider grants Client a non-exclusive license to use Provider's
pre-existing IP solely to the extent necessary to use the Work Product.

SECTION 4: LIMITATION OF LIABILITY
IN NO EVENT SHALL EITHER PARTY BE LIABLE FOR INDIRECT, INCIDENTAL, SPECIAL,
EXEMPLARY, OR CONSEQUENTIAL DAMAGES. EACH PARTY'S TOTAL LIABILITY SHALL NOT
EXCEED THE TOTAL FEES PAID IN THE TWELVE MONTHS PRECEDING THE CLAIM.
EOF
```

Now ingest them using the CLI:

```bash
# Activate venv if not active
source .venv/bin/activate

# Install the CLI (already done in pip install -e .)
retrievallab --help   # should show available commands

# Ingest healthcare corpus (semantic chunking — best for clinical text)
retrievallab corpus ingest \
  --source data/seeds/healthcare/ \
  --corpus-id healthcare_sample_v1 \
  --domain healthcare \
  --strategy sentence_window \
  --chunk-size 512

# Ingest finance corpus
retrievallab corpus ingest \
  --source data/seeds/finance/ \
  --corpus-id finance_sample_v1 \
  --domain finance \
  --strategy recursive

# Ingest legal corpus
retrievallab corpus ingest \
  --source data/seeds/legal/ \
  --corpus-id legal_sample_v1 \
  --domain legal \
  --strategy document_structure

# List all corpora
retrievallab corpus list

# Check status of a specific corpus
retrievallab corpus status healthcare_sample_v1
```

### 10b. Verify via API

```bash
# List corpora via REST API
curl http://localhost:8000/api/v1/corpus/ | python3 -m json.tool

# Browse chunks in the healthcare corpus
curl "http://localhost:8000/api/v1/corpus/healthcare_sample_v1/chunks?limit=5" | python3 -m json.tool
```

---

## 11. Common Errors & Fixes

### ❌ `ModuleNotFoundError: No module named 'fastapi'`

**Cause:** Virtual environment not activated.

```bash
source .venv/bin/activate
# Confirm: (.venv) should appear in your terminal prompt
```

### ❌ `Connection refused` (database or Redis)

**Cause:** Docker containers aren't running.

```bash
docker compose -f infra/docker/docker-compose.yml ps    # check status
docker compose -f infra/docker/docker-compose.yml up -d # restart
docker compose -f infra/docker/docker-compose.yml logs postgres  # check logs
```

### ❌ `pgvector extension not found`

**Cause:** Using a standard postgres image instead of pgvector/pgvector:pg16.

```bash
# The docker-compose.yml uses pgvector/pgvector:pg16, but if you have an old container:
docker compose -f infra/docker/docker-compose.yml down -v  # ⚠️ deletes data
docker compose -f infra/docker/docker-compose.yml up -d
alembic upgrade head
```

### ❌ `pip install` fails with build errors for `torch` or `faiss`

**Apple Silicon (M1/M2/M3) specific:**

```bash
# Install torch for Apple Silicon first
pip install torch torchvision torchaudio

# Then install the rest
pip install -e ".[dev]"
```

### ❌ `ERROR: Could not find a version that satisfies the requirement faiss-cpu`

```bash
# Install faiss separately first
pip install faiss-cpu --no-deps
pip install -e ".[dev]"
```

### ❌ Elasticsearch container keeps restarting

**Cause:** Not enough memory.

1. Open Docker Desktop
2. Go to Settings → Resources → Memory
3. Set to **6 GB** minimum (Elasticsearch needs at least 2 GB)
4. Click "Apply & Restart"
5. Re-run `make up`

### ❌ `alembic: command not found`

```bash
# Make sure venv is active
source .venv/bin/activate
# Then retry alembic upgrade head
```

### ❌ `ImportError: libGL.so.1: cannot open shared object file`

```bash
brew install mesa
```

### ❌ Port 8000 already in use

```bash
# Find what's using port 8000
lsof -i :8000

# Kill it
kill -9 <PID>

# Or use a different port:
uvicorn backend.main:app --reload --port 8001
```

---

## 12. Daily Development Workflow

Every day when you sit down to work on RetrievalLab:

```bash
# Step 1: Open terminal, go to project
cd ~/Projects/retrievallab

# Step 2: Activate virtual environment (EVERY TIME you open a new terminal)
source .venv/bin/activate

# Step 3: Make sure Docker is running (open Docker Desktop if not)
docker compose -f infra/docker/docker-compose.yml ps

# Step 4: If containers are stopped, restart them
docker compose -f infra/docker/docker-compose.yml up -d

# Step 5: Start the API server
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### Useful commands during development

```bash
# Run tests (in a new terminal tab)
pytest tests/ -v

# Run only fast unit tests (no DB, no Docker)
pytest tests/unit/ -v -x --no-cov

# Lint your code
ruff check .
ruff format .

# Type check
mypy backend/ corpus/ eval/

# Create a new DB migration after model changes
alembic revision --autogenerate -m "add embedding_metadata column"
alembic upgrade head

# View all Docker service logs
docker compose -f infra/docker/docker-compose.yml logs -f

# View logs for specific service
docker compose -f infra/docker/docker-compose.yml logs -f postgres

# Stop all Docker services (does NOT delete data)
docker compose -f infra/docker/docker-compose.yml down

# Stop and delete ALL data (use carefully)
docker compose -f infra/docker/docker-compose.yml down -v
```

---

## Quick Reference Card

| What | Command |
|------|---------|
| Activate venv | `source .venv/bin/activate` |
| Start Docker | `docker compose -f infra/docker/docker-compose.yml up -d` |
| Start API | `uvicorn backend.main:app --reload --port 8000` |
| Run migrations | `alembic upgrade head` |
| Run tests | `pytest tests/ -v` |
| Ingest corpus | `retrievallab corpus ingest --source <path> --corpus-id <id>` |
| List corpora | `retrievallab corpus list` |
| API docs | http://localhost:8000/docs |
| MLflow UI | http://localhost:5000 |
| MinIO console | http://localhost:9001 |
| Health check | `curl localhost:8000/api/v1/health` |
| Stop Docker | `docker compose -f infra/docker/docker-compose.yml down` |

---

*For Day 2 (EmbedHub + IndexRegistry + RetrieverCore) and Day 3 (EvalEngine + BEIR + Adversarial) walkthrough, see `docs/DAY2_WALKTHROUGH.md` and `docs/DAY3_WALKTHROUGH.md`.*
