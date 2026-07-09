# =============================================================================
# RetrievalLab — backend/services/observe_lab.py
# =============================================================================
# PURPOSE : Centralized observability for all retrieval operations.
#           Instruments every retrieval call with OpenTelemetry traces and
#           Prometheus metrics so you can monitor production performance.
#
# WHAT IT TRACKS:
#   • Retrieval latency histogram (p50, p95, p99 by corpus, mode, strategy)
#   • Chunk counts per retrieval
#   • NDCG@10 per experiment run
#   • Agent pipeline node latencies
#   • Active retrieval request count (gauge)
#   • Cache hit/miss rates for embedding cache
#
# METRICS EXPOSED:
#   /metrics endpoint (Prometheus scrape target)
#   Grafana dashboard JSON in docs/grafana_dashboard.json
#
# HOW TO USE:
#   observe = ObserveLab()
#
#   # Instrument a retrieval call:
#   with observe.trace_retrieval("my_corpus", "hybrid") as span:
#       results = await retriever.retrieve(request)
#       observe.record_retrieval(results, latency_ms=span.latency_ms)
#
# INPUT  : Retrieval events from RetrieverCore and EvalEngine
# OUTPUT : OpenTelemetry spans → Jaeger/Tempo
#          Prometheus metrics   → Grafana dashboards
# =============================================================================

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Generator

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class RetrievalSpan:
    """Context manager span for timing retrieval operations."""
    corpus_id: str
    mode:      str
    start_time: float = 0.0
    latency_ms: float = 0.0

    def __enter__(self) -> "RetrievalSpan":
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, *args) -> None:
        self.latency_ms = round((time.perf_counter() - self.start_time) * 1000, 2)


