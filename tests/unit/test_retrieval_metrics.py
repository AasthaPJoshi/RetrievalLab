# =============================================================================
# RetrievalLab — tests/unit/test_retrieval_metrics.py
# =============================================================================
# PURPOSE : Unit tests for all retrieval evaluation metrics.
#           Verifies mathematical correctness using hand-computed examples
#           with known ground-truth values.
#
# WHAT WE TEST:
#   1. DCG and IDCG computation
#   2. NDCG@K — perfect ranking, worst ranking, partial relevance, K cutoffs
#   3. Reciprocal Rank — rank 1, rank 3, none found
#   4. Precision@K — standard cases and edge cases
#   5. Recall@K — standard cases
#   6. Average Precision@K
#   7. Hit Rate@K (binary)
#   8. evaluate_retrieval() all-in-one
#   9. aggregate_scores() macro-averaging
#
# RUN:
#   pytest tests/unit/test_retrieval_metrics.py -v
# =============================================================================

from __future__ import annotations

import math

from eval.metrics.retrieval_metrics import (
    AggregatedEvalScore,
    EvalScore,
    aggregate_scores,
    average_precision_at_k,
    dcg_at_k,
    evaluate_retrieval,
    hit_rate_at_k,
    idcg_at_k,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)

# ─── DCG / IDCG ───────────────────────────────────────────────────────────────

class TestDCG:
    def test_empty_retrieved(self):
        assert dcg_at_k([], {"a": 1.0}, k=10) == 0.0

    def test_single_relevant_at_rank1(self):
        # DCG = (2^1 - 1) / log2(2) = 1.0 / 1.0 = 1.0
        result = dcg_at_k(["a"], {"a": 1.0}, k=1)
        assert abs(result - 1.0) < 1e-6

    def test_single_relevant_at_rank2(self):
        # DCG = (2^1 - 1) / log2(3) ≈ 0.6309
        result = dcg_at_k(["x", "a"], {"a": 1.0}, k=2)
        expected = 1.0 / math.log2(3)
        assert abs(result - expected) < 1e-6

    def test_graded_relevance(self):
        # rank1: grade=2 → (2^2-1)/log2(2) = 3.0
        # rank2: grade=1 → (2^1-1)/log2(3) ≈ 0.631
        result = dcg_at_k(["a", "b"], {"a": 2.0, "b": 1.0}, k=2)
        expected = 3.0 + 1.0 / math.log2(3)
        assert abs(result - expected) < 1e-6

    def test_irrelevant_docs_not_counted(self):
        dcg_with    = dcg_at_k(["a", "x", "y"], {"a": 1.0}, k=3)
        dcg_without = dcg_at_k(["a"], {"a": 1.0}, k=1)
        assert abs(dcg_with - dcg_without) < 1e-6

    def test_k_cutoff_respected(self):
        # Doc "b" at rank 2 is relevant, but k=1 so shouldn't count
        result = dcg_at_k(["a", "b"], {"b": 1.0}, k=1)
        assert result == 0.0


class TestIDCG:
    def test_no_relevant_docs(self):
        assert idcg_at_k({}, k=10) == 0.0

    def test_one_relevant_doc(self):
        # IDCG@5 with one relevant doc = (2^1-1)/log2(2) = 1.0
        result = idcg_at_k({"a": 1.0}, k=5)
        assert abs(result - 1.0) < 1e-6

    def test_sorts_by_grade_descending(self):
        # 2 relevant docs, grades 2 and 1 — IDCG should place grade-2 first
        relevant = {"a": 1.0, "b": 2.0}
        result = idcg_at_k(relevant, k=5)
        # Ideal: rank1=grade2, rank2=grade1
        expected = 3.0 / math.log2(2) + 1.0 / math.log2(3)
        assert abs(result - expected) < 1e-6


# ─── NDCG@K ──────────────────────────────────────────────────────────────────

