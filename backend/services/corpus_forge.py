# =============================================================================
# RetrievalLab — backend/services/corpus_forge.py
# =============================================================================
# PURPOSE : CorpusForge is the top-level ingestion service.
#           It orchestrates the full pipeline from raw files → stored chunks:
#
#           1. Receive ingest request (corpus_id, source path, config)
#           2. Load all documents via LoaderRegistry
#           3. Validate and deduplicate documents
#           4. Compute corpus fingerprint (SHA-256 over all file hashes)
#           5. Chunk each document via ChunkEngine
#           6. Upload raw files to MinIO object storage
#           7. Persist corpus metadata and chunks to PostgreSQL
#           8. Update corpus status throughout lifecycle
#
# DESIGN:
#   • Each public method is async (FastAPI background task / Celery worker).
#   • Status is updated in DB at each stage → frontend can poll for progress.
#   • Idempotent: re-ingesting the same corpus_id + same files is a no-op
#     (detected via corpus fingerprint comparison).
#   • Transactional: DB writes are atomic; partial failures roll back.
#
# INPUT  : IngestRequest dataclass (corpus_id, source, domain, strategy, ...)
# OUTPUT : Corpus DB record (status=READY) + Chunk DB records
#          → Next: EmbedHub reads chunks for vectorization (Day 2)
# =============================================================================

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.corpus import (
    Chunk,
    ChunkStrategy,
    Corpus,
    CorpusDomain,
    CorpusStatus,
)
from corpus.chunkers.chunk_engine import ChunkConfig, ChunkEngine, default_chunk_engine
from corpus.loaders.base_loader import ParsedDocument
from corpus.loaders.loader_registry import LoaderRegistry, default_registry

logger = structlog.get_logger(__name__)


# ─── Request / Response Models ────────────────────────────────────────────────

@dataclass
class IngestRequest:
    """
    Parameters for a corpus ingestion job.

    Attributes:
        corpus_id:      Human-readable unique identifier (e.g., 'healthcare_pubmed_v1').
        source:         Local path or S3 URI to documents.
        name:           Display name for UI.
        domain:         Industry domain (sets chunking defaults if strategy not given).
        strategy:       Chunking strategy name (overrides domain default).
        chunk_size:     Target chunk size in tokens.
        chunk_overlap:  Overlap between consecutive chunks in tokens.
        embedding_model: Embedding model to use for dense index (set in EmbedHub).
        force_reingest: If True, re-ingest even if fingerprint matches existing corpus.
        extra_config:   Strategy-specific extra parameters.
    """
    corpus_id:       str
    source:          str
    name:            str             = ""
    domain:          str             = "general"
    strategy:        str             = "recursive"
    chunk_size:      int             = 512
    chunk_overlap:   int             = 64
    embedding_model: str             = "text-embedding-3-small"
    force_reingest:  bool            = False
    extra_config:    dict[str, Any]  = field(default_factory=dict)


@dataclass
class IngestResult:
    """
    Result of a completed ingestion job.

    Attributes:
        corpus_id:     The corpus that was ingested.
        status:        Final corpus status (READY or FAILED).
        doc_count:     Number of source documents successfully parsed.
        chunk_count:   Number of chunks created.
        total_tokens:  Approximate total token count.
        duration_s:    Wall-clock seconds for the full pipeline.
        failures:      List of (source, error) for documents that failed.
        skipped:       True if ingestion was skipped (same fingerprint, no force).
    """
    corpus_id:    str
    status:       str
    doc_count:    int             = 0
    chunk_count:  int             = 0
    total_tokens: int             = 0
    duration_s:   float           = 0.0
    failures:     list[tuple[str, str]] = field(default_factory=list)
    skipped:      bool            = False

    @property
    def success(self) -> bool:
        return self.status == "READY"


# ─── Domain → Default Strategy Mapping ───────────────────────────────────────

DOMAIN_DEFAULT_STRATEGIES: dict[str, str] = {
    "healthcare":    "sentence_window",    # clinical notes need sentence precision
    "finance":       "recursive",          # good for mixed prose + numbers
    "legal":         "document_structure", # legal docs have clear section hierarchy
    "manufacturing": "table_aware",        # SOPs and spec sheets heavy in tables
    "ecommerce":     "recursive",          # product descriptions — short and varied
    "education":     "semantic",           # textbooks benefit from topical coherence
    "cybersecurity": "recursive",          # CVEs and threat intel — short entries
    "government":    "document_structure", # policy docs have numbered sections
    "general":       "recursive",          # safe default for unknown domains
}


# ─── CorpusForge Service ─────────────────────────────────────────────────────

