# =============================================================================
# RetrievalLab — eval/metrics/retrieval_metrics.py
# =============================================================================
# PURPOSE : Implements the standard IR evaluation metrics used throughout
#           RetrievalLab's EvalEngine, BEIR runner, and adversarial harness.
#
# METRICS IMPLEMENTED:
#   ndcg_at_k       — Normalized Discounted Cumulative Gain @K
#   mrr             — Mean Reciprocal Rank
#   map_at_k        — Mean Average Precision @K
#   precision_at_k  — Precision @K
#   recall_at_k     — Recall @K (for completeness comparison)
#   hit_rate_at_k   — Binary: did any relevant doc appear in top-K?
#
# WHY THESE METRICS:
#   NDCG@10 is the gold standard for ranked IR systems. It rewards placing
#   highly-relevant results higher in the list (graded relevance).
#   MRR measures time-to-first-relevant-result (critical for Q&A applications).
#   MAP balances precision and recall across all relevant documents.
#
# MATHEMATICAL DEFINITIONS:
#   DCG@K = Σ (2^rel_i - 1) / log2(rank_i + 1)   for i in 1..K
#   NDCG@K = DCG@K / IDCG@K   (IDCG = ideal DCG if results were perfectly ordered)
#   RR(q) = 1/rank_of_first_relevant_doc  (0 if none in top-K)
#   MRR = mean(RR) over all queries
#   AP@K = Σ P@i * rel_i / min(|relevant|, K)
#
# HOW TO USE:
#   from eval.metrics.retrieval_metrics import evaluate_retrieval
#
#   score = evaluate_retrieval(
#       retrieved=["doc3", "doc1", "doc5"],   # retrieved doc ids in rank order
#       relevant={"doc1": 1, "doc3": 2},      # relevant doc ids → relevance grade
#   )
#   print(score.ndcg_at_10, score.mrr, score.precision_at_5)
#
# INPUT  : Retrieved doc IDs (ranked list) + relevant doc IDs (with grades)
# OUTPUT : EvalScore dataclass with all metric values
#
# AFTER THIS FILE:
#   Scores aggregated by → RagasEvaluator and BEIRRunner → MLflow (Day 3)
# =============================================================================

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field

# ─── Data Classes ─────────────────────────────────────────────────────────────


@dataclass
class EvalScore:
    """
    All retrieval evaluation scores for a single query.

    Attributes:
        ndcg_at_k:     NDCG@K (K=1,3,5,10). Key metric for ranked retrieval.
        mrr:           Mean Reciprocal Rank (single-query).
        map_at_k:      Mean Average Precision @K.
        precision_at_k: Precision @K (K=1,3,5,10).
        recall_at_k:   Recall @K.
        hit_rate_at_k: Binary hit rate @K.
        query:         The query text (for logging).
        retrieved_ids: The retrieved document IDs in order.
        relevant_ids:  The ground-truth relevant document IDs.
        k:             The cutoff K used.
    """

    # Core metrics (most important first)
    ndcg_at_10: float = 0.0
    ndcg_at_5: float = 0.0
    ndcg_at_3: float = 0.0
    ndcg_at_1: float = 0.0
    mrr: float = 0.0
    map_at_10: float = 0.0
    precision_at_10: float = 0.0
    precision_at_5: float = 0.0
    precision_at_3: float = 0.0
    precision_at_1: float = 0.0
    recall_at_10: float = 0.0
    recall_at_5: float = 0.0
    hit_rate_at_10: float = 0.0

    # Context
    query: str = ""
    retrieved_ids: list[str] = field(default_factory=list)
    relevant_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, float]:
        """Return all numeric metrics as a flat dict (for MLflow logging)."""
        return {
            "ndcg@10": self.ndcg_at_10,
            "ndcg@5": self.ndcg_at_5,
            "ndcg@3": self.ndcg_at_3,
            "ndcg@1": self.ndcg_at_1,
            "mrr": self.mrr,
            "map@10": self.map_at_10,
            "precision@10": self.precision_at_10,
            "precision@5": self.precision_at_5,
            "precision@3": self.precision_at_3,
            "precision@1": self.precision_at_1,
            "recall@10": self.recall_at_10,
            "recall@5": self.recall_at_5,
            "hit_rate@10": self.hit_rate_at_10,
        }


@dataclass
class AggregatedEvalScore:
    """
    Macro-averaged metrics across all queries in an evaluation run.

    Used for BEIR suite results and overall leaderboard scores.
    """

    ndcg_at_10: float = 0.0
    ndcg_at_5: float = 0.0
    ndcg_at_3: float = 0.0
    mrr: float = 0.0
    map_at_10: float = 0.0
    precision_at_10: float = 0.0
    recall_at_10: float = 0.0
    hit_rate_at_10: float = 0.0
    query_count: int = 0

    def to_dict(self) -> dict[str, float]:
        return {
            "avg_ndcg@10": self.ndcg_at_10,
            "avg_ndcg@5": self.ndcg_at_5,
            "avg_ndcg@3": self.ndcg_at_3,
            "avg_mrr": self.mrr,
            "avg_map@10": self.map_at_10,
            "avg_precision@10": self.precision_at_10,
            "avg_recall@10": self.recall_at_10,
            "avg_hit_rate@10": self.hit_rate_at_10,
            "query_count": float(self.query_count),
        }


