# =============================================================================
# RetrievalLab — eval/metrics/ragas_evaluator.py
# =============================================================================
# PURPOSE : RAG-specific evaluation using the Ragas framework.
#           Ragas measures the quality of the full RAG pipeline (not just
#           retrieval) by evaluating context precision, recall, faithfulness,
#           and answer relevance using an LLM-as-judge approach.
#
# RAGAS METRICS:
#   context_precision:    Are the retrieved chunks relevant to the question?
#   context_recall:       Do the retrieved chunks cover all expected answers?
#   faithfulness:         Is the LLM answer grounded in retrieved context?
#   answer_relevance:     Is the answer relevant to the original question?
#   context_entity_recall: Are key entities from ground truth in retrieved context?
#
# WHY RAGAS OVER TRADITIONAL METRICS:
#   Traditional IR metrics (NDCG, MRR) measure retrieval only.
#   Ragas measures the full pipeline: retrieval quality + generation quality.
#   This catches cases where retrieval is good but generation is hallucinating.
#
# SETUP REQUIREMENTS:
#   OPENAI_API_KEY or ANTHROPIC_API_KEY in .env
#   (Ragas uses an LLM judge to evaluate faithfulness and answer relevance)
#
# HOW TO USE:
#   evaluator = RagasEvaluator(model="claude-3-5-haiku-20241022")
#   results = await evaluator.evaluate(
#       questions=["What is RAG?"],
#       answers=["RAG stands for Retrieval-Augmented Generation..."],
#       contexts=[["Context chunk 1...", "Context chunk 2..."]],
#       ground_truths=["RAG combines retrieval with generation."],
#   )
#   print(results.faithfulness)    # 0.92
#   print(results.context_recall)  # 0.87
#
# INPUT  : Questions, LLM answers, retrieved contexts, ground truth answers
# OUTPUT : RagasResult with metric scores per question and aggregated
#
# AFTER THIS FILE:
#   Results logged to → MLflow experiment tracker (mlflow_tracker.py)
#   Displayed in → React dashboard (Day 5)
# =============================================================================

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


# ─── Result Data Classes ──────────────────────────────────────────────────────

@dataclass
class RagasQuestionResult:
    """Ragas metrics for a single question."""

    question:          str
    answer:            str
    context_precision: float = 0.0
    context_recall:    float = 0.0
    faithfulness:      float = 0.0
    answer_relevance:  float = 0.0
    error:             str | None = None


@dataclass
class RagasResult:
    """
    Aggregated Ragas evaluation results for a set of questions.

    All scores are in [0.0, 1.0] — higher is better.
    None values indicate the metric could not be computed (e.g., no API key).
    """

    context_precision: float | None    = None
    context_recall:    float | None    = None
    faithfulness:      float | None    = None
    answer_relevance:  float | None    = None
    question_results:  list[RagasQuestionResult] = field(default_factory=list)
    question_count:    int             = 0
    duration_s:        float           = 0.0
    model_used:        str             = ""
    error:             str | None      = None

    def to_dict(self) -> dict[str, float]:
        """Return scalar metrics as flat dict (for MLflow logging)."""
        out = {}
        for key in ("context_precision", "context_recall", "faithfulness", "answer_relevance"):
            val = getattr(self, key)
            if val is not None:
                out[f"ragas_{key}"] = val
        out["ragas_question_count"] = float(self.question_count)
        return out


# ─── RagasEvaluator ──────────────────────────────────────────────────────────

