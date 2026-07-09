# =============================================================================
# RetrievalLab — backend/api/v1/endpoints/retrieve.py
# =============================================================================
# PURPOSE : FastAPI router for retrieval search endpoints.
#           Exposes the RetrieverCore service over HTTP so the React dashboard,
#           Jupyter notebooks, and external tools can submit queries.
#
# ENDPOINTS:
#   POST /api/v1/retrieve           → single query (sparse | dense | hybrid)
#   POST /api/v1/retrieve/batch     → batch of queries in one call
#   GET  /api/v1/retrieve/modes     → list available retrieval modes
#
# REQUEST FLOW:
#   HTTP request → schema validation → RetrieverCore.retrieve()
#   → IndexRegistry.search() + optional BM25
#   → RRF fusion (hybrid mode)
#   → JSON response
#
# INPUT  : JSON body with query string, corpus_id, mode, top_k
# OUTPUT : JSON array of RetrievalResult objects with score, rank, text, metadata
#
# AFTER THIS FILE:
#   Results can be passed to POST /api/v1/eval/score to compute NDCG/MRR
# =============================================================================

from __future__ import annotations

import time
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.base import get_db
from backend.services.embed_hub import EmbedHub
from backend.services.index_registry import IndexRegistry
from backend.services.retriever_core import RetrievalRequest, RetrieverCore

logger = structlog.get_logger(__name__)
router = APIRouter()

# Module-level singletons (shared across requests — expensive to reinitialize)
_embed_hub: EmbedHub | None = None
_index_registry: IndexRegistry | None = None
_retriever_core: RetrieverCore | None = None


def _get_retriever() -> RetrieverCore:
    """Lazy-initialize the retrieval stack once per process."""
    global _embed_hub, _index_registry, _retriever_core

    if _retriever_core is None:
        from config.settings import get_settings

        s = get_settings()
        _embed_hub = EmbedHub(model_name=s.llm.default_embed_model)
        _index_registry = IndexRegistry()
        _retriever_core = RetrieverCore(
            index_registry=_index_registry,
            embed_hub=_embed_hub,
            default_mode=s.retrieval.retriever,
        )

    return _retriever_core


# ─── Schemas ──────────────────────────────────────────────────────────────────


class RetrieveRequest(BaseModel):
    """Request body for POST /retrieve"""

    query: str = Field(
        ...,
        min_length=1,
        max_length=2048,
        description="Natural language query string",
        examples=["What are the symptoms of type 2 diabetes?"],
    )
    corpus_id: str = Field(
        ...,
        description="Corpus to search (must be in READY status)",
        examples=["healthcare_pubmed_v1"],
    )
    mode: str = Field(
        default="hybrid",
        description="Retrieval mode: sparse (BM25) | dense (vector) | hybrid (RRF)",
    )
    top_k: int = Field(default=10, ge=1, le=100, description="Number of results")
    rrf_k: int = Field(default=60, ge=1, le=200, description="RRF damping constant")


class RetrieveResultItem(BaseModel):
    """Single item in a retrieval response."""

    chunk_id: str
    text: str
    score: float
    rank: int
    source_doc: str
    retrieval_mode: str
    sparse_rank: int | None
    dense_rank: int | None
    latency_ms: float
    metadata: dict[str, Any]


class RetrieveResponse(BaseModel):
    """Full response from POST /retrieve"""

    query: str
    corpus_id: str
    mode: str
    total_results: int
    latency_ms: float
    results: list[RetrieveResultItem]


class BatchRetrieveRequest(BaseModel):
    """Request body for POST /retrieve/batch"""

    queries: list[str] = Field(..., min_length=1, max_length=50)
    corpus_id: str
    mode: str = "hybrid"
    top_k: int = Field(default=10, ge=1, le=100)


# ─── Endpoints ────────────────────────────────────────────────────────────────