# ─── Core Metric Functions ────────────────────────────────────────────────────


def dcg_at_k(
    retrieved: Sequence[str],
    relevant: dict[str, float],
    k: int,
) -> float:
    """
    Compute Discounted Cumulative Gain @K.

    Args:
        retrieved: Doc IDs in retrieved rank order (rank 1 = first element).
        relevant:  Dict mapping doc_id → relevance grade (1.0 = relevant, 2.0 = highly relevant).
        k:         Cutoff rank.

    Returns:
        DCG@K score (higher = better).

    Example:
        dcg = dcg_at_k(["a","b","c"], {"a": 2.0, "c": 1.0}, k=3)
    """
    dcg = 0.0
    for rank, doc_id in enumerate(retrieved[:k], start=1):
        rel = relevant.get(doc_id, 0.0)
        if rel > 0:
            # Standard DCG formula: (2^rel - 1) / log2(rank + 1)
            dcg += (2.0**rel - 1.0) / math.log2(rank + 1)
    return dcg


def idcg_at_k(relevant: dict[str, float], k: int) -> float:
    """
    Compute Ideal DCG @K — the maximum possible DCG if results were perfect.

    Places documents in descending relevance order, computes DCG.

    Args:
        relevant: Dict of relevant doc IDs → relevance grades.
        k:        Cutoff rank.

    Returns:
        IDCG@K (used as normalizer for NDCG).
    """
    ideal_rels = sorted(relevant.values(), reverse=True)[:k]
    idcg = 0.0
    for rank, rel in enumerate(ideal_rels, start=1):
        if rel > 0:
            idcg += (2.0**rel - 1.0) / math.log2(rank + 1)
    return idcg


def ndcg_at_k(
    retrieved: Sequence[str],
    relevant: dict[str, float],
    k: int,
) -> float:
    """
    Compute Normalized Discounted Cumulative Gain @K.

    NDCG = DCG@K / IDCG@K  (range: 0.0 to 1.0)

    This is the primary metric for ranking quality.
    1.0 = perfect ranking; 0.0 = no relevant results retrieved.

    Args:
        retrieved: Ranked list of retrieved doc IDs.
        relevant:  Ground truth: doc_id → relevance grade (1.0 = relevant).
                   Binary relevance: use {doc_id: 1.0} for all relevant docs.
        k:         Cutoff rank (typically 10 for web search, 5 for medical).

    Returns:
        NDCG@K in [0.0, 1.0].

    Example:
        score = ndcg_at_k(["a","b","c"], {"a": 1.0, "c": 1.0}, k=5)
        # a is rank 1 (good), c is rank 3 (ok), b is irrelevant → score ~ 0.74
    """
    ideal = idcg_at_k(relevant, k)
    if ideal == 0.0:
        return 0.0
    return dcg_at_k(retrieved, relevant, k) / ideal


def reciprocal_rank(
    retrieved: Sequence[str],
    relevant: dict[str, float],
    k: int = 10,
) -> float:
    """
    Compute Reciprocal Rank for a single query.

    RR = 1/rank_of_first_relevant_result  (0 if none in top K).

    Args:
        retrieved: Ranked list of retrieved doc IDs.
        relevant:  Relevant doc IDs (with any positive grade).
        k:         Only consider top-K results.

    Returns:
        Reciprocal rank in (0.0, 1.0].
    """
    for rank, doc_id in enumerate(retrieved[:k], start=1):
        if relevant.get(doc_id, 0.0) > 0:
            return 1.0 / rank
    return 0.0


def precision_at_k(
    retrieved: Sequence[str],
    relevant: dict[str, float],
    k: int,
) -> float:
    """
    Precision @K: fraction of top-K retrieved docs that are relevant.

    P@K = |{retrieved ∩ relevant}| / K

    Args:
        retrieved: Ranked list of retrieved doc IDs.
        relevant:  Relevant doc IDs (any positive grade counts as relevant).
        k:         Cutoff rank.

    Returns:
        Precision @K in [0.0, 1.0].
    """
    top_k = list(retrieved[:k])
    n_relevant = sum(1 for d in top_k if relevant.get(d, 0.0) > 0)
    return n_relevant / k if k > 0 else 0.0


def recall_at_k(
    retrieved: Sequence[str],
    relevant: dict[str, float],
    k: int,
) -> float:
    """
    Recall @K: fraction of all relevant docs that appear in top-K.

    R@K = |{retrieved ∩ relevant}| / |relevant|

    Args:
        retrieved: Ranked list of retrieved doc IDs.
        relevant:  All relevant doc IDs.
        k:         Cutoff rank.

    Returns:
        Recall @K in [0.0, 1.0].
    """
    n_total = len(relevant)
    if n_total == 0:
        return 0.0
    top_k = list(retrieved[:k])
    n_relevant = sum(1 for d in top_k if relevant.get(d, 0.0) > 0)
    return n_relevant / n_total


