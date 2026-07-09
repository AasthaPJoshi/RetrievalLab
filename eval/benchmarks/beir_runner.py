# =============================================================================
# RetrievalLab — eval/benchmarks/beir_runner.py
# =============================================================================
# PURPOSE : Runs standard BEIR (Benchmarking Information Retrieval) evaluation
#           suite on RetrievalLab's retrieval system.
#
# WHAT IS BEIR?
#   BEIR (Thakur et al., 2021) is a heterogeneous benchmark of 18 IR datasets
#   covering biomedical, financial, legal, scientific, and general web domains.
#   It is the de facto standard for zero-shot dense retrieval evaluation.
#
# DATASETS SUPPORTED (subset of BEIR):
#   trec-covid       — Biomedical COVID-19 literature retrieval
#   nfcorpus         — Medical/nutrition information retrieval
#   fiqa             — Financial question answering
#   scifact          — Scientific claim verification
#   arguana          — Counter-argument retrieval
#   msmarco          — MS MARCO passage retrieval
#
# HOW IT WORKS:
#   1. Download BEIR dataset (if not cached)
#   2. Ingest corpus into RetrievalLab
#   3. Embed corpus using EmbedHub
#   4. Build index using IndexRegistry
#   5. Run all queries → retrieve top-100 results
#   6. Compute NDCG@10, MRR, MAP@10 against BEIR qrels
#   7. Log results to MLflow
#
# HOW TO USE:
#   runner = BEIRRunner(retriever=retriever, embed_hub=hub)
#   results = await runner.run("nfcorpus", top_k=100)
#   print(results.ndcg_at_10)  # Compare against published numbers
#
# PUBLISHED BASELINES (for comparison):
#   BM25:    nfcorpus=0.325, fiqa=0.236, trec-covid=0.656
#   DPR:     nfcorpus=0.189, fiqa=0.297, trec-covid=0.332
#   Hybrid:  typically 5-10% above BM25 or DPR alone
#
# INPUT  : BEIR dataset name + retrieval configuration
# OUTPUT : AggregatedEvalScore + per-query scores → MLflow artifact
#
# AFTER THIS FILE:
#   Results compared with → leaderboard table in React dashboard (Day 5)
# =============================================================================

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog

from eval.metrics.retrieval_metrics import (
    AggregatedEvalScore,
    EvalScore,
    aggregate_scores,
    evaluate_retrieval,
)

logger = structlog.get_logger(__name__)


# ─── BEIR Dataset Config ──────────────────────────────────────────────────────

BEIR_DATASETS = {
    "trec-covid": {
        "description": "COVID-19 biomedical literature retrieval",
        "domain": "healthcare",
        "size": "171k docs, 50 queries",
        "metric": "NDCG@10",
        "bm25_baseline": 0.656,
    },
    "nfcorpus": {
        "description": "Medical/nutrition information retrieval",
        "domain": "healthcare",
        "size": "3.6k docs, 323 queries",
        "metric": "NDCG@10",
        "bm25_baseline": 0.325,
    },
    "fiqa": {
        "description": "Financial opinion question answering",
        "domain": "finance",
        "size": "57k docs, 648 queries",
        "metric": "NDCG@10",
        "bm25_baseline": 0.236,
    },
    "scifact": {
        "description": "Scientific claim verification",
        "domain": "general",
        "size": "5.2k docs, 300 queries",
        "metric": "NDCG@10",
        "bm25_baseline": 0.665,
    },
    "arguana": {
        "description": "Counter-argument retrieval",
        "domain": "general",
        "size": "8.7k docs, 1.4k queries",
        "metric": "NDCG@10",
        "bm25_baseline": 0.472,
    },
}


# ─── Result Classes ───────────────────────────────────────────────────────────