class TestNDCG:
    def test_perfect_ranking(self):
        """If retrieved order matches ideal order, NDCG = 1.0."""
        relevant  = {"doc1": 1.0, "doc2": 1.0}
        retrieved = ["doc1", "doc2", "doc3"]
        result    = ndcg_at_k(retrieved, relevant, k=10)
        assert abs(result - 1.0) < 1e-6

    def test_no_relevant_found(self):
        """If no relevant docs retrieved, NDCG = 0.0."""
        result = ndcg_at_k(["x", "y", "z"], {"a": 1.0}, k=10)
        assert result == 0.0

    def test_worst_ranking(self):
        """Relevant doc at last position should give very low NDCG."""
        # 10 docs, relevant doc is last
        retrieved = [f"x{i}" for i in range(9)] + ["rel"]
        result    = ndcg_at_k(retrieved, {"rel": 1.0}, k=10)
        # Not zero (doc is found at k=10), but very low
        assert 0.0 < result < 0.3

    def test_ndcg_bounded_0_to_1(self):
        """NDCG must always be in [0.0, 1.0]."""
        for retrieved, relevant in [
            ([], {}),
            (["a"], {}),
            (["a", "b"], {"a": 1.0}),
            (["x", "a"], {"a": 2.0, "b": 1.0}),
        ]:
            result = ndcg_at_k(retrieved, relevant, k=10)
            assert 0.0 <= result <= 1.0 + 1e-9

    def test_k_cutoff_matters(self):
        """NDCG@1 should be 0 if relevant doc is at rank 2."""
        retrieved = ["irrelevant", "relevant"]
        relevant  = {"relevant": 1.0}
        ndcg1 = ndcg_at_k(retrieved, relevant, k=1)
        ndcg2 = ndcg_at_k(retrieved, relevant, k=2)
        assert ndcg1 == 0.0
        assert ndcg2 > 0.0

    def test_empty_relevant_returns_zero(self):
        result = ndcg_at_k(["a", "b"], {}, k=10)
        assert result == 0.0


# ─── Reciprocal Rank ─────────────────────────────────────────────────────────

class TestReciprocalRank:
    def test_first_relevant_at_rank_1(self):
        result = reciprocal_rank(["a", "b", "c"], {"a": 1.0}, k=10)
        assert abs(result - 1.0) < 1e-6

    def test_first_relevant_at_rank_3(self):
        result = reciprocal_rank(["x", "y", "a"], {"a": 1.0}, k=10)
        assert abs(result - 1.0 / 3.0) < 1e-6

    def test_no_relevant_in_top_k(self):
        result = reciprocal_rank(["x", "y", "z"], {"a": 1.0}, k=3)
        assert result == 0.0

    def test_relevant_beyond_k_not_counted(self):
        # Relevant doc at rank 5, but k=3
        result = reciprocal_rank(["x", "y", "z", "w", "a"], {"a": 1.0}, k=3)
        assert result == 0.0

    def test_multiple_relevant_uses_first(self):
        # Both b and c are relevant — RR should use rank of first (rank 2)
        result = reciprocal_rank(["x", "b", "c"], {"b": 1.0, "c": 1.0}, k=10)
        assert abs(result - 0.5) < 1e-6


# ─── Precision@K ─────────────────────────────────────────────────────────────

class TestPrecisionAtK:
    def test_all_relevant(self):
        result = precision_at_k(["a", "b", "c"], {"a": 1.0, "b": 1.0, "c": 1.0}, k=3)
        assert abs(result - 1.0) < 1e-6

    def test_none_relevant(self):
        result = precision_at_k(["x", "y", "z"], {"a": 1.0}, k=3)
        assert result == 0.0

    def test_half_relevant(self):
        result = precision_at_k(["a", "x", "b", "y"], {"a": 1.0, "b": 1.0}, k=4)
        assert abs(result - 0.5) < 1e-6

    def test_k_1(self):
        result = precision_at_k(["a"], {"a": 1.0}, k=1)
        assert abs(result - 1.0) < 1e-6

    def test_k_zero_returns_zero(self):
        result = precision_at_k(["a"], {"a": 1.0}, k=0)
        assert result == 0.0


# ─── Recall@K ────────────────────────────────────────────────────────────────

class TestRecallAtK:
    def test_all_relevant_retrieved(self):
        result = recall_at_k(["a", "b"], {"a": 1.0, "b": 1.0}, k=2)
        assert abs(result - 1.0) < 1e-6

    def test_half_retrieved(self):
        result = recall_at_k(["a", "x"], {"a": 1.0, "b": 1.0}, k=2)
        assert abs(result - 0.5) < 1e-6

    def test_no_relevant_set(self):
        result = recall_at_k(["a", "b"], {}, k=10)
        assert result == 0.0

    def test_relevant_beyond_k_not_counted(self):
        # "b" is relevant but beyond k=1
        result = recall_at_k(["a", "b"], {"a": 1.0, "b": 1.0}, k=1)
        assert abs(result - 0.5) < 1e-6


# ─── Average Precision@K ─────────────────────────────────────────────────────

