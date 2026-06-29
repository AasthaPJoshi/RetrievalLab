# =============================================================================
# RetrievalLab — backend/api/v1/endpoints/corpus.py
# =============================================================================
# PURPOSE : FastAPI router for corpus management endpoints.
#           Handles ingestion, status polling, corpus listing, and deletion.
#
# ENDPOINTS:
#   POST /api/v1/corpus/ingest      → trigger ingestion job
#   GET  /api/v1/corpus/            → list all corpora
#   GET  /api/v1/corpus/{corpus_id} → get corpus details + stats
#   GET  /api/v1/corpus/{corpus_id}/chunks → paginated chunk browser
#   DELETE /api/v1/corpus/{corpus_id}     → delete corpus and all chunks
#
# ASYNC JOB PATTERN:
#   Ingest returns immediately with a job_id.
#   Client polls GET /corpus/{corpus_id} to check status.
#   Status transitions: PENDING → INGESTING → CHUNKING → READY | FAILED
#
# INPUT  : HTTP requests with JSON bodies validated by Pydantic v2 schemas
# OUTPUT : JSON responses (Pydantic model → dict)
# =============================================================================

from __future__ import annotations

from typing import Annotated

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.base import get_db
from backend.models.corpus import Corpus, Chunk, CorpusDomain, CorpusStatus
from backend.services.corpus_forge import CorpusForge, IngestRequest

logger  = structlog.get_logger(__name__)
router  = APIRouter()


# ─── Pydantic Request / Response Schemas ─────────────────────────────────────

class IngestRequestSchema(BaseModel):
    """Request body for POST /corpus/ingest"""

    corpus_id:       str   = Field(
        ...,
        min_length=3,
        max_length=128,
        pattern=r"^[a-zA-Z0-9_\-]+$",
        description="Unique corpus identifier. Use snake_case (e.g., 'healthcare_pubmed_v1')",
        examples=["healthcare_pubmed_v1"],
    )
    source:          str   = Field(
        ...,
        description="Local file path or S3 URI to the documents directory or single file",
        examples=["data/seeds/healthcare/", "s3://mybucket/legal-contracts/"],
    )
    name:            str   = Field(
        default="",
        description="Human-readable display name (auto-generated from corpus_id if empty)",
    )
    domain:          str   = Field(
        default="general",
        description="Industry domain — affects default chunking strategy selection",
        examples=["healthcare", "finance", "legal"],
    )
    strategy:        str   = Field(
        default="recursive",
        description="Chunking strategy name",
        examples=["recursive", "semantic", "sentence_window", "document_structure"],
    )
    chunk_size:      int   = Field(default=512,  ge=64,  le=2048, description="Target chunk size in tokens")
    chunk_overlap:   int   = Field(default=64,   ge=0,   le=512,  description="Overlap between chunks in tokens")
    embedding_model: str   = Field(
        default="text-embedding-3-small",
        description="Embedding model for dense index (used by EmbedHub in Day 2)",
    )
    force_reingest:  bool  = Field(
        default=False,
        description="If true, re-ingest even if corpus fingerprint matches existing",
    )


class CorpusResponse(BaseModel):
    """Response schema for a single corpus record."""

    corpus_id:       str
    name:            str
    domain:          str
    version:         str
    status:          str
    doc_count:       int
    chunk_count:     int
    total_tokens:    int
    avg_chunk_tokens: float | None
    chunk_strategy:  str
    embedding_model: str | None
    fingerprint:     str | None
    created_at:      str
    updated_at:      str

    model_config = {"from_attributes": True}


class ChunkResponse(BaseModel):
    """Response schema for a chunk preview."""

    chunk_id:      str
    text:          str
    token_count:   int
    chunk_index:   int
    source_doc_id: str | None
    strategy:      str

    model_config = {"from_attributes": True}


class IngestJobResponse(BaseModel):
    """Immediate response from POST /corpus/ingest — job is queued."""

    corpus_id:  str
    status:     str
    message:    str


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post(
    "/ingest",
    response_model=IngestJobResponse,
    status_code=202,   # 202 Accepted — processing happens asynchronously
    summary="Ingest documents into a corpus",
    description=(
        "Upload or reference documents for ingestion. "
        "Returns immediately; monitor progress via GET /corpus/{corpus_id}. "
        "Ingestion runs as a FastAPI BackgroundTask."
    ),
)
async def ingest_corpus(
    body:               IngestRequestSchema,
    background_tasks:   BackgroundTasks,
    db:                 AsyncSession = Depends(get_db),
) -> IngestJobResponse:
    """
    Trigger corpus ingestion as a background task.

    The response (202 Accepted) is returned immediately.
    The actual work happens asynchronously — poll the corpus status endpoint.
    """
    log = logger.bind(corpus_id=body.corpus_id)
    log.info("ingest_request_received", source=body.source, strategy=body.strategy)

    # Build the internal request object
    request = IngestRequest(
        corpus_id       = body.corpus_id,
        source          = body.source,
        name            = body.name,
        domain          = body.domain,
        strategy        = body.strategy,
        chunk_size      = body.chunk_size,
        chunk_overlap   = body.chunk_overlap,
        embedding_model = body.embedding_model,
        force_reingest  = body.force_reingest,
    )

    # Queue ingestion as a FastAPI background task.
    # For production with large corpora, replace with Celery:
    #   celery_task = ingest_corpus_task.delay(request)
    background_tasks.add_task(_run_ingest_background, request)

    return IngestJobResponse(
        corpus_id = body.corpus_id,
        status    = "PENDING",
        message   = (
            f"Ingestion queued for corpus '{body.corpus_id}'. "
            f"Poll GET /api/v1/corpus/{body.corpus_id} to track progress."
        ),
    )


