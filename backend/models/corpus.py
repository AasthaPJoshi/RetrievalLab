# =============================================================================
# RetrievalLab — backend/models/corpus.py
# =============================================================================
# PURPOSE : SQLAlchemy ORM models for the corpus layer.
#           Defines the database tables that store corpus metadata and chunks.
#
# MODELS:
#   Corpus — represents a named, versioned collection of documents
#   Chunk  — a single text chunk derived from a Corpus document
#
# RELATIONSHIPS:
#   Corpus --< Chunk   (one corpus has many chunks)
#
# KEY DESIGN CHOICES:
#   • UUIDs as primary keys: globally unique, safe for distributed systems.
#   • SHA-256 corpus fingerprint: detect if re-ingestion is needed.
#   • JSONB metadata: flexible schema for domain-specific doc attributes.
#   • pgvector `Vector` column on Chunk: enables SQL+vector hybrid queries.
#   • All timestamps in UTC (never local time).
#
# INPUT  : Written by CorpusForge pipeline after document ingestion.
# OUTPUT : Read by RetrieverCore, EvalEngine, and API endpoints.
#
# MIGRATIONS: Run `alembic revision --autogenerate -m "add corpus models"`
#             after changes to generate migration scripts.
# =============================================================================

from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base


# ─── Enumerations ────────────────────────────────────────────────────────────

class CorpusDomain(str, enum.Enum):
    """Industry domain of the corpus. Drives domain-specific chunking defaults."""
    HEALTHCARE   = "healthcare"
    FINANCE      = "finance"
    LEGAL        = "legal"
    MANUFACTURING = "manufacturing"
    ECOMMERCE    = "ecommerce"
    EDUCATION    = "education"
    CYBERSECURITY = "cybersecurity"
    GOVERNMENT   = "government"
    GENERAL      = "general"


class CorpusStatus(str, enum.Enum):
    """Ingestion lifecycle state."""
    PENDING    = "pending"     # queued for ingestion
    INGESTING  = "ingesting"   # currently being processed
    CHUNKING   = "chunking"    # documents parsed, chunking in progress
    EMBEDDING  = "embedding"   # chunks ready, embedding in progress
    READY      = "ready"       # fully indexed and queryable
    FAILED     = "failed"      # ingestion failed; see error_message
    DEPRECATED = "deprecated"  # superseded by a newer version


class ChunkStrategy(str, enum.Enum):
    """The chunking algorithm used to produce this chunk."""
    FIXED              = "fixed"
    RECURSIVE          = "recursive"
    SEMANTIC           = "semantic"
    SENTENCE_WINDOW    = "sentence_window"
    RAPTOR             = "raptor"
    PROPOSITIONAL      = "propositional"
    DOCUMENT_STRUCTURE = "document_structure"
    LATE               = "late"
    CODE_AWARE         = "code_aware"
    TABLE_AWARE        = "table_aware"


# ─── Corpus Model ────────────────────────────────────────────────────────────

