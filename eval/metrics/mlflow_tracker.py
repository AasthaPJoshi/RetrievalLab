# =============================================================================
# RetrievalLab — eval/metrics/mlflow_tracker.py
# =============================================================================
# PURPOSE : Centralizes all MLflow experiment tracking for RetrievalLab.
#           Every evaluation run (BEIR, Ragas, adversarial, custom) logs
#           through this module so results are consistently structured.
#
# WHAT IT DOES:
#   • Creates/reuses MLflow experiments by name
#   • Logs retrieval metrics (NDCG@K, MRR, MAP) as MLflow metrics
#   • Logs run configuration (model, strategy, corpus) as MLflow params
#   • Saves per-query scores as a JSON artifact for drill-down analysis
#   • Saves adversarial reports as text artifacts
#   • Provides a leaderboard query across all runs for a corpus
#
# MLflow UI: http://localhost:5000 (after `make up`)
#
# HOW TO USE:
#   tracker = MLflowTracker(experiment_name="healthcare_eval_v1")
#   with tracker.start_run(run_name="hybrid_512chunk") as run:
#       tracker.log_config({"mode": "hybrid", "chunk_size": 512})
#       tracker.log_retrieval_scores(aggregated_scores)
#       tracker.log_ragas_result(ragas_result)
#
# INPUT  : AggregatedEvalScore, RagasResult, AdversarialReport objects
# OUTPUT : MLflow run with logged metrics, params, and artifacts
#
# AFTER THIS FILE:
#   Results visible in → MLflow UI (http://localhost:5000)
#   Queried by → leaderboard API endpoint
# =============================================================================

from __future__ import annotations

