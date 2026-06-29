# =============================================================================
# RetrievalLab — backend/models/experiment.py
# =============================================================================
# PURPOSE : ORM models for storing retrieval experiment results in PostgreSQL.
#           Complements MLflow tracking with structured relational queries
#           (e.g., "show all experiments where corpus=healthcare AND ndcg>0.8").
#
# MODELS:
#   Experiment  — one eval run (corpus + retriever config + all metrics)
#   QueryResult — individual query result within an experiment
#
# WHY POSTGRES IN ADDITION TO MLFLOW?
#   MLflow stores flat metrics as floats. Our Leaderboard and comparison views
#   need rich SQL queries: GROUP BY corpus, WHERE domain='healthcare',
#   JOIN with corpus table. MLflow's query API is limited for this.
#   Both are written — MLflow for experiment UI, Postgres for dashboards.
#
# INPUT  : Written by EvalEngine after each evaluation run
# OUTPUT : Read by leaderboard API endpoint and React dashboard (Day 5)
# =============================================================================

from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Index,
    Boolean,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base


class RetrieverMode(str, enum.Enum):
    """Retrieval mode used in the experiment."""
    SPARSE  = "sparse"
    DENSE   = "dense"
    HYBRID  = "hybrid"
    AGENTIC = "agentic"


class Experiment(Base):
    """
    Represents one evaluation run of a retrieval configuration on a corpus.

    Each Experiment corresponds to one call to EvalEngine.evaluate() and
    stores the aggregated metric results alongside configuration details.

    Table: experiments
    """

    __tablename__ = "experiments"

    # ── Identity ─────────────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    experiment_name: Mapped[str] = mapped_column(
        String(256), nullable=False, index=True,
        comment="Human-readable name for the experiment run",
    )

    # ── Configuration ─────────────────────────────────────────────────────────
    corpus_id: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True,
        comment="corpus_id of the corpus evaluated",
    )
    retriever_mode: Mapped[RetrieverMode] = mapped_column(
        Enum(RetrieverMode, name="retriever_mode"), nullable=False,
    )
    embed_model: Mapped[str | None] = mapped_column(
        String(128), nullable=True,
        comment="Embedding model used for dense/hybrid retrieval",
    )
    chunk_strategy: Mapped[str | None] = mapped_column(
        String(64), nullable=True,
    )
    top_k: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    config_json: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict,
        comment="Full configuration snapshot for reproducibility",
    )

    # ── Aggregated retrieval metrics ──────────────────────────────────────────
    ndcg_at_10:      Mapped[float | None] = mapped_column(Float, nullable=True)
    ndcg_at_5:       Mapped[float | None] = mapped_column(Float, nullable=True)
    ndcg_at_3:       Mapped[float | None] = mapped_column(Float, nullable=True)
    mrr:             Mapped[float | None] = mapped_column(Float, nullable=True)
    map_at_10:       Mapped[float | None] = mapped_column(Float, nullable=True)
    precision_at_10: Mapped[float | None] = mapped_column(Float, nullable=True)
    recall_at_10:    Mapped[float | None] = mapped_column(Float, nullable=True)
    hit_rate_at_10:  Mapped[float | None] = mapped_column(Float, nullable=True)

    # ── Ragas metrics (optional — only populated when Ragas eval runs) ────────
    ragas_faithfulness:     Mapped[float | None] = mapped_column(Float, nullable=True)
    ragas_context_precision: Mapped[float | None] = mapped_column(Float, nullable=True)
    ragas_context_recall:   Mapped[float | None] = mapped_column(Float, nullable=True)
    ragas_answer_relevance: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ── Adversarial robustness (optional) ────────────────────────────────────
    adversarial_robustness_pct: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ── Run stats ─────────────────────────────────────────────────────────────
    query_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_s:  Mapped[float | None] = mapped_column(Float, nullable=True)
    mlflow_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_published:  Mapped[bool] = mapped_column(Boolean, nullable=False, default=False,
                                                 comment="Pinned to public leaderboard")

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    query_results: Mapped[list["QueryResult"]] = relationship(
        "QueryResult", back_populates="experiment", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_experiment_corpus_mode", "corpus_id", "retriever_mode"),
        Index("ix_experiment_ndcg", "ndcg_at_10"),
    )

    def __repr__(self) -> str:
        return (
            f"<Experiment name={self.experiment_name!r} "
            f"corpus={self.corpus_id} "
            f"ndcg@10={self.ndcg_at_10}>"
        )


class QueryResult(Base):
    """
    Per-query retrieval result within an Experiment.

    Stores individual query text, retrieved IDs, and per-query metrics.
    Enables drill-down analysis: "which queries did this retriever struggle with?"

    Table: query_results
    """

    __tablename__ = "query_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    experiment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("experiments.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    # ── Query ─────────────────────────────────────────────────────────────────
    query_text:    Mapped[str] = mapped_column(Text, nullable=False)
    query_index:   Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # ── Results snapshot ──────────────────────────────────────────────────────
    retrieved_ids: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list,
        comment="Ordered list of retrieved chunk IDs (rank 1 = first)",
    )
    relevant_ids: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict,
        comment="Ground truth: {doc_id: grade}",
    )

    # ── Per-query metrics ─────────────────────────────────────────────────────
    ndcg_at_10:  Mapped[float | None] = mapped_column(Float, nullable=True)
    mrr:         Mapped[float | None] = mapped_column(Float, nullable=True)
    hit_rate:    Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_ms:  Mapped[float | None] = mapped_column(Float, nullable=True)

    # ── Relationship ─────────────────────────────────────────────────────────
    experiment: Mapped["Experiment"] = relationship("Experiment", back_populates="query_results")

    __table_args__ = (
        Index("ix_qr_experiment_index", "experiment_id", "query_index"),
    )
