# =============================================================================
# RetrievalLab — Makefile
# =============================================================================
# PURPOSE : Wraps every common developer action (setup, run, test, lint, etc.)
#           into short, memorable make targets. Eliminates "how do I run this?"
#           questions for every new contributor.
#
# PREREQUISITES : make, python 3.11+, docker, docker-compose
#
# USAGE:
#   make setup      → one-time project setup (venv + deps + pre-commit)
#   make up         → start all Docker services
#   make dev        → start FastAPI dev server (hot-reload)
#   make test       → run all pytest tests with coverage
#   make lint       → run ruff + mypy
#   make migrate    → run Alembic DB migrations
#   make ingest     → ingest seed corpora (Day 1 demo)
#   make clean      → remove caches, .pyc files, coverage artifacts
# =============================================================================

.PHONY: help setup venv deps pre-commit up down dev migrate \
        test lint format type-check ingest clean docs

# ─── Colors for terminal output ─────────────────────────────────────────────
GREEN  := \033[0;32m
YELLOW := \033[1;33m
RESET  := \033[0m

PYTHON  := python3.11
VENV    := .venv
PIP     := $(VENV)/bin/pip
PYTEST  := $(VENV)/bin/pytest
RUFF    := $(VENV)/bin/ruff
MYPY    := $(VENV)/bin/mypy
UVICORN := $(VENV)/bin/uvicorn
ALEMBIC := $(VENV)/bin/alembic
RL      := $(VENV)/bin/retrievallab   # CLI entry point

# ─── Default target: show help ───────────────────────────────────────────────
help:
	@echo ""
	@echo "$(GREEN)RetrievalLab — Developer Commands$(RESET)"
	@echo "──────────────────────────────────────────────────────────"
	@echo "  $(YELLOW)make setup$(RESET)        One-time: create venv, install deps, pre-commit"
	@echo "  $(YELLOW)make up$(RESET)           Start Docker services (Postgres, Redis, MinIO, Chroma)"
	@echo "  $(YELLOW)make down$(RESET)         Stop Docker services"
	@echo "  $(YELLOW)make dev$(RESET)          Start FastAPI server with hot-reload on :8000"
	@echo "  $(YELLOW)make migrate$(RESET)      Run Alembic schema migrations"
	@echo "  $(YELLOW)make ingest$(RESET)       Ingest all 3 seed corpora (healthcare, finance, legal)"
	@echo "  $(YELLOW)make test$(RESET)         Run pytest suite with coverage report"
	@echo "  $(YELLOW)make lint$(RESET)         Run ruff linter + mypy type checker"
	@echo "  $(YELLOW)make format$(RESET)       Auto-format with ruff"
	@echo "  $(YELLOW)make clean$(RESET)        Remove caches and build artifacts"
	@echo ""

# ─── ONE-TIME SETUP ──────────────────────────────────────────────────────────
setup: venv deps pre-commit
	@echo "$(GREEN)✓ Setup complete! Run 'make up' then 'make dev' to start.$(RESET)"

venv:
	@echo "$(YELLOW)Creating virtual environment...$(RESET)"
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip setuptools wheel

deps:
	@echo "$(YELLOW)Installing dependencies...$(RESET)"
	$(PIP) install -e ".[dev]"
	# Download spaCy English model (required by ChunkEngine)
	$(VENV)/bin/python -m spacy download en_core_web_sm
	# Download NLTK data (required by BM25 tokenizer)
	$(VENV)/bin/python -c "import nltk; nltk.download('punkt'); nltk.download('stopwords'); nltk.download('punkt_tab')"

pre-commit:
	@echo "$(YELLOW)Installing pre-commit hooks...$(RESET)"
	$(VENV)/bin/pre-commit install

# ─── DOCKER SERVICES ─────────────────────────────────────────────────────────
up:
	@echo "$(YELLOW)Starting Docker services...$(RESET)"
	docker compose -f infra/docker/docker-compose.yml up -d
	@echo "$(GREEN)✓ Services running. Check status: docker compose ps$(RESET)"

down:
	docker compose -f infra/docker/docker-compose.yml down

logs:
	docker compose -f infra/docker/docker-compose.yml logs -f

# ─── DEV SERVER ──────────────────────────────────────────────────────────────
dev:
	@echo "$(GREEN)Starting RetrievalLab API on http://localhost:8000$(RESET)"
	@echo "$(GREEN)Docs at: http://localhost:8000/docs$(RESET)"
	$(UVICORN) backend.main:app --reload --host 0.0.0.0 --port 8000

# ─── DATABASE ────────────────────────────────────────────────────────────────
migrate:
	@echo "$(YELLOW)Running Alembic migrations...$(RESET)"
	$(ALEMBIC) upgrade head

migrate-new:
	@echo "$(YELLOW)Creating new migration: $(MSG)$(RESET)"
	$(ALEMBIC) revision --autogenerate -m "$(MSG)"

migrate-down:
	$(ALEMBIC) downgrade -1

# ─── CORPUS INGESTION (Day 1 Demo) ───────────────────────────────────────────
ingest:
	@echo "$(YELLOW)Ingesting seed corpora...$(RESET)"
	$(RL) corpus ingest \
	  --source data/seeds/healthcare \
	  --corpus-id healthcare_pubmed_v1 \
	  --domain healthcare \
	  --strategy semantic
	$(RL) corpus ingest \
	  --source data/seeds/finance \
	  --corpus-id finance_sec_v1 \
	  --domain finance \
	  --strategy recursive
	$(RL) corpus ingest \
	  --source data/seeds/legal \
	  --corpus-id legal_contracts_v1 \
	  --domain legal \
	  --strategy document_structure

# ─── TESTING ─────────────────────────────────────────────────────────────────
test:
	@echo "$(YELLOW)Running test suite...$(RESET)"
	$(PYTEST) tests/ -v

test-unit:
	$(PYTEST) tests/unit/ -v

test-integration:
	$(PYTEST) tests/integration/ -v -m "not slow"

test-fast:
	$(PYTEST) tests/unit/ -v -x --no-cov  # -x = stop on first failure

# ─── CODE QUALITY ────────────────────────────────────────────────────────────
lint: ruff-check type-check

ruff-check:
	@echo "$(YELLOW)Running Ruff linter...$(RESET)"
	$(RUFF) check .

format:
	@echo "$(YELLOW)Auto-formatting with Ruff...$(RESET)"
	$(RUFF) format .
	$(RUFF) check --fix .

type-check:
	@echo "$(YELLOW)Running mypy type checker...$(RESET)"
	$(MYPY) backend/ corpus/ eval/ --ignore-missing-imports

# ─── CLEAN ───────────────────────────────────────────────────────────────────
clean:
	@echo "$(YELLOW)Cleaning build artifacts...$(RESET)"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null; true
	find . -type f -name "*.pyc"       -delete 2>/dev/null; true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null; true
	find . -type d -name ".mypy_cache"   -exec rm -rf {} + 2>/dev/null; true
	find . -type d -name ".ruff_cache"   -exec rm -rf {} + 2>/dev/null; true
	find . -type d -name "*.egg-info"    -exec rm -rf {} + 2>/dev/null; true
	rm -f .coverage coverage.xml
	@echo "$(GREEN)✓ Clean complete$(RESET)"