class ObserveLab:
    """
    Observability layer for RetrievalLab.

    Wraps OpenTelemetry tracing and Prometheus metrics in a single interface.
    Gracefully degrades if telemetry dependencies are unavailable.

    Usage:
        observe = ObserveLab()
        observe.start()  # initialize metrics server

        # Time a retrieval
        with observe.trace_retrieval("healthcare_v1", "hybrid") as span:
            results = await retriever.retrieve(req)
        observe.record_retrieval_completed(
            corpus_id="healthcare_v1",
            mode="hybrid",
            result_count=len(results),
            latency_ms=span.latency_ms,
        )

        # Record eval metrics
        observe.record_eval_score(
            corpus_id="healthcare_v1",
            ndcg_at_10=0.847,
            mrr=0.912,
        )
    """

    def __init__(self) -> None:
        self._metrics_initialized = False
        self._tracer              = None
        self._prom_available      = False
        self._counters: dict[str, Any] = {}
        self._histograms: dict[str, Any] = {}
        self._gauges: dict[str, Any]    = {}

    def start(self, port: int = 9090) -> None:
        """Initialize Prometheus metrics server and OpenTelemetry tracer."""
        self._init_prometheus(port)
        self._init_otel()

    def _init_prometheus(self, port: int) -> None:
        """Set up Prometheus metrics."""
        try:
            from prometheus_client import (
                Counter, Histogram, Gauge, start_http_server,
                CollectorRegistry, CONTENT_TYPE_LATEST, generate_latest,
            )

            # Retrieval latency histogram (ms)
            self._histograms["retrieval_latency"] = Histogram(
                "retrievallab_retrieval_latency_ms",
                "Retrieval latency in milliseconds",
                labelnames=["corpus_id", "mode", "strategy"],
                buckets=[10, 25, 50, 100, 250, 500, 1000, 2500, 5000],
            )

            # Retrieval result count
            self._histograms["result_count"] = Histogram(
                "retrievallab_result_count",
                "Number of results returned per retrieval",
                labelnames=["corpus_id", "mode"],
                buckets=[1, 5, 10, 20, 50, 100],
            )

            # Total retrieval requests
            self._counters["requests_total"] = Counter(
                "retrievallab_requests_total",
                "Total retrieval requests",
                labelnames=["corpus_id", "mode", "status"],
            )

            # NDCG@10 gauge per experiment
            self._gauges["ndcg_at_10"] = Gauge(
                "retrievallab_ndcg_at_10",
                "Latest NDCG@10 score",
                labelnames=["corpus_id", "retriever_mode"],
            )

            # Active requests
            self._gauges["active_requests"] = Gauge(
                "retrievallab_active_requests",
                "Currently active retrieval requests",
            )

            # Embedding cache hits
            self._counters["cache_hits"] = Counter(
                "retrievallab_embed_cache_hits_total",
                "Embedding cache hits",
                labelnames=["model"],
            )
            self._counters["cache_misses"] = Counter(
                "retrievallab_embed_cache_misses_total",
                "Embedding cache misses",
                labelnames=["model"],
            )

            # Agent pipeline node latencies
            self._histograms["agent_node_latency"] = Histogram(
                "retrievallab_agent_node_latency_ms",
                "Agent pipeline node latency",
                labelnames=["node_name"],
                buckets=[10, 50, 100, 500, 1000, 3000],
            )

            # Rerank rank-shift — how much cross-encoder reranking changed result order
            self._histograms["rerank_score_delta"] = Histogram(
                "retrievallab_rerank_score_delta",
                "Average rank position shift caused by cross-encoder reranking",
                labelnames=["corpus_id"],
                buckets=[0, 0.5, 1, 2, 3, 5, 10, 20],
            )

            # Start HTTP server for Prometheus scraping
            try:
                start_http_server(port)
                logger.info("prometheus_metrics_server_started", port=port)
            except OSError:
                logger.warning("prometheus_port_in_use", port=port)

            self._prom_available = True
            self._metrics_initialized = True

        except ImportError:
            logger.warning("prometheus_client_not_installed", advice="pip install prometheus-client")

    def _init_otel(self) -> None:
        """Set up OpenTelemetry tracer."""
        try:
            from opentelemetry import trace
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
            from config.settings import get_settings

            s        = get_settings()
            provider = TracerProvider()

            try:
                from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
                exporter  = OTLPSpanExporter(endpoint=s.observability.otel_endpoint)
                processor = BatchSpanProcessor(exporter)
                provider.add_span_processor(processor)
            except Exception:
                pass  # OTLP exporter optional

            trace.set_tracer_provider(provider)
            self._tracer = trace.get_tracer("retrievallab")
            logger.info("otel_tracer_initialized")

        except ImportError:
            logger.debug("opentelemetry_not_available")

    # ── Public API ────────────────────────────────────────────────────────────

    @contextmanager
    def trace_retrieval(
        self,
        corpus_id: str,
        mode:      str,
        strategy:  str = "hybrid",
    ) -> Generator[RetrievalSpan, None, None]:
        """
        Context manager that times a retrieval operation and records metrics.

        Usage:
            with observe.trace_retrieval("healthcare_v1", "hybrid") as span:
                results = await retriever.retrieve(req)
            # span.latency_ms is populated after the block exits
        """
        span = RetrievalSpan(corpus_id=corpus_id, mode=mode)

        if self._prom_available:
            self._gauges["active_requests"].inc()

        with span:
            yield span

        if self._prom_available:
            self._gauges["active_requests"].dec()
            self._histograms["retrieval_latency"].labels(
                corpus_id=corpus_id,
                mode=mode,
                strategy=strategy,
            ).observe(span.latency_ms)

    def record_retrieval_completed(
        self,
        corpus_id:    str,
        mode:         str,
        result_count: int,
        latency_ms:   float,
        status:       str = "success",
    ) -> None:
        """Record a completed retrieval call."""
        if not self._prom_available:
            return
        self._counters["requests_total"].labels(
            corpus_id=corpus_id, mode=mode, status=status
        ).inc()
        self._histograms["result_count"].labels(
            corpus_id=corpus_id, mode=mode
        ).observe(result_count)

    def record_eval_score(
        self,
        corpus_id:    str,
        retriever_mode: str,
        ndcg_at_10:   float,
        mrr:          float = 0.0,
    ) -> None:
        """Record evaluation metrics from an experiment run."""
        if not self._prom_available:
            return
        self._gauges["ndcg_at_10"].labels(
            corpus_id=corpus_id, retriever_mode=retriever_mode
        ).set(ndcg_at_10)

        logger.info(
            "eval_score_recorded",
            corpus_id=corpus_id,
            retriever_mode=retriever_mode,
            ndcg_at_10=ndcg_at_10,
            mrr=mrr,
        )

    def record_cache_event(self, model: str, hit: bool) -> None:
        """Record embedding cache hit or miss."""
        if not self._prom_available:
            return
        if hit:
            self._counters["cache_hits"].labels(model=model).inc()
        else:
            self._counters["cache_misses"].labels(model=model).inc()

    def record_agent_node(self, node_name: str, latency_ms: float) -> None:
        """Record individual agent pipeline node latency."""
        if not self._prom_available:
            return
        self._histograms["agent_node_latency"].labels(node_name=node_name).observe(latency_ms)

    def record_rerank_delta(self, corpus_id: str, avg_rank_shift: float) -> None:
        """Record how much reranking changed result ordering vs initial retrieval score."""
        if not self._prom_available:
            return
        self._histograms["rerank_score_delta"].labels(corpus_id=corpus_id).observe(avg_rank_shift)

    def get_stats_snapshot(self) -> dict[str, Any]:
        """Return current metrics snapshot as a dict (for /health endpoint)."""
        return {
            "metrics_initialized": self._metrics_initialized,
            "prometheus_available": self._prom_available,
            "otel_available":       self._tracer is not None,
        }


# Module-level singleton
observe_lab = ObserveLab()