async def _run_ingest_background(request: IngestRequest) -> None:
    """
    Background task runner for corpus ingestion.

    Gets a fresh DB session (background tasks don't share the request session).
    """
    from backend.db.base import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        forge = CorpusForge(db=db)
        result = await forge.ingest(request)
        if not result.success and not result.skipped:
            logger.error(
                "background_ingest_failed",
                corpus_id=request.corpus_id,
                failures=result.failures,
            )


@router.get(
    "/",
    response_model=list[CorpusResponse],
    summary="List all corpora",
    description="Returns all corpora ordered by creation date (newest first).",
)
async def list_corpora(
    domain: str | None   = Query(default=None, description="Filter by domain"),
    status: str | None   = Query(default=None, description="Filter by status (READY, FAILED, etc.)"),
    limit:  int          = Query(default=20, ge=1, le=100),
    offset: int          = Query(default=0, ge=0),
    db:     AsyncSession = Depends(get_db),
) -> list[CorpusResponse]:
    """
    List all corpora with optional domain/status filtering.

    Args:
        domain: Filter to corpora of a specific domain.
        status: Filter by lifecycle status.
        limit:  Max results to return (pagination).
        offset: Skip N results (pagination).
    """
    query = select(Corpus).order_by(Corpus.created_at.desc())

    if domain:
        try:
            query = query.where(Corpus.domain == CorpusDomain(domain))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid domain: {domain!r}")

    if status:
        try:
            query = query.where(Corpus.status == CorpusStatus(status.upper()))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status!r}")

    query  = query.limit(limit).offset(offset)
    result = await db.execute(query)
    corpora = result.scalars().all()

    return [_corpus_to_response(c) for c in corpora]


@router.get(
    "/{corpus_id}",
    response_model=CorpusResponse,
    summary="Get corpus details",
    description="Returns metadata, statistics, and current ingestion status for a corpus.",
)
async def get_corpus(
    corpus_id: str,
    db:        AsyncSession = Depends(get_db),
) -> CorpusResponse:
    """Fetch a single corpus by its corpus_id string."""
    result = await db.execute(
        select(Corpus).where(Corpus.corpus_id == corpus_id)
    )
    corpus = result.scalar_one_or_none()

    if corpus is None:
        raise HTTPException(status_code=404, detail=f"Corpus '{corpus_id}' not found")

    return _corpus_to_response(corpus)


@router.get(
    "/{corpus_id}/chunks",
    response_model=list[ChunkResponse],
    summary="Browse chunks in a corpus",
    description="Returns paginated chunks for a corpus. Useful for inspecting chunking quality.",
)
async def list_chunks(
    corpus_id:  str,
    limit:      int          = Query(default=20, ge=1, le=200),
    offset:     int          = Query(default=0, ge=0),
    source_doc: str | None   = Query(default=None, description="Filter by source document ID"),
    db:         AsyncSession = Depends(get_db),
) -> list[ChunkResponse]:
    """Paginated chunk browser for a specific corpus."""
    # First verify corpus exists
    corpus_result = await db.execute(
        select(Corpus).where(Corpus.corpus_id == corpus_id)
    )
    corpus = corpus_result.scalar_one_or_none()
    if corpus is None:
        raise HTTPException(status_code=404, detail=f"Corpus '{corpus_id}' not found")

    query = (
        select(Chunk)
        .where(Chunk.corpus_id == corpus.id)
        .order_by(Chunk.chunk_index)
    )

    if source_doc:
        query = query.where(Chunk.source_doc_id == source_doc)

    query  = query.limit(limit).offset(offset)
    result = await db.execute(query)
    chunks = result.scalars().all()

    return [
        ChunkResponse(
            chunk_id      = str(c.id),
            text          = c.text,
            token_count   = c.token_count,
            chunk_index   = c.chunk_index,
            source_doc_id = c.source_doc_id,
            strategy      = c.chunk_strategy.value,
        )
        for c in chunks
    ]


@router.delete(
    "/{corpus_id}",
    status_code=204,
    summary="Delete a corpus",
    description="Permanently deletes a corpus and all its chunks. This cannot be undone.",
)
async def delete_corpus(
    corpus_id: str,
    db:        AsyncSession = Depends(get_db),
) -> None:
    """Delete a corpus and cascade-delete all associated chunks."""
    result = await db.execute(
        select(Corpus).where(Corpus.corpus_id == corpus_id)
    )
    corpus = result.scalar_one_or_none()

    if corpus is None:
        raise HTTPException(status_code=404, detail=f"Corpus '{corpus_id}' not found")

    await db.delete(corpus)  # CASCADE deletes chunks too (FK constraint)
    await db.commit()

    logger.info("corpus_deleted", corpus_id=corpus_id)


# ─── Internal Helpers ─────────────────────────────────────────────────────────

def _corpus_to_response(corpus: Corpus) -> CorpusResponse:
    """Convert a Corpus ORM model to a CorpusResponse dict."""
    return CorpusResponse(
        corpus_id        = corpus.corpus_id,
        name             = corpus.name,
        domain           = corpus.domain.value,
        version          = corpus.version,
        status           = corpus.status.value,
        doc_count        = corpus.doc_count,
        chunk_count      = corpus.chunk_count,
        total_tokens     = corpus.total_tokens,
        avg_chunk_tokens = corpus.avg_chunk_tokens,
        chunk_strategy   = corpus.chunk_strategy.value,
        embedding_model  = corpus.embedding_model,
        fingerprint      = corpus.fingerprint,
        created_at       = corpus.created_at.isoformat(),
        updated_at       = corpus.updated_at.isoformat(),
    )
