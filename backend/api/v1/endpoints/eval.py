# =============================================================================
# RetrievalLab — backend/api/v1/endpoints/eval.py
# =============================================================================
# PURPOSE : FastAPI router for evaluation endpoints.
#           Accepts retrieved results + ground truth and returns standard
#           IR metrics (NDCG@K, MRR, MAP) and Ragas RAG-quality scores.
#
# ENDPOINTS:
#   POST /api/v1/eval/score           → compute NDCG/MRR/MAP for a result set
#   POST /api/v1/eval/ragas           → run Ragas pipeline evaluation
#   POST /api/v1/eval/adversarial     → run all 6 adversarial attacks
#   GET  /api/v1/eval/experiments     → list MLflow experiments
#
# DESIGN:
#   Eval endpoints are stateless — they don't store anything by default.
#   Pass log_to_mlflow=true in the request to persist results to MLflow.
#
# INPUT  : Retrieved chunk IDs + ground truth relevant doc IDs (with grades)
# OUTPUT : EvalScore or RagasResult as JSON
# =============================================================================

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from eval.metrics.retrieval_metrics import (
    EvalScore,
    aggregate_scores,
    evaluate_retrieval,
)

logger = structlog.get_logger(__name__)
router = APIRouter()


# ─── Schemas ──────────────────────────────────────────────────────────────────


class ScoreRequest(BaseModel):
    """Request for computing retrieval metrics."""

    retrieved_ids: list[str] = Field(
        ...,
        description="Ordered list of retrieved chunk/doc IDs (rank 1 = first)",
        examples=[["chunk_a", "chunk_b", "chunk_c"]],
    )
    relevant_ids: dict[str, float] = Field(
        ...,
        description="Ground truth: {doc_id: relevance_grade}. Use 1.0 for binary relevance.",
        examples=[{"chunk_a": 1.0, "chunk_d": 1.0}],
    )
    query: str = Field(default="", description="Query text for logging")


class BatchScoreRequest(BaseModel):
    """Request for computing averaged metrics over multiple queries."""

    queries: list[ScoreRequest]
    experiment_name: str = Field(default="", description="MLflow experiment name")
    log_to_mlflow: bool = Field(default=False)


class RagasRequest(BaseModel):
    """Request for Ragas RAG pipeline evaluation."""

    questions: list[str] = Field(..., description="Query strings")
    answers: list[str] = Field(..., description="LLM-generated answers")
    contexts: list[list[str]] = Field(..., description="Retrieved context chunks per question")
    ground_truths: list[str] | None = Field(
        default=None, description="Expected answers (for context_recall)"
    )
    model: str = Field(default="gpt-4o-mini", description="LLM judge model")
    log_to_mlflow: bool = Field(default=False)
    experiment_name: str = Field(default="ragas_eval")


# ─── Endpoints ────────────────────────────────────────────────────────────────


@router.post(
    "/score",
    response_model=dict,
    summary="Compute retrieval metrics for a single query",
    description="Compute NDCG@K, MRR, MAP@K, Precision@K for one query's retrieved results.",
)
async def score_retrieval(body: ScoreRequest) -> dict[str, Any]:
    """
    Compute standard IR metrics for one query.

    Returns all metrics as a flat dict for easy consumption.

    Example request:
        POST /api/v1/eval/score
        {
            "retrieved_ids": ["chunk_1", "chunk_4", "chunk_2"],
            "relevant_ids":  {"chunk_1": 1.0, "chunk_3": 1.0},
            "query":         "cardiac arrest treatment"
        }
    """
    score = evaluate_retrieval(
        retrieved=body.retrieved_ids,
        relevant=body.relevant_ids,
        query=body.query,
    )
    return {
        "query": score.query,
        "metrics": score.to_dict(),
    }