def average_precision_at_k(
    retrieved: Sequence[str],
    relevant: dict[str, float],
    k: int,
) -> float:
    """
    Average Precision @K for a single query.

    AP@K = Σ P@i * rel_i / min(|relevant|, K)
    where rel_i = 1 if doc at rank i is relevant, else 0.

    AP penalizes gaps in the ranked list — relevant docs should appear early.

    Args:
        retrieved: Ranked list of retrieved doc IDs.
        relevant:  Relevant doc IDs with grades.
        k:         Cutoff rank.

    Returns:
        Average Precision @K in [0.0, 1.0].
    """
    n_relevant = min(len(relevant), k)
    if n_relevant == 0:
        return 0.0

    hits = 0.0
    ap = 0.0
    for rank, doc_id in enumerate(retrieved[:k], start=1):
        if relevant.get(doc_id, 0.0) > 0:
            hits += 1
            ap += hits / rank

    return ap / n_relevant


def hit_rate_at_k(
    retrieved: Sequence[str],
    relevant: dict[str, float],
    k: int,
) -> float:
    """
    Binary hit rate @K: 1.0 if any relevant doc in top-K, else 0.0.

    Useful for Q&A systems where a single relevant answer suffices.

    Args:
        retrieved: Ranked list.
        relevant:  Relevant doc IDs.
        k:         Cutoff.

    Returns:
        1.0 or 0.0.
    """
    return 1.0 if any(relevant.get(d, 0) > 0 for d in retrieved[:k]) else 0.0


# ─── All-in-one Evaluator ─────────────────────────────────────────────────────


def evaluate_retrieval(
    retrieved: Sequence[str],
    relevant: dict[str, float],
    query: str = "",
) -> EvalScore:
    """
    Compute all retrieval metrics for a single query.

    This is the main entry point used by EvalEngine, BEIRRunner, and tests.

    Args:
        retrieved: Ranked list of retrieved doc IDs (rank 1 = first).
        relevant:  Ground truth: {doc_id: relevance_grade}.
                   Use grade 1.0 for binary relevance.
                   Use grade 2.0 for highly relevant, 1.0 for partially relevant.
        query:     Optional query string for logging/display.

    Returns:
        EvalScore with all metric values pre-computed.

    Example:
        score = evaluate_retrieval(
            retrieved=["doc1", "doc3", "doc2", "doc5"],
            relevant={"doc1": 1.0, "doc5": 1.0},
        )
        print(score.ndcg_at_10)   # 0.874...
        print(score.mrr)          # 1.0 (doc1 is rank 1)
        print(score.precision_at_5) # 0.4 (2/5 relevant in top 5)
    """
    retrieved = list(retrieved)

    return EvalScore(
        ndcg_at_10=ndcg_at_k(retrieved, relevant, 10),
        ndcg_at_5=ndcg_at_k(retrieved, relevant, 5),
        ndcg_at_3=ndcg_at_k(retrieved, relevant, 3),
        ndcg_at_1=ndcg_at_k(retrieved, relevant, 1),
        mrr=reciprocal_rank(retrieved, relevant, 10),
        map_at_10=average_precision_at_k(retrieved, relevant, 10),
        precision_at_10=precision_at_k(retrieved, relevant, 10),
        precision_at_5=precision_at_k(retrieved, relevant, 5),
        precision_at_3=precision_at_k(retrieved, relevant, 3),
        precision_at_1=precision_at_k(retrieved, relevant, 1),
        recall_at_10=recall_at_k(retrieved, relevant, 10),
        recall_at_5=recall_at_k(retrieved, relevant, 5),
        hit_rate_at_10=hit_rate_at_k(retrieved, relevant, 10),
        query=query,
        retrieved_ids=retrieved,
        relevant_ids=list(relevant.keys()),
    )


def aggregate_scores(scores: list[EvalScore]) -> AggregatedEvalScore:
    """
    Macro-average EvalScores across a list of queries.

    Macro-average treats every query equally regardless of the number of
    relevant documents. This is the standard approach for BEIR evaluation.

    Args:
        scores: List of per-query EvalScore objects.

    Returns:
        AggregatedEvalScore with macro-averaged metrics.
    """
    if not scores:
        return AggregatedEvalScore()

    n = len(scores)

    def avg(attr: str) -> float:
        return sum(getattr(s, attr) for s in scores) / n

    return AggregatedEvalScore(
        ndcg_at_10=avg("ndcg_at_10"),
        ndcg_at_5=avg("ndcg_at_5"),
        ndcg_at_3=avg("ndcg_at_3"),
        mrr=avg("mrr"),
        map_at_10=avg("map_at_10"),
        precision_at_10=avg("precision_at_10"),
        recall_at_10=avg("recall_at_10"),
        hit_rate_at_10=avg("hit_rate_at_10"),
        query_count=n,
    )