import json
import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class MLflowTracker:
    """
    Wrapper around MLflow for structured experiment tracking in RetrievalLab.

    Ensures consistent metric naming and artifact structure across all
    evaluation types (BEIR, Ragas, adversarial, custom).

    Args:
        experiment_name: MLflow experiment to log to (created if not exists).
        tracking_uri:    MLflow server URL. Default: from settings.

    Example:
        tracker = MLflowTracker("healthcare_pubmed_v1_eval")

        with tracker.start_run("hybrid_bge_m3") as run_id:
            tracker.log_config({
                "corpus_id":    "healthcare_pubmed_v1",
                "retriever":    "hybrid",
                "embed_model":  "BAAI/bge-m3",
                "chunk_size":   512,
                "chunk_strategy": "sentence_window",
            })
            tracker.log_retrieval_scores(agg_scores)
            tracker.log_ragas_result(ragas_result)
            tracker.log_adversarial_report(adv_report)

        print(f"Run logged: {run_id}")
    """

    # Canonical metric names — never change these once experiments are running
    # (changing names breaks cross-run comparison in MLflow UI)
    METRIC_PREFIX_RETRIEVAL = "ret"
    METRIC_PREFIX_RAGAS = "ragas"
    METRIC_PREFIX_ADVERSARIAL = "adv"

    def __init__(
        self,
        experiment_name: str | None = None,
        tracking_uri: str | None = None,
    ) -> None:
        self.experiment_name = experiment_name
        self._tracking_uri = tracking_uri
        self._active_run = None

    def _setup_mlflow(self) -> None:
        """Initialize MLflow connection. Called lazily on first use."""
        try:
            import mlflow
            from config.settings import get_settings

            uri = self._tracking_uri or get_settings().mlflow.tracking_uri
            mlflow.set_tracking_uri(uri)

            exp_name = self.experiment_name or get_settings().mlflow.experiment_name
            mlflow.set_experiment(exp_name)
        except ImportError:
            raise ImportError("mlflow required: pip install mlflow")
        except Exception as exc:
            logger.warning("mlflow_setup_failed", error=str(exc))
            raise

    @contextmanager
    def start_run(
        self,
        run_name: str | None = None,
        tags: dict[str, str] | None = None,
    ) -> Generator[str, None, None]:
        """
        Context manager that starts an MLflow run and returns the run ID.

        All log_*() calls within the context are associated with this run.
        The run is automatically ended when the context exits (even on error).

        Args:
            run_name: Human-readable run name shown in MLflow UI.
            tags:     Key-value string tags for the run.

        Yields:
            MLflow run ID (UUID string).

        Example:
            with tracker.start_run("hybrid_512_run1") as run_id:
                tracker.log_config({"mode": "hybrid"})
                tracker.log_retrieval_scores(scores)
        """
        import mlflow

        self._setup_mlflow()

        with mlflow.start_run(run_name=run_name, tags=tags or {}) as run:
            self._active_run = run
            logger.info(
                "mlflow_run_started",
                run_id=run.info.run_id,
                run_name=run_name,
            )
            try:
                yield run.info.run_id
            finally:
                self._active_run = None
                logger.info("mlflow_run_ended", run_id=run.info.run_id)

    def log_config(self, config: dict[str, Any]) -> None:
        """
        Log experiment configuration as MLflow params.

        MLflow params are string key-value pairs that describe the experiment
        setup (not metrics). They appear in the Parameters tab in the UI.

        Args:
            config: Dict of configuration key-value pairs.
                    Values are coerced to strings automatically.

        Example:
            tracker.log_config({
                "corpus_id":     "healthcare_pubmed_v1",
                "retriever":     "hybrid",
                "embed_model":   "text-embedding-3-small",
                "chunk_size":    512,
                "chunk_strategy": "sentence_window",
                "top_k":         10,
            })
        """
        import mlflow

        # MLflow params must be strings and ≤ 500 chars
        str_params = {str(k): str(v)[:500] for k, v in config.items()}
        mlflow.log_params(str_params)

    def log_retrieval_scores(self, scores: AggregatedEvalScore) -> None:
        """
        Log aggregated retrieval metrics as MLflow metrics.

        Metric names follow the format: ret_{metric_name}
        e.g., ret_ndcg_at_10, ret_mrr, ret_map_at_10

        Args:
            scores: AggregatedEvalScore from aggregate_scores().
        """
        import mlflow

        metrics = {
            f"{self.METRIC_PREFIX_RETRIEVAL}_ndcg_at_10": scores.ndcg_at_10,
            f"{self.METRIC_PREFIX_RETRIEVAL}_ndcg_at_5": scores.ndcg_at_5,
            f"{self.METRIC_PREFIX_RETRIEVAL}_ndcg_at_3": scores.ndcg_at_3,
            f"{self.METRIC_PREFIX_RETRIEVAL}_mrr": scores.mrr,
            f"{self.METRIC_PREFIX_RETRIEVAL}_map_at_10": scores.map_at_10,
            f"{self.METRIC_PREFIX_RETRIEVAL}_precision_at_10": scores.precision_at_10,
            f"{self.METRIC_PREFIX_RETRIEVAL}_recall_at_10": scores.recall_at_10,
            f"{self.METRIC_PREFIX_RETRIEVAL}_hit_rate_at_10": scores.hit_rate_at_10,
            f"{self.METRIC_PREFIX_RETRIEVAL}_query_count": float(scores.query_count),
        }
        mlflow.log_metrics(metrics)
        logger.debug("mlflow_retrieval_scores_logged", ndcg=scores.ndcg_at_10)

    def log_ragas_result(self, result: RagasResult) -> None:
        """
        Log Ragas RAG-quality metrics as MLflow metrics.

        Metric names: ragas_faithfulness, ragas_context_precision, etc.

        Args:
            result: RagasResult from RagasEvaluator.evaluate().
        """
        import mlflow

        metrics: dict[str, float] = {}

        for attr in ("faithfulness", "context_precision", "context_recall", "answer_relevance"):
            val = getattr(result, attr, None)
            if val is not None:
                metrics[f"{self.METRIC_PREFIX_RAGAS}_{attr}"] = val

        if metrics:
            mlflow.log_metrics(metrics)
            logger.debug("mlflow_ragas_scores_logged", metrics=list(metrics.keys()))

    def log_adversarial_report(self, report: AdversarialReport) -> None:
        """
        Log adversarial robustness metrics and save full report as artifact.

        Logs summary metrics and saves the full report text + JSON for each attack.

        Args:
            report: AdversarialReport from AdversarialHarness.run_all().
        """
        import mlflow

        # Log aggregated metrics
        metrics = {
            f"{self.METRIC_PREFIX_ADVERSARIAL}_overall_robustness": report.overall_robustness,
        }
        for ar in report.attack_results:
            prefix = f"{self.METRIC_PREFIX_ADVERSARIAL}_{ar.attack_name}"
            metrics[f"{prefix}_ndcg"] = ar.attacked_ndcg
            metrics[f"{prefix}_degradation_pct"] = ar.degradation_pct

        mlflow.log_metrics(metrics)

        # Save full report as text artifact
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(report.summary())
            tmp_path = f.name
        mlflow.log_artifact(tmp_path, artifact_path="adversarial")

        # Save JSON for programmatic parsing
        report_json = {
            "corpus_id": report.corpus_id,
            "overall_robustness": report.overall_robustness,
            "duration_s": report.duration_s,
            "attacks": [
                {
                    "name": ar.attack_name,
                    "baseline_ndcg": ar.baseline_ndcg,
                    "attacked_ndcg": ar.attacked_ndcg,
                    "degradation": ar.degradation,
                    "degradation_pct": ar.degradation_pct,
                    "is_robust": ar.is_robust,
                }
                for ar in report.attack_results
            ],
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(report_json, f, indent=2)
            tmp_json_path = f.name
        mlflow.log_artifact(tmp_json_path, artifact_path="adversarial")

    def log_per_query_scores(
        self,
        per_query_scores: list[EvalScore],
        filename: str = "per_query_scores.json",
    ) -> None:
        """
        Save per-query scores as a JSON artifact for drill-down analysis.

        Args:
            per_query_scores: List of EvalScore objects, one per query.
            filename:         Artifact filename in MLflow.
        """
        import mlflow

        data = [
            {
                "query": s.query,
                "ndcg_at_10": s.ndcg_at_10,
                "mrr": s.mrr,
                "map_at_10": s.map_at_10,
                "hit_rate@10": s.hit_rate_at_10,
                "retrieved_ids": s.retrieved_ids[:5],  # first 5 for preview
            }
            for s in per_query_scores
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f, indent=2)
            tmp_path = f.name

        mlflow.log_artifact(tmp_path, artifact_path="scores")
        logger.debug("mlflow_per_query_scores_logged", count=len(per_query_scores))

    def get_leaderboard(
        self,
        corpus_id: str | None = None,
        metric: str = "ret_ndcg_at_10",
        top_n: int = 20,
    ) -> list[dict[str, Any]]:
        """
        Query MLflow for the top-N runs by a specified metric.

        Returns a leaderboard sorted by metric (descending).

        Args:
            corpus_id: Filter to runs with this corpus_id param. None = all corpora.
            metric:    MLflow metric name to rank by. Default: ret_ndcg_at_10.
            top_n:     Number of runs to return.

        Returns:
            List of dicts with run_id, run_name, metrics, params, sorted by metric.

        Example:
            leaderboard = tracker.get_leaderboard(corpus_id="healthcare_v1")
            for rank, run in enumerate(leaderboard, 1):
                print(f"{rank}. {run['run_name']} — NDCG@10: {run['metrics'].get('ret_ndcg_at_10'):.4f}")
        """
        import mlflow

        self._setup_mlflow()

        filter_str = f"metrics.{metric} > 0"
        if corpus_id:
            filter_str += f" and params.corpus_id = '{corpus_id}'"

        runs = mlflow.search_runs(
            filter_string=filter_str,
            order_by=[f"metrics.{metric} DESC"],
            max_results=top_n,
        )

        leaderboard = []
        for _, row in runs.iterrows():
            leaderboard.append(
                {
                    "run_id": row["run_id"],
                    "run_name": row.get("tags.mlflow.runName", ""),
                    "metrics": {
                        col.replace("metrics.", ""): row[col]
                        for col in runs.columns
                        if col.startswith("metrics.") and row[col] == row[col]  # not NaN
                    },
                    "params": {
                        col.replace("params.", ""): row[col]
                        for col in runs.columns
                        if col.startswith("params.")
                    },
                }
            )

        return leaderboard