class TestAveragePrecision:
    def test_perfect_ranking(self):
        # Both relevant docs at ranks 1 and 2
        result = average_precision_at_k(["a", "b", "x"], {"a": 1.0, "b": 1.0}, k=3)
        # AP = (P@1 + P@2) / 2 = (1.0 + 1.0) / 2 = 1.0
        assert abs(result - 1.0) < 1e-6

    def test_interleaved_relevant(self):
        # Relevant at ranks 1 and 3 (out of 3)
        result = average_precision_at_k(["a", "x", "b"], {"a": 1.0, "b": 1.0}, k=3)
        # P@1 = 1/1 = 1.0, P@3 = 2/3 ≈ 0.667 → AP = (1.0 + 0.667) / 2 ≈ 0.833
        assert 0.8 < result < 0.9

    def test_no_relevant_returns_zero(self):
        result = average_precision_at_k(["x", "y"], {"a": 1.0}, k=5)
        assert result == 0.0


# ─── Hit Rate@K ──────────────────────────────────────────────────────────────

class TestHitRate:
    def test_hit_at_rank_1(self):
        result = hit_rate_at_k(["a", "x"], {"a": 1.0}, k=5)
        assert result == 1.0

    def test_miss(self):
        result = hit_rate_at_k(["x", "y"], {"a": 1.0}, k=2)
        assert result == 0.0

    def test_hit_at_boundary(self):
        result = hit_rate_at_k(["x", "x", "x", "x", "a"], {"a": 1.0}, k=5)
        assert result == 1.0

    def test_beyond_k_not_counted(self):
        result = hit_rate_at_k(["x", "x", "x", "x", "a"], {"a": 1.0}, k=4)
        assert result == 0.0


# ─── evaluate_retrieval() — all-in-one ───────────────────────────────────────

class TestEvaluateRetrieval:
    def test_returns_eval_score(self):
        score = evaluate_retrieval(["a", "b"], {"a": 1.0})
        assert isinstance(score, EvalScore)

    def test_perfect_result(self):
        score = evaluate_retrieval(["a", "b"], {"a": 1.0, "b": 1.0})
        assert abs(score.ndcg_at_10 - 1.0) < 1e-6
        assert abs(score.mrr - 1.0) < 1e-6
        assert abs(score.hit_rate_at_10 - 1.0) < 1e-6

    def test_empty_retrieved(self):
        score = evaluate_retrieval([], {"a": 1.0})
        assert score.ndcg_at_10 == 0.0
        assert score.mrr == 0.0

    def test_query_stored(self):
        score = evaluate_retrieval(["a"], {"a": 1.0}, query="test query")
        assert score.query == "test query"

    def test_to_dict_has_all_keys(self):
        score = evaluate_retrieval(["a"], {"a": 1.0})
        d     = score.to_dict()
        required_keys = {
            "ndcg@10", "ndcg@5", "ndcg@3", "ndcg@1",
            "mrr", "map@10", "precision@10", "precision@5",
            "recall@10", "hit_rate@10",
        }
        for key in required_keys:
            assert key in d, f"Missing key: {key}"

    def test_retrieved_ids_stored(self):
        retrieved = ["x", "y", "z"]
        score     = evaluate_retrieval(retrieved, {"x": 1.0})
        assert score.retrieved_ids == retrieved


# ─── aggregate_scores() ──────────────────────────────────────────────────────

class TestAggregateScores:
    def test_empty_list(self):
        result = aggregate_scores([])
        assert result.query_count == 0
        assert result.ndcg_at_10 == 0.0

    def test_single_score(self):
        score  = evaluate_retrieval(["a", "b"], {"a": 1.0})
        result = aggregate_scores([score])
        assert result.query_count == 1
        assert abs(result.ndcg_at_10 - score.ndcg_at_10) < 1e-6

    def test_macro_average(self):
        """Average should be arithmetic mean of individual scores."""
        scores = [
            EvalScore(ndcg_at_10=0.8, mrr=0.9, map_at_10=0.7,
                      ndcg_at_5=0.8, ndcg_at_3=0.8,
                      precision_at_10=0.6, recall_at_10=0.5, hit_rate_at_10=1.0),
            EvalScore(ndcg_at_10=0.6, mrr=0.7, map_at_10=0.5,
                      ndcg_at_5=0.6, ndcg_at_3=0.6,
                      precision_at_10=0.4, recall_at_10=0.3, hit_rate_at_10=0.0),
        ]
        result = aggregate_scores(scores)
        assert abs(result.ndcg_at_10 - 0.7) < 1e-6
        assert abs(result.mrr - 0.8) < 1e-6
        assert result.query_count == 2

    def test_returns_aggregated_eval_score(self):
        scores = [evaluate_retrieval(["a"], {"a": 1.0})]
        result = aggregate_scores(scores)
        assert isinstance(result, AggregatedEvalScore)

    def test_to_dict_returns_floats(self):
        scores = [evaluate_retrieval(["a"], {"a": 1.0})]
        result = aggregate_scores(scores)
        d      = result.to_dict()
        for k, v in d.items():
            assert isinstance(v, (int, float)), f"{k} should be numeric"