class RagasEvaluator:
    """
    RAG pipeline evaluator using the Ragas framework.

    Wraps ragas.evaluate() with async support, error handling,
    MLflow logging, and fallback to manual metric computation.

    Args:
        model:      LLM to use as judge (Ragas calls this for faithfulness/relevance).
                    Accepts OpenAI or Anthropic model names.
        metrics:    List of metric names to compute. Default: all 4.
        use_openai: If True, use OpenAI LLM. Else, try Anthropic. Default: auto-detect.

    Example:
        evaluator = RagasEvaluator(model="claude-3-5-haiku-20241022")
        result = await evaluator.evaluate(
            questions=["What is BM25?"],
            answers=["BM25 is a ranking function..."],
            contexts=[["BM25 is a bag-of-words retrieval function..."]],
            ground_truths=["BM25 is a probabilistic ranking function based on TF-IDF."],
        )
    """

    DEFAULT_METRICS = [
        "context_precision",
        "context_recall",
        "faithfulness",
        "answer_relevance",
    ]

    def __init__(
        self,
        model:      str = "gpt-4o-mini",
        metrics:    list[str] | None = None,
        use_openai: bool | None = None,
    ) -> None:
        self.model      = model
        self.metrics    = metrics or self.DEFAULT_METRICS
        self.use_openai = use_openai  # None = auto-detect from API keys

    async def evaluate(
        self,
        questions:    list[str],
        answers:      list[str],
        contexts:     list[list[str]],
        ground_truths: list[str] | None = None,
    ) -> RagasResult:
        """
        Run Ragas evaluation on a set of question-answer-context triples.

        Args:
            questions:    List of query strings.
            answers:      List of LLM-generated answers (one per question).
            contexts:     List of context lists (retrieved chunks per question).
            ground_truths: List of expected answers (needed for context_recall).
                           If None, context_recall is not computed.

        Returns:
            RagasResult with per-question and aggregated scores.

        Note:
            This calls an LLM API for faithfulness and answer_relevance metrics.
            Estimated cost: ~$0.02 per question (OpenAI GPT-4o-mini) or free (local).
        """
        start = time.perf_counter()

        if not questions:
            return RagasResult(error="No questions provided", duration_s=0.0)

        logger.info(
            "ragas_eval_started",
            question_count=len(questions),
            metrics=self.metrics,
            model=self.model,
        )

        try:
            result = await self._run_ragas(questions, answers, contexts, ground_truths)
            result.duration_s    = time.perf_counter() - start
            result.question_count = len(questions)
            result.model_used    = self.model

            logger.info(
                "ragas_eval_complete",
                faithfulness=result.faithfulness,
                context_recall=result.context_recall,
                duration_s=round(result.duration_s, 2),
            )
            return result

        except Exception as exc:
            logger.error("ragas_eval_failed", error=str(exc))
            return RagasResult(
                error=str(exc),
                duration_s=time.perf_counter() - start,
                question_count=len(questions),
            )

    async def _run_ragas(
        self,
        questions:    list[str],
        answers:      list[str],
        contexts:     list[list[str]],
        ground_truths: list[str] | None,
    ) -> RagasResult:
        """
        Execute Ragas evaluation using the ragas library.

        Builds a Ragas Dataset, selects metrics, calls ragas.evaluate(),
        and parses scores into RagasResult.
        """
        try:
            from datasets import Dataset as HFDataset
            import ragas
            from ragas import evaluate as ragas_evaluate
            from ragas.metrics import (
                context_precision,
                context_recall,
                faithfulness,
                answer_relevance,
            )
        except ImportError as e:
            raise ImportError(
                f"Ragas dependencies missing: {e}. "
                "Install with: pip install ragas datasets"
            )

        # Build HuggingFace Dataset for Ragas
        data_dict: dict[str, list] = {
            "question":  questions,
            "answer":    answers,
            "contexts":  contexts,
        }
        if ground_truths:
            data_dict["ground_truth"] = ground_truths

        dataset = HFDataset.from_dict(data_dict)

        # Select metrics based on config
        metric_map = {
            "context_precision": context_precision,
            "context_recall":    context_recall,
            "faithfulness":      faithfulness,
            "answer_relevance":  answer_relevance,
        }
        # context_recall requires ground_truth
        active_metrics = []
        for m_name in self.metrics:
            if m_name == "context_recall" and not ground_truths:
                continue
            if m_name in metric_map:
                active_metrics.append(metric_map[m_name])

        # Configure LLM judge
        llm = self._get_ragas_llm()

        # Run evaluation (Ragas calls LLM internally)
        ragas_result = ragas_evaluate(
            dataset,
            metrics=active_metrics,
            llm=llm,
            raise_exceptions=False,
        )

        # Parse results
        scores_df = ragas_result.to_pandas()

        def _safe_mean(col: str) -> float | None:
            if col not in scores_df.columns:
                return None
            return float(scores_df[col].dropna().mean())

        # Build per-question results
        question_results = []
        for i, q in enumerate(questions):
            qr = RagasQuestionResult(
                question          = q,
                answer            = answers[i],
                context_precision = float(scores_df.get("context_precision", [0])[i]) if "context_precision" in scores_df else 0.0,
                context_recall    = float(scores_df.get("context_recall",    [0])[i]) if "context_recall"    in scores_df else 0.0,
                faithfulness      = float(scores_df.get("faithfulness",       [0])[i]) if "faithfulness"       in scores_df else 0.0,
                answer_relevance  = float(scores_df.get("answer_relevance",  [0])[i]) if "answer_relevance"  in scores_df else 0.0,
            )
            question_results.append(qr)

        return RagasResult(
            context_precision = _safe_mean("context_precision"),
            context_recall    = _safe_mean("context_recall"),
            faithfulness      = _safe_mean("faithfulness"),
            answer_relevance  = _safe_mean("answer_relevance"),
            question_results  = question_results,
        )

    def _get_ragas_llm(self):
        """Return a Ragas-compatible LLM instance based on available API keys."""
        from config.settings import get_settings
        s = get_settings()

        # Try Anthropic first if model name suggests it
        if "claude" in self.model.lower() and s.llm.anthropic_api_key:
            try:
                from langchain_anthropic import ChatAnthropic
                return ChatAnthropic(
                    model=self.model,
                    api_key=s.llm.anthropic_api_key.get_secret_value(),
                )
            except ImportError:
                pass

        # Fall back to OpenAI
        if s.llm.openai_api_key:
            try:
                from langchain_openai import ChatOpenAI
                return ChatOpenAI(
                    model="gpt-4o-mini",
                    api_key=s.llm.openai_api_key.get_secret_value(),
                )
            except ImportError:
                pass

        raise RuntimeError(
            "No LLM API key found. Set ANTHROPIC_API_KEY or OPENAI_API_KEY in .env"
        )