@router.post(
    "/",
    response_model=RetrieveResponse,
    summary="Retrieve documents for a query",
    description=(
        "Submit a natural language query and retrieve the most relevant chunks "
        "from the specified corpus. Supports sparse (BM25), dense (vector), "
        "and hybrid (RRF fusion) retrieval modes."
    ),
)
async def retrieve(
    body: RetrieveRequest,
    db: AsyncSession = Depends(get_db),
) -> RetrieveResponse:
    """
    Retrieve top-K relevant chunks for a query.

    The index must be built before this endpoint works.
    Use POST /corpus/ingest first, then the index is built automatically
    in the background after embedding completes.
    """
    t0 = time.perf_counter()

    logger.info(
        "retrieve_request",
        query=body.query[:80],
        corpus_id=body.corpus_id,
        mode=body.mode,
        top_k=body.top_k,
    )

    retriever = _get_retriever()

    # Ensure the corpus index is built
    await _ensure_index_built(body.corpus_id, body.mode, retriever, db)

    request = RetrievalRequest(
        query=body.query,
        corpus_id=body.corpus_id,
        mode=body.mode,
        top_k=body.top_k,
        rrf_k=body.rrf_k,
    )

    try:
        results = await retriever.retrieve(request)
    except KeyError as e:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No index found for corpus '{body.corpus_id}'. "
                "Ensure the corpus is ingested and embedding is complete. "
                f"Original error: {e}"
            ),
        )

    latency_ms = round((time.perf_counter() - t0) * 1000, 2)

    return RetrieveResponse(
        query=body.query,
        corpus_id=body.corpus_id,
        mode=body.mode,
        total_results=len(results),
        latency_ms=latency_ms,
        results=[
            RetrieveResultItem(
                chunk_id=r.chunk_id,
                text=r.text,
                score=r.score,
                rank=r.rank,
                source_doc=r.source_doc,
                retrieval_mode=r.retrieval_mode,
                sparse_rank=r.sparse_rank,
                dense_rank=r.dense_rank,
                latency_ms=r.latency_ms,
                metadata=r.metadata,
            )
            for r in results
        ],
    )


@router.post(
    "/batch",
    response_model=list[RetrieveResponse],
    summary="Batch retrieval for multiple queries",
    description=(
        "Submit up to 50 queries at once. Results are returned in the same order "
        "as the input queries. Useful for evaluation runs and benchmark pipelines."
    ),
)
async def batch_retrieve(
    body: BatchRetrieveRequest,
    db: AsyncSession = Depends(get_db),
) -> list[RetrieveResponse]:
    """Retrieve documents for a batch of queries against the same corpus."""
    import asyncio

    retriever = _get_retriever()
    await _ensure_index_built(body.corpus_id, body.mode, retriever, db)

    async def _single(query: str) -> RetrieveResponse:
        t0 = time.perf_counter()
        request = RetrievalRequest(
            query=query,
            corpus_id=body.corpus_id,
            mode=body.mode,
            top_k=body.top_k,
        )
        results = await retriever.retrieve(request)
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        return RetrieveResponse(
            query=query,
            corpus_id=body.corpus_id,
            mode=body.mode,
            total_results=len(results),
            latency_ms=latency_ms,
            results=[
                RetrieveResultItem(
                    chunk_id=r.chunk_id,
                    text=r.text,
                    score=r.score,
                    rank=r.rank,
                    source_doc=r.source_doc,
                    retrieval_mode=r.retrieval_mode,
                    sparse_rank=r.sparse_rank,
                    dense_rank=r.dense_rank,
                    latency_ms=r.latency_ms,
                    metadata=r.metadata,
                )
                for r in results
            ],
        )

    # Run all queries concurrently
    responses = await asyncio.gather(*[_single(q) for q in body.queries])
    return list(responses)


@router.get(
    "/modes",
    summary="List available retrieval modes",
)
async def list_modes() -> dict[str, Any]:
    """Return metadata about available retrieval modes."""
    return {
        "modes": [
            {
                "name": "sparse",
                "description": "BM25 keyword matching via Elasticsearch",
                "best_for": "Exact term matches, legal/regulatory queries",
                "speed": "fastest",
            },
            {
                "name": "dense",
                "description": "Vector similarity via FAISS (cosine)",
                "best_for": "Semantic queries, paraphrase retrieval",
                "speed": "fast",
            },
            {
                "name": "hybrid",
                "description": "Reciprocal Rank Fusion of sparse + dense",
                "best_for": "General purpose; best average performance",
                "speed": "moderate (2 parallel searches + fusion)",
            },
        ]
    }


# ─── Internal Helper ──────────────────────────────────────────────────────────


async def _ensure_index_built(
    corpus_id: str,
    mode: str,
    retriever: RetrieverCore,
    db: AsyncSession,
) -> None:
    """
    Build the required index if not already in memory.

    For dense/hybrid: builds FAISS index from PostgreSQL embeddings.
    For sparse/hybrid: builds BM25 index from chunk texts.

    This is called lazily on first search request so the server starts
    fast even with large corpora.
    """
    from config.settings import get_settings

    s = get_settings()

    # Dense index
    if mode in ("dense", "hybrid"):
        existing = retriever.index_registry.get(corpus_id, "faiss")
        if existing is None or not existing.is_built:
            try:
                await retriever.index_registry.build_from_db(
                    corpus_id=corpus_id,
                    backend="faiss",
                    embed_model=s.llm.default_embed_model,
                    db=db,
                )
            except ValueError as e:
                logger.warning("dense_index_build_skipped", reason=str(e))

    # Sparse BM25 index
    if mode in ("sparse", "hybrid"):
        if corpus_id not in retriever.bm25_indexes:
            try:
                await retriever.build_bm25_index(corpus_id=corpus_id, db=db)
            except Exception as e:
                logger.warning("bm25_index_build_skipped", reason=str(e))