@router.post(
    "/score/batch",
    response_model=dict,
    summary="Compute averaged metrics across multiple queries",
    description=(
        "Evaluate a full query set and return macro-averaged NDCG@10, MRR, MAP@10. "
        "Pass log_to_mlflow=true to persist results to the MLflow experiment tracker."
    ),
)
async def batch_score(body: BatchScoreRequest) -> dict[str, Any]:
    """
    Compute and aggregate retrieval metrics across many queries.

    Optionally logs results to MLflow for experiment tracking.
    """
    per_query_scores: list[EvalScore] = []

    for q in body.queries:
        score = evaluate_retrieval(
            retrieved=q.retrieved_ids,
            relevant=q.relevant_ids,
            query=q.query,
        )
        per_query_scores.append(score)

    agg = aggregate_scores(per_query_scores)

    # Optional MLflow logging
    if body.log_to_mlflow and body.experiment_name:
        await _log_to_mlflow(body.experiment_name, agg.to_dict())

    return {
        "query_count": agg.query_count,
        "aggregated": agg.to_dict(),
        "per_query_count": len(per_query_scores),
        "logged_to_mlflow": body.log_to_mlflow,
    }


@router.post(
    "/ragas",
    response_model=dict,
    summary="Run Ragas RAG pipeline evaluation",
    description=(
        "Evaluate the full RAG pipeline quality using Ragas metrics: "
        "context_precision, context_recall, faithfulness, answer_relevance. "
        "Requires an LLM API key (ANTHROPIC_API_KEY or OPENAI_API_KEY)."
    ),
)
async def ragas_eval(body: RagasRequest) -> dict[str, Any]:
    """
    Run Ragas evaluation on a set of question-answer-context triples.

    This calls an LLM API internally — estimated cost: ~$0.02 per question.
    """
    from eval.metrics.ragas_evaluator import RagasEvaluator

    if len(body.questions) != len(body.answers) or len(body.questions) != len(body.contexts):
        raise HTTPException(
            status_code=400,
            detail="questions, answers, and contexts must have the same length",
        )

    evaluator = RagasEvaluator(model=body.model)
    result = await evaluator.evaluate(
        questions=body.questions,
        answers=body.answers,
        contexts=body.contexts,
        ground_truths=body.ground_truths,
    )

    if result.error:
        raise HTTPException(status_code=500, detail=f"Ragas evaluation failed: {result.error}")

    output = {
        "question_count": result.question_count,
        "duration_s": result.duration_s,
        "model_used": result.model_used,
        "aggregated_scores": result.to_dict(),
    }

    if body.log_to_mlflow and body.experiment_name:
        await _log_to_mlflow(body.experiment_name, result.to_dict())
        output["logged_to_mlflow"] = True

    return output


@router.get(
    "/metrics",
    summary="List available evaluation metrics",
    description="Returns metadata about all supported evaluation metrics.",
)
async def list_metrics() -> dict[str, Any]:
    """Return descriptions of all available evaluation metrics."""
    return {
        "retrieval_metrics": [
            {
                "name": "ndcg@10",
                "description": "Normalized DCG @ rank 10 (primary metric)",
                "range": "[0, 1]",
            },
            {"name": "ndcg@5", "description": "Normalized DCG @ rank 5", "range": "[0, 1]"},
            {"name": "mrr", "description": "Mean Reciprocal Rank", "range": "(0, 1]"},
            {"name": "map@10", "description": "Mean Average Precision @ 10", "range": "[0, 1]"},
            {"name": "precision@10", "description": "Precision @ rank 10", "range": "[0, 1]"},
            {"name": "recall@10", "description": "Recall @ rank 10", "range": "[0, 1]"},
            {
                "name": "hit_rate@10",
                "description": "Any relevant in top-10 (binary)",
                "range": "{0, 1}",
            },
        ],
        "rag_metrics": [
            {
                "name": "context_precision",
                "description": "Fraction of retrieved context that is relevant",
            },
            {
                "name": "context_recall",
                "description": "Fraction of ground truth covered by context",
            },
            {
                "name": "faithfulness",
                "description": "Answer grounded in retrieved context (0=hallucination)",
            },
            {"name": "answer_relevance", "description": "Answer addresses the question directly"},
        ],
    }


# ─── Internal Helper ──────────────────────────────────────────────────────────


async def _log_to_mlflow(experiment_name: str, metrics: dict[str, float]) -> None:
    """Log metrics to MLflow. Non-blocking — failures are logged but don't raise."""
    try:
        import mlflow
        from config.settings import get_settings

        s = get_settings()
        mlflow.set_tracking_uri(s.mlflow.tracking_uri)
        mlflow.set_experiment(experiment_name)
        with mlflow.start_run():
            mlflow.log_metrics({k: v for k, v in metrics.items() if isinstance(v, (int, float))})
    except Exception as exc:
        logger.warning("mlflow_log_failed", error=str(exc))