@dataclass
class BEIRDatasetResult:
    """Results for a single BEIR dataset."""

    dataset_name: str
    retrieval_mode: str
    scores: AggregatedEvalScore
    bm25_baseline: float | None = None
    improvement: float | None = None  # over BM25 baseline, if known
    duration_s: float = 0.0
    query_count: int = 0
    error: str | None = None

    def __post_init__(self) -> None:
        if self.bm25_baseline and self.bm25_baseline > 0:
            self.improvement = (
                (self.scores.ndcg_at_10 - self.bm25_baseline) / self.bm25_baseline * 100
            )

    def to_dict(self) -> dict[str, Any]:
        d = {
            f"beir_{self.dataset_name}_ndcg@10": self.scores.ndcg_at_10,
            f"beir_{self.dataset_name}_mrr": self.scores.mrr,
            f"beir_{self.dataset_name}_map@10": self.scores.map_at_10,
            f"beir_{self.dataset_name}_queries": float(self.query_count),
        }
        if self.improvement is not None:
            d[f"beir_{self.dataset_name}_vs_bm25_pct"] = self.improvement
        return d


@dataclass
class BEIRSuiteResult:
    """Results across all BEIR datasets in a run."""

    dataset_results: list[BEIRDatasetResult]
    mean_ndcg: float = 0.0
    duration_s: float = 0.0

    def __post_init__(self) -> None:
        successful = [r for r in self.dataset_results if r.error is None]
        if successful:
            self.mean_ndcg = sum(r.scores.ndcg_at_10 for r in successful) / len(successful)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "beir_mean_ndcg@10": self.mean_ndcg,
            "beir_duration_s": self.duration_s,
        }
        for r in self.dataset_results:
            out.update(r.to_dict())
        return out

    def summary(self) -> str:
        lines = [
            "\n=== BEIR Benchmark Results ===",
            f"Mean NDCG@10: {self.mean_ndcg:.4f}  (duration: {self.duration_s:.0f}s)",
            "",
            f"{'Dataset':<20} {'NDCG@10':>10} {'MRR':>8} {'BM25 Base':>10} {'Δ vs BM25':>10}",
            "-" * 62,
        ]
        for r in self.dataset_results:
            if r.error:
                lines.append(f"  {r.dataset_name:<18} {'ERROR':>10}")
            else:
                improvement = (
                    f"+{r.improvement:.1f}%"
                    if r.improvement and r.improvement > 0
                    else (f"{r.improvement:.1f}%" if r.improvement else "  N/A")
                )
                lines.append(
                    f"  {r.dataset_name:<18} "
                    f"{r.scores.ndcg_at_10:>10.4f} "
                    f"{r.scores.mrr:>8.4f} "
                    f"{(r.bm25_baseline or 0):>10.3f} "
                    f"{improvement:>10}"
                )
        return "\n".join(lines)


# ─── BEIRRunner ──────────────────────────────────────────────────────────────