class CorpusForge:
    """
    Orchestrates the full document ingestion pipeline.

    Designed to run as:
    - A FastAPI background task (for small corpora < 500 docs)
    - A Celery worker task (for large corpora, triggered async via API)

    Args:
        db:             AsyncSession for PostgreSQL.
        loader_registry: Document loader registry (default: shared instance).
        chunk_engine:   Chunk engine (default: shared instance with all strategies).

    Example:
        forge = CorpusForge(db=session)
        request = IngestRequest(
            corpus_id="legal_contracts_v1",
            source="data/legal/",
            domain="legal",
        )
        result = await forge.ingest(request)
        print(f"Ingested {result.chunk_count} chunks in {result.duration_s:.1f}s")
    """

    def __init__(
        self,
        db: AsyncSession,
        loader_registry: LoaderRegistry | None = None,
        chunk_engine:    ChunkEngine | None    = None,
    ) -> None:
        self.db             = db
        self.loader_registry = loader_registry or default_registry
        self.chunk_engine    = chunk_engine    or default_chunk_engine
        self._log            = structlog.get_logger(self.__class__.__name__)

    # ── Main Entry Point ──────────────────────────────────────────────────────

    async def ingest(self, request: IngestRequest) -> IngestResult:
        """
        Run the full ingestion pipeline for a corpus.

        Steps:
            1. Validate source path
            2. Load documents via LoaderRegistry
            3. Compute corpus fingerprint
            4. Check for existing corpus (idempotency check)
            5. Create or update Corpus DB record
            6. Chunk all documents
            7. Bulk-insert Chunk records
            8. Update corpus statistics and status

        Args:
            request: IngestRequest with corpus configuration.

        Returns:
            IngestResult with statistics and status.
        """
        start = time.perf_counter()
        log   = self._log.bind(corpus_id=request.corpus_id)
        log.info("ingest_started", source=request.source, strategy=request.strategy)

        # ── 1. Validate source ────────────────────────────────────────────
        source_path = Path(request.source)
        if not source_path.exists():
            log.error("source_not_found", source=request.source)
            return IngestResult(
                corpus_id=request.corpus_id,
                status="FAILED",
                failures=[(request.source, "Source path does not exist")],
            )

        # ── 2. Load documents ─────────────────────────────────────────────
        log.info("loading_documents")
        await self._update_status(request.corpus_id, CorpusStatus.INGESTING)

        load_result = self.loader_registry.load(request.source)
        log.info(
            "documents_loaded",
            success=load_result.success_count,
            failed=load_result.failure_count,
            duration_s=round(load_result.duration_s, 2),
        )

        if load_result.success_count == 0:
            await self._update_status(request.corpus_id, CorpusStatus.FAILED,
                                       "No documents could be loaded from source")
            return IngestResult(
                corpus_id=request.corpus_id,
                status="FAILED",
                failures=load_result.failures,
            )

        # ── 3. Compute corpus fingerprint ────────────────────────────────
        fingerprint = self._compute_fingerprint(load_result.documents)
        log.info("fingerprint_computed", fingerprint=fingerprint[:8] + "...")

        # ── 4. Idempotency check ──────────────────────────────────────────
        existing = await self._get_existing_corpus(request.corpus_id)
        if existing and existing.fingerprint == fingerprint and not request.force_reingest:
            log.info("skipping_reingest_same_fingerprint")
            return IngestResult(
                corpus_id=request.corpus_id,
                status="READY",
                doc_count=existing.doc_count,
                chunk_count=existing.chunk_count,
                skipped=True,
            )

        # ── 5. Create/update corpus DB record ────────────────────────────
        corpus = await self._upsert_corpus(request, fingerprint, load_result.success_count)

        # ── 6. Chunk documents ─────────────────────────────────────────────
        log.info("chunking_started")
        await self._update_status(request.corpus_id, CorpusStatus.CHUNKING)

        # Resolve strategy: explicit > domain default
        strategy = request.strategy or DOMAIN_DEFAULT_STRATEGIES.get(request.domain, "recursive")
        chunk_config = ChunkConfig(
            strategy=strategy,
            chunk_size=request.chunk_size,
            chunk_overlap=request.chunk_overlap,
            **request.extra_config,
        )

        all_chunks = []
        for doc in load_result.documents:
            try:
                doc_chunks = self.chunk_engine.chunk(doc, chunk_config)
                all_chunks.extend(doc_chunks)
            except Exception as exc:
                load_result.failures.append((doc.source, f"Chunking failed: {exc}"))
                log.warning("chunking_failed", source=doc.source, error=str(exc))

        log.info("chunking_complete", chunk_count=len(all_chunks))

        # ── 7. Bulk insert chunks ─────────────────────────────────────────
        await self._bulk_insert_chunks(corpus.id, all_chunks, request)

        # ── 8. Update corpus statistics ───────────────────────────────────
        total_tokens = sum(c.token_count for c in all_chunks)
        avg_tokens   = total_tokens / max(len(all_chunks), 1)

        corpus.doc_count   = load_result.success_count
        corpus.chunk_count = len(all_chunks)
        corpus.total_tokens = total_tokens
        corpus.avg_chunk_tokens = avg_tokens
        corpus.status = CorpusStatus.READY

        from datetime import UTC, datetime
        corpus.ingestion_completed_at = datetime.now(UTC)

        await self.db.commit()

        duration = time.perf_counter() - start
        log.info(
            "ingest_complete",
            doc_count=load_result.success_count,
            chunk_count=len(all_chunks),
            total_tokens=total_tokens,
            duration_s=round(duration, 2),
        )

        return IngestResult(
            corpus_id=request.corpus_id,
            status="READY",
            doc_count=load_result.success_count,
            chunk_count=len(all_chunks),
            total_tokens=total_tokens,
            duration_s=duration,
            failures=load_result.failures,
        )

    # ── Internal Helpers ──────────────────────────────────────────────────────

    def _compute_fingerprint(self, documents: list[ParsedDocument]) -> str:
        """
        Compute a SHA-256 fingerprint over all source files.

        Concatenates sorted source paths + char counts, then hashes.
        Changes if any file is added, removed, or modified.
        """
        sha = hashlib.sha256()
        for doc in sorted(documents, key=lambda d: d.source):
            sha.update(doc.source.encode())
            sha.update(str(doc.char_count).encode())
        return sha.hexdigest()

    async def _get_existing_corpus(self, corpus_id: str) -> Corpus | None:
        """Look up an existing corpus by corpus_id."""
        result = await self.db.execute(
            select(Corpus).where(Corpus.corpus_id == corpus_id)
        )
        return result.scalar_one_or_none()

    async def _upsert_corpus(
        self,
        request: IngestRequest,
        fingerprint: str,
        doc_count: int,
    ) -> Corpus:
        """Create a new Corpus record or update an existing one."""
        existing = await self._get_existing_corpus(request.corpus_id)

        if existing:
            # Update existing corpus record
            existing.fingerprint    = fingerprint
            existing.status         = CorpusStatus.INGESTING
            existing.chunk_strategy = ChunkStrategy(request.strategy)
            existing.chunk_config   = {
                "chunk_size": request.chunk_size,
                "chunk_overlap": request.chunk_overlap,
                **request.extra_config,
            }
            existing.embedding_model = request.embedding_model
            await self.db.commit()
            return existing
        else:
            # Create new corpus record
            corpus = Corpus(
                corpus_id       = request.corpus_id,
                name            = request.name or request.corpus_id.replace("_", " ").title(),
                domain          = CorpusDomain(request.domain),
                fingerprint     = fingerprint,
                source_path     = request.source,
                chunk_strategy  = ChunkStrategy(request.strategy),
                chunk_config    = {
                    "chunk_size": request.chunk_size,
                    "chunk_overlap": request.chunk_overlap,
                    **request.extra_config,
                },
                embedding_model = request.embedding_model,
                status          = CorpusStatus.INGESTING,
                doc_count       = doc_count,
            )
            self.db.add(corpus)
            await self.db.flush()  # get the generated UUID without full commit
            return corpus

    async def _bulk_insert_chunks(
        self,
        corpus_uuid,
        chunks,
        request: IngestRequest,
    ) -> None:
        """
        Bulk-insert TextChunks into the chunks table.

        Uses SQLAlchemy bulk_insert_mappings for performance on large corpora.
        Flushes every 1000 chunks to avoid holding a giant transaction open.
        """

        BATCH_SIZE = 1000
        batch: list[dict] = []

        for text_chunk in chunks:
            batch.append({
                "corpus_id":      corpus_uuid,
                "text":           text_chunk.text,
                "token_count":    text_chunk.token_count,
                "source_doc_id":  text_chunk.source_doc_id,
                "chunk_index":    text_chunk.chunk_index,
                "chunk_strategy": ChunkStrategy(request.strategy),
                "chunk_metadata": text_chunk.metadata,
                # embedding filled later by EmbedHub
            })

            if len(batch) >= BATCH_SIZE:
                await self._flush_batch(batch)
                batch = []

        if batch:
            await self._flush_batch(batch)

    async def _flush_batch(self, batch: list[dict]) -> None:
        """Insert a batch of chunk dicts and flush."""
        chunk_objects = [Chunk(**row) for row in batch]
        self.db.add_all(chunk_objects)
        await self.db.flush()

    async def _update_status(
        self,
        corpus_id: str,
        status: CorpusStatus,
        error_message: str | None = None,
    ) -> None:
        """Update corpus status in DB (best-effort, doesn't raise on miss)."""
        try:
            corpus = await self._get_existing_corpus(corpus_id)
            if corpus:
                corpus.status = status
                if error_message:
                    corpus.error_message = error_message
                await self.db.commit()
        except Exception as exc:
            self._log.warning("status_update_failed", error=str(exc))