class Corpus(Base):
    """
    Represents a named, versioned collection of documents for retrieval experiments.

    A Corpus is the top-level unit of data management. Every retrieval experiment
    targets a specific corpus_id. Multiple versions of the same corpus can exist
    (e.g., healthcare_pubmed_v1, healthcare_pubmed_v2).

    Table: corpora
    """

    __tablename__ = "corpora"

    # ── Primary key ──────────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Globally unique corpus identifier (UUID v4)",
    )

    # ── Identity ─────────────────────────────────────────────────────────────
    corpus_id: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        nullable=False,
        index=True,
        comment="Human-readable corpus identifier (e.g., 'healthcare_pubmed_v1')",
    )
    name: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
        comment="Display name for UI and reports",
    )
    domain: Mapped[CorpusDomain] = mapped_column(
        Enum(CorpusDomain, name="corpus_domain"),
        nullable=False,
        default=CorpusDomain.GENERAL,
        comment="Industry domain — used to select domain-specific chunking defaults",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Optional human description of corpus contents and scope",
    )

    # ── Versioning & integrity ────────────────────────────────────────────────
    version: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="v1",
        comment="Semantic version string (e.g., 'v1', 'v2.1')",
    )
    fingerprint: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="SHA-256 hash of all source file checksums. Detects changes requiring re-ingestion.",
    )

    # ── Source configuration ──────────────────────────────────────────────────
    source_path: Mapped[str | None] = mapped_column(
        String(1024),
        nullable=True,
        comment="S3 key or local path where raw documents are stored",
    )
    chunk_strategy: Mapped[ChunkStrategy] = mapped_column(
        Enum(ChunkStrategy, name="chunk_strategy"),
        nullable=False,
        default=ChunkStrategy.RECURSIVE,
        comment="Chunking strategy used for this corpus",
    )
    chunk_config: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Full chunking parameters as JSON (size, overlap, strategy-specific settings)",
    )
    embedding_model: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        comment="Embedding model used for dense index (e.g., 'text-embedding-3-small')",
    )

    # ── Statistics (updated after ingestion completes) ────────────────────────
    doc_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of source documents ingested",
    )
    chunk_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total number of chunks created",
    )
    total_tokens: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        comment="Approximate total token count across all chunks",
    )
    avg_chunk_tokens: Mapped[float | None] = mapped_column(
        nullable=True,
        comment="Mean tokens per chunk (quality signal)",
    )

    # ── Lifecycle ────────────────────────────────────────────────────────────
    status: Mapped[CorpusStatus] = mapped_column(
        Enum(CorpusStatus, name="corpus_status"),
        nullable=False,
        default=CorpusStatus.PENDING,
        index=True,
        comment="Current ingestion lifecycle state",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Last error message if status=FAILED",
    )
    is_public: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether this corpus is visible in public leaderboard experiments",
    )

    # ── Timestamps ───────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        comment="UTC timestamp when corpus record was created",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        comment="UTC timestamp of last status update",
    )
    ingestion_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="UTC timestamp when ingestion reached READY status",
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    chunks: Mapped[list["Chunk"]] = relationship(
        "Chunk",
        back_populates="corpus",
        cascade="all, delete-orphan",
        lazy="select",
    )

    # ── Constraints & Indexes ─────────────────────────────────────────────────
    __table_args__ = (
        UniqueConstraint("corpus_id", name="uq_corpus_corpus_id"),
        Index("ix_corpus_domain_status", "domain", "status"),
        Index("ix_corpus_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Corpus corpus_id={self.corpus_id!r} domain={self.domain} status={self.status}>"


# ─── Chunk Model ─────────────────────────────────────────────────────────────

class Chunk(Base):
    """
    A single text chunk produced from a source document in a Corpus.

    Chunks are the atomic unit of retrieval. The embedding vector column
    enables pgvector similarity searches directly in SQL, useful for
    hybrid SQL+vector queries (e.g., filter by domain + vector similarity).

    Table: chunks
    """

    __tablename__ = "chunks"

    # ── Primary key ──────────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # ── Foreign key ──────────────────────────────────────────────────────────
    corpus_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("corpora.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Parent corpus this chunk belongs to",
    )

    # ── Content ──────────────────────────────────────────────────────────────
    text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Raw text content of the chunk",
    )
    token_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Approximate token count (tiktoken cl100k_base)",
    )

    # ── Provenance ───────────────────────────────────────────────────────────
    source_doc_id: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
        index=True,
        comment="Original document identifier (filename, URL, or DOI)",
    )
    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Position of this chunk within the parent document (0-indexed)",
    )
    parent_chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chunks.id", ondelete="SET NULL"),
        nullable=True,
        comment="For hierarchical strategies (RAPTOR): parent chunk reference",
    )

    # ── Chunking metadata ─────────────────────────────────────────────────────
    chunk_strategy: Mapped[ChunkStrategy] = mapped_column(
        Enum(ChunkStrategy, name="chunk_strategy"),
        nullable=False,
    )
    chunk_metadata: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Strategy-specific metadata: section headers, page numbers, table coords, etc.",
    )

    # ── Embedding ────────────────────────────────────────────────────────────
    # Vector dimension must match the embedding model used.
    # text-embedding-3-small = 1536 dims
    # BGE-M3 = 1024 dims
    # Change dimension if switching default embed model.
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(1536),
        nullable=True,
        comment="Dense embedding vector (pgvector). None until embedding step completes.",
    )
    embedding_model: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        comment="Model used to generate the embedding (e.g., 'text-embedding-3-small')",
    )
    embedding_created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When the embedding was generated (for cache invalidation)",
    )

    # ── Timestamps ───────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    corpus: Mapped["Corpus"] = relationship("Corpus", back_populates="chunks")

    # ── Indexes ──────────────────────────────────────────────────────────────
    __table_args__ = (
        # Composite index for the most common query: chunks for a corpus in order
        Index("ix_chunk_corpus_index", "corpus_id", "chunk_index"),
        # Partial index for chunks that have embeddings (for vector queries)
        Index(
            "ix_chunk_embedding_not_null",
            "corpus_id",
            postgresql_where="embedding IS NOT NULL",
        ),
        # IVFFlat index for pgvector approximate nearest-neighbor search.
        # lists=100 is suitable for up to ~1M vectors.
        # Rebuild with higher lists count when corpus grows past 1M chunks.
        Index(
            "ix_chunk_embedding_ivfflat",
            "embedding",
            postgresql_using="ivfflat",
            postgresql_ops={"embedding": "vector_cosine_ops"},
            postgresql_with={"lists": "100"},
        ),
    )

    def __repr__(self) -> str:
        preview = self.text[:60].replace("\n", " ") + ("..." if len(self.text) > 60 else "")
        return f"<Chunk id={self.id} corpus={self.corpus_id} tokens={self.token_count} text={preview!r}>"