class BEIRRunner:
    """
    Evaluates the RetrievalLab retrieval stack on standard BEIR benchmarks.

    This class integrates with the beir Python library (pip install beir) to
    download standard datasets and evaluate against their official qrels.

    Args:
        retriever:      RetrieverCore instance.
        embed_hub:      EmbedHub for corpus embedding.
        data_dir:       Directory to download/cache BEIR datasets.
        retrieval_mode: "sparse", "dense", or "hybrid".

    Example:
        runner = BEIRRunner(
            retriever=retriever,
            embed_hub=EmbedHub("text-embedding-3-small"),
            data_dir="data/beir/",
        )
        result = await runner.run("nfcorpus")
        print(f"NDCG@10: {result.scores.ndcg_at_10:.4f}")
    """

    def __init__(
        self,
        retriever,
        embed_hub,
        data_dir: str = "data/beir/",
        retrieval_mode: str = "hybrid",
    ) -> None:
        self.retriever = retriever
        self.embed_hub = embed_hub
        self.data_dir = Path(data_dir)
        self.retrieval_mode = retrieval_mode

    async def run(
        self,
        dataset_name: str,
        top_k: int = 100,
        max_queries: int | None = None,
    ) -> BEIRDatasetResult:
        """
        Run BEIR evaluation on a single dataset.

        Downloads the dataset if not cached, ingests into RetrievalLab,
        runs all queries, and computes standard BEIR metrics.

        Args:
            dataset_name: BEIR dataset name (e.g., "nfcorpus", "fiqa").
            top_k:        Number of results to retrieve per query (default 100).
            max_queries:  Cap query count for quick dev runs (None = all).

        Returns:
            BEIRDatasetResult with NDCG@10, MRR, MAP@10.
        """
        if dataset_name not in BEIR_DATASETS:
            raise ValueError(
                f"Unknown BEIR dataset: {dataset_name!r}. Available: {list(BEIR_DATASETS.keys())}"
            )

        start = time.perf_counter()
        config = BEIR_DATASETS[dataset_name]

        logger.info(
            "beir_dataset_start",
            dataset=dataset_name,
            domain=config["domain"],
            size=config["size"],
        )

        try:
            # 1. Load corpus, queries, qrels from BEIR
            corpus, queries, qrels = await self._load_beir_dataset(dataset_name)

            if max_queries:
                query_ids = list(queries.keys())[:max_queries]
                queries = {qid: queries[qid] for qid in query_ids}

            # 2. Ingest corpus into RetrievalLab
            corpus_id = f"beir_{dataset_name}"
            await self._ingest_corpus(corpus_id, corpus, config["domain"])

            # 3. Embed and build index
            await self._build_index(corpus_id)

            # 4. Run all queries and collect results
            per_query_scores = await self._eval_all_queries(queries, corpus_id, qrels, top_k)

            # 5. Aggregate
            agg = aggregate_scores(per_query_scores)

            duration = time.perf_counter() - start
            logger.info(
                "beir_dataset_complete",
                dataset=dataset_name,
                ndcg_at_10=round(agg.ndcg_at_10, 4),
                mrr=round(agg.mrr, 4),
                query_count=len(per_query_scores),
                duration_s=round(duration, 1),
            )

            return BEIRDatasetResult(
                dataset_name=dataset_name,
                retrieval_mode=self.retrieval_mode,
                scores=agg,
                bm25_baseline=config.get("bm25_baseline"),
                duration_s=duration,
                query_count=len(per_query_scores),
            )

        except Exception as exc:
            logger.error("beir_dataset_failed", dataset=dataset_name, error=str(exc))
            return BEIRDatasetResult(
                dataset_name=dataset_name,
                retrieval_mode=self.retrieval_mode,
                scores=AggregatedEvalScore(),
                error=str(exc),
                duration_s=time.perf_counter() - start,
            )

    async def run_suite(
        self,
        datasets: list[str] | None = None,
        top_k: int = 100,
        max_queries: int | None = None,
    ) -> BEIRSuiteResult:
        """
        Run BEIR evaluation on multiple datasets sequentially.

        Args:
            datasets:    List of dataset names (default: all in BEIR_DATASETS).
            top_k:       Results per query.
            max_queries: Cap per dataset for quick runs.

        Returns:
            BEIRSuiteResult with all dataset results and mean NDCG@10.
        """
        datasets = datasets or list(BEIR_DATASETS.keys())
        start = time.perf_counter()
        results = []

        for dataset in datasets:
            result = await self.run(dataset, top_k=top_k, max_queries=max_queries)
            results.append(result)

        return BEIRSuiteResult(
            dataset_results=results,
            duration_s=time.perf_counter() - start,
        )

    # ── Internal Pipeline Steps ───────────────────────────────────────────────

    async def _load_beir_dataset(
        self,
        dataset_name: str,
    ) -> tuple[dict, dict, dict]:
        """
        Load BEIR corpus, queries, and qrels using the beir library.

        Downloads to self.data_dir if not cached.
        Returns: (corpus, queries, qrels) in BEIR format.
        """
        try:
            from beir import util as beir_util
            from beir.datasets.data_loader import GenericDataLoader
        except ImportError:
            raise ImportError(
                "BEIR library required: pip install beir\n"
                "Also install: pip install pytrec-eval-terrier"
            )

        dataset_path = self.data_dir / dataset_name

        if not dataset_path.exists():
            logger.info("downloading_beir_dataset", dataset=dataset_name)
            url = f"https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/{dataset_name}.zip"
            beir_util.download_and_unzip(url, str(self.data_dir))

        corpus, queries, qrels = GenericDataLoader(data_folder=str(dataset_path)).load(split="test")

        logger.info(
            "beir_dataset_loaded",
            dataset=dataset_name,
            corpus_size=len(corpus),
            query_count=len(queries),
        )
        return corpus, queries, qrels

    async def _ingest_corpus(
        self,
        corpus_id: str,
        corpus: dict,
        domain: str,
    ) -> None:
        """
        Write BEIR corpus to temporary files and ingest into RetrievalLab.

        Reuses existing corpus if already ingested (idempotent).
        """
        import json

        # Write corpus to temp dir
        tmp_dir = self.data_dir / "tmp" / corpus_id
        tmp_dir.mkdir(parents=True, exist_ok=True)

        corpus_file = tmp_dir / "corpus.jsonl"
        with open(corpus_file, "w") as f:
            for doc_id, doc in corpus.items():
                text = doc.get("text", "") + " " + doc.get("title", "")
                f.write(json.dumps({"id": doc_id, "text": text.strip()}) + "\n")

        # Ingest using CorpusForge (reuses fingerprint check for idempotency)
        from backend.db.base import AsyncSessionLocal
        from backend.services.corpus_forge import CorpusForge, IngestRequest

        async with AsyncSessionLocal() as db:
            forge = CorpusForge(db=db)
            request = IngestRequest(
                corpus_id=corpus_id,
                source=str(corpus_file),
                domain=domain,
                strategy="recursive",
            )
            result = await forge.ingest(request)
            logger.info("beir_corpus_ingested", corpus_id=corpus_id, skipped=result.skipped)

    async def _build_index(self, corpus_id: str) -> None:
        """Embed corpus and build vector index."""
        from backend.db.base import AsyncSessionLocal
        from backend.services.index_registry import IndexRegistry

        async with AsyncSessionLocal() as db:
            await self.embed_hub.embed_corpus(corpus_id=corpus_id, db=db)

        registry = IndexRegistry()
        async with AsyncSessionLocal() as db:
            await registry.build_from_db(
                corpus_id=corpus_id,
                backend="faiss",
                embed_model=self.embed_hub.model_config.name,
                db=db,
            )
        # Register in retriever's index registry
        built_index = registry.get(corpus_id, "faiss")
        if built_index:
            self.retriever.index_registry.register(corpus_id, "faiss", built_index)

    async def _eval_all_queries(
        self,
        queries: dict[str, str],
        corpus_id: str,
        qrels: dict[str, dict[str, int]],
        top_k: int,
    ) -> list[EvalScore]:
        """Retrieve results for all queries and compute per-query scores."""
        from backend.services.retriever_core import RetrievalRequest

        scores: list[EvalScore] = []

        for qid, query_text in queries.items():
            try:
                request = RetrievalRequest(
                    query=query_text,
                    corpus_id=corpus_id,
                    mode=self.retrieval_mode,
                    top_k=top_k,
                )
                results = await self.retriever.retrieve(request)
                retrieved_ids = [r.chunk_id for r in results]

                # Convert qrels int grades to float
                relevant = {
                    doc_id: float(grade)
                    for doc_id, grade in qrels.get(qid, {}).items()
                    if grade > 0
                }

                score = evaluate_retrieval(retrieved_ids, relevant, query=query_text)
                scores.append(score)

            except Exception as exc:
                logger.warning("query_failed", qid=qid, error=str(exc))
                scores.append(EvalScore(query=query_text))

        return scores
