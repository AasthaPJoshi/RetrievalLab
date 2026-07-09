# =============================================================================
# RetrievalLab — backend/services/retriever_core.py
# =============================================================================
# PURPOSE : RetrieverCore implements the three retrieval modes:
#           sparse (BM25), dense (vector), and hybrid (both fused via RRF).
#
# RETRIEVAL MODES:
#   sparse  — BM25 keyword matching via Elasticsearch or rank_bm25
#   dense   — vector similarity via IndexRegistry (FAISS / Chroma)
#   hybrid  — Reciprocal Rank Fusion of sparse + dense results
#
# WHY HYBRID?
#   Dense retrieval excels at semantic queries ("what causes cardiac arrest?")
#   Sparse retrieval excels at exact-match queries ("FDA 21 CFR 820.30")
#   Hybrid combines both, consistently outperforming either alone on standard
#   benchmarks (BEIR, MIRACL) by 5-12% NDCG@10.
#
# RECIPROCAL RANK FUSION (RRF):
#   score(d) = Σ 1 / (k + rank(d, list_i))
#   where k=60 is a damping constant (Cormack et al., 2009).
#   RRF requires no tuning and beats linear interpolation on most tasks.
#
# HOW TO USE:
#   retriever = RetrieverCore(
#       index_registry=registry,
#       embed_hub=hub,
#   )
#   results = await retriever.retrieve(
#       query="How is diabetes diagnosed?",
#       corpus_id="healthcare_v1",
#       mode="hybrid",
#       top_k=10,
#   )
#
# INPUT  : Natural language query string + corpus_id + retrieval mode
# OUTPUT : List[RetrievalResult] sorted by relevance score
#
# AFTER THIS FILE:
#   Results go to → EvalEngine (Day 3) for NDCG@K / MRR / MAP computation
# =============================================================================

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Literal

import structlog

from backend.services.embed_hub import EmbedHub
from backend.services.index_registry import IndexRegistry

logger = structlog.get_logger(__name__)

RetrievalMode = Literal["sparse", "dense", "hybrid"]


# ─── Result Data Class ────────────────────────────────────────────────────────

@dataclass
class RetrievalResult:
    """
    Single retrieval result with attribution metadata.

    Attributes:
        chunk_id:       UUID of the matching chunk.
        text:           Text content.
        score:          Final relevance score (RRF for hybrid, raw for others).
        rank:           1-based rank in final result list.
        source_doc:     Source document identifier.
        retrieval_mode: Mode used ("sparse", "dense", "hybrid").
        sparse_rank:    Rank in sparse (BM25) result list (None if not retrieved).
        dense_rank:     Rank in dense (vector) result list (None if not retrieved).
        latency_ms:     Total retrieval latency in milliseconds.
        metadata:       Chunk metadata.
    """
    chunk_id:       str
    text:           str
    score:          float
    rank:           int
    source_doc:     str              = ""
    retrieval_mode: str              = "hybrid"
    sparse_rank:    int | None       = None
    dense_rank:     int | None       = None
    latency_ms:     float            = 0.0
    metadata:       dict[str, Any]   = field(default_factory=dict)


@dataclass
class RetrievalRequest:
    """Parameters for a single retrieval call."""
    query:       str
    corpus_id:   str
    mode:        RetrievalMode  = "hybrid"
    top_k:       int            = 10
    dense_weight:  float        = 0.5   # weight for hybrid combination (unused in RRF)
    rrf_k:         int          = 60    # RRF damping constant
    rerank:        bool         = False  # whether to apply cross-encoder reranking (Day 4+)


# ─── RetrieverCore ────────────────────────────────────────────────────────────

class RetrieverCore:
    """
    Core retrieval engine supporting sparse, dense, and hybrid modes.

    Args:
        index_registry: IndexRegistry with built FAISS/Chroma indexes.
        embed_hub:      EmbedHub for query embedding.
        bm25_indexes:   dict mapping corpus_id → BM25Okapi instance (for sparse).
        default_mode:   Default retrieval mode if not specified per-request.

    Example:
        retriever = RetrieverCore(
            index_registry=IndexRegistry(),
            embed_hub=EmbedHub(model_name="text-embedding-3-small"),
        )

        # Search healthcare corpus
        results = await retriever.retrieve(
            query="symptoms of type 2 diabetes",
            corpus_id="healthcare_pubmed_v1",
            mode="hybrid",
            top_k=10,
        )

        for r in results:
            print(f"[{r.rank}] (score={r.score:.4f}) {r.text[:120]}")
    """

    # k constant for Reciprocal Rank Fusion
    RRF_K = 60

    def __init__(
        self,
        index_registry: IndexRegistry,
        embed_hub:       EmbedHub,
        bm25_indexes:    dict[str, Any] | None = None,
        default_mode:    RetrievalMode = "hybrid",
        default_backend: str = "faiss",
    ) -> None:
        self.index_registry = index_registry
        self.embed_hub      = embed_hub
        self.bm25_indexes   = bm25_indexes or {}
        self.default_mode   = default_mode
        self.default_backend = default_backend

    # ── Main Entry Point ──────────────────────────────────────────────────────

    async def retrieve(self, request: RetrievalRequest) -> list[RetrievalResult]:
        """
        Execute a retrieval request and return ranked results.

        Routes to sparse(), dense(), or hybrid() based on request.mode.

        Args:
            request: RetrievalRequest with query, corpus_id, mode, top_k.

        Returns:
            Ranked list of RetrievalResult (rank 1 = most relevant).

        Raises:
            ValueError: If corpus has no index built for the requested mode.
        """
        start = time.perf_counter()
        mode  = request.mode

        logger.info(
            "retrieve_started",
            query=request.query[:80],
            corpus_id=request.corpus_id,
            mode=mode,
            top_k=request.top_k,
        )

        if mode == "dense":
            results = await self._dense_retrieve(request)
        elif mode == "sparse":
            results = await self._sparse_retrieve(request)
        elif mode == "hybrid":
            results = await self._hybrid_retrieve(request)
        else:
            raise ValueError(f"Unknown retrieval mode: {mode!r}")

        latency_ms = round((time.perf_counter() - start) * 1000, 2)

        # Attach latency to each result
        for r in results:
            r.latency_ms = latency_ms

        logger.info(
            "retrieve_complete",
            mode=mode,
            results=len(results),
            latency_ms=latency_ms,
        )

        return results

    # ── Dense Retrieval ───────────────────────────────────────────────────────

    async def _dense_retrieve(self, request: RetrievalRequest) -> list[RetrievalResult]:
        """
        Dense (vector similarity) retrieval.

        1. Embed the query text.
        2. Search the vector index.
        3. Convert IndexSearchResults to RetrievalResults.
        """
        # Embed query
        query_vector = await self.embed_hub.embed_single(request.query)

        # Search index
        raw_results = await self.index_registry.search(
            corpus_id    = request.corpus_id,
            backend      = self.default_backend,
            query_vector = query_vector,
            top_k        = request.top_k,
        )

        return [
            RetrievalResult(
                chunk_id       = r.chunk_id,
                text           = r.text,
                score          = r.score,
                rank           = r.rank,
                source_doc     = r.source_doc,
                retrieval_mode = "dense",
                dense_rank     = r.rank,
                metadata       = r.metadata,
            )
            for r in raw_results
        ]

    # ── Sparse Retrieval ──────────────────────────────────────────────────────

    async def _sparse_retrieve(self, request: RetrievalRequest) -> list[RetrievalResult]:
        """
        Sparse (BM25) retrieval using rank_bm25.

        Falls back to Elasticsearch if rank_bm25 index not available.

        BM25 formula:
            score(D,Q) = Σ IDF(qi) * f(qi,D) * (k1+1) / (f(qi,D) + k1*(1-b+b*|D|/avgdl))
        """
        corpus_id = request.corpus_id

        # Try in-memory BM25 first
        if corpus_id in self.bm25_indexes:
            return await self._bm25_retrieve(request)

        # Fallback: Elasticsearch sparse retrieval
        return await self._elasticsearch_retrieve(request)

    async def _bm25_retrieve(self, request: RetrievalRequest) -> list[RetrievalResult]:
        """In-memory BM25 search using rank_bm25."""
        import asyncio

        from rank_bm25 import BM25Okapi

        bm25_data = self.bm25_indexes[request.corpus_id]
        bm25: BM25Okapi    = bm25_data["bm25"]
        chunk_ids: list[str] = bm25_data["chunk_ids"]
        texts:     list[str] = bm25_data["texts"]

        # Tokenize query (simple whitespace tokenization)
        tokenized_query = request.query.lower().split()

        def _sync_score():
            scores  = bm25.get_scores(tokenized_query)
            top_idx = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
            return top_idx[:request.top_k], scores

        top_idx, scores = await asyncio.get_event_loop().run_in_executor(None, _sync_score)

        results = []
        for rank, idx in enumerate(top_idx[:request.top_k], start=1):
            results.append(RetrievalResult(
                chunk_id       = chunk_ids[idx],
                text           = texts[idx],
                score          = float(scores[idx]),
                rank           = rank,
                retrieval_mode = "sparse",
                sparse_rank    = rank,
            ))

        return results

    async def _elasticsearch_retrieve(self, request: RetrievalRequest) -> list[RetrievalResult]:
        """BM25 retrieval via Elasticsearch."""
        try:
            from config.settings import get_settings
            from elasticsearch import AsyncElasticsearch
            s = get_settings()

            es = AsyncElasticsearch(s.elasticsearch.url)
            index_name = f"{s.elasticsearch.index_prefix}{request.corpus_id}"

            response = await es.search(
                index=index_name,
                body={
                    "query": {"match": {"text": {"query": request.query}}},
                    "size": request.top_k,
                },
            )
            await es.close()

            results = []
            for rank, hit in enumerate(response["hits"]["hits"], start=1):
                results.append(RetrievalResult(
                    chunk_id       = hit["_id"],
                    text           = hit["_source"].get("text", ""),
                    score          = hit["_score"],
                    rank           = rank,
                    retrieval_mode = "sparse",
                    sparse_rank    = rank,
                    metadata       = hit["_source"].get("metadata", {}),
                ))

            return results

        except Exception as exc:
            logger.warning("elasticsearch_retrieve_failed", error=str(exc))
            return []

    # ── Hybrid Retrieval (RRF Fusion) ─────────────────────────────────────────

    async def _hybrid_retrieve(self, request: RetrievalRequest) -> list[RetrievalResult]:
        """
        Hybrid retrieval using Reciprocal Rank Fusion (RRF).

        Runs sparse and dense in parallel, then fuses with RRF formula.

        RRF(d) = Σ 1 / (k + rank(d))  for each result list containing d
        Lower rank = higher score = higher in final list.

        Why RRF beats linear interpolation:
        - No score normalization needed (different scales for BM25 vs cosine)
        - Works well even when one ranker has very low confidence
        - Robust to rank ties and edge cases
        """
        import asyncio

        # Run sparse and dense retrieval in parallel
        # Fetch 2x top_k from each to maximize RRF coverage
        fetch_k = min(request.top_k * 2, 50)

        sparse_request = RetrievalRequest(
            query=request.query,
            corpus_id=request.corpus_id,
            mode="sparse",
            top_k=fetch_k,
        )
        dense_request = RetrievalRequest(
            query=request.query,
            corpus_id=request.corpus_id,
            mode="dense",
            top_k=fetch_k,
        )

        sparse_results, dense_results = await asyncio.gather(
            self._sparse_retrieve(sparse_request),
            self._dense_retrieve(dense_request),
            return_exceptions=True,
        )

        # Handle failures gracefully
        if isinstance(sparse_results, Exception):
            logger.warning("sparse_failed_hybrid_dense_only", error=str(sparse_results))
            sparse_results = []
        if isinstance(dense_results, Exception):
            logger.warning("dense_failed_hybrid_sparse_only", error=str(dense_results))
            dense_results = []

        # RRF fusion
        fused = self._rrf_fuse(
            lists=[sparse_results, dense_results],
            k=request.rrf_k,
            top_k=request.top_k,
        )

        return fused

    def _rrf_fuse(
        self,
        lists:  list[list[RetrievalResult]],
        k:      int = 60,
        top_k:  int = 10,
    ) -> list[RetrievalResult]:
        """
        Apply Reciprocal Rank Fusion across multiple ranked lists.

        Args:
            lists:  List of ranked result lists (sparse, dense, etc.)
            k:      RRF damping constant (default 60, per Cormack 2009).
            top_k:  Number of results to return.

        Returns:
            Merged, re-ranked list of RetrievalResult.
        """
        # Track RRF scores and result objects per chunk_id
        rrf_scores: dict[str, float]           = {}
        chunk_data: dict[str, RetrievalResult] = {}

        for result_list in lists:
            for result in result_list:
                cid = result.chunk_id
                rrf_scores[cid] = rrf_scores.get(cid, 0.0) + 1.0 / (k + result.rank)
                if cid not in chunk_data:
                    chunk_data[cid] = result

        # Sort by RRF score (descending)
        ranked_ids = sorted(rrf_scores, key=lambda cid: rrf_scores[cid], reverse=True)

        fused: list[RetrievalResult] = []
        for final_rank, cid in enumerate(ranked_ids[:top_k], start=1):
            base = chunk_data[cid]
            fused.append(RetrievalResult(
                chunk_id       = base.chunk_id,
                text           = base.text,
                score          = rrf_scores[cid],
                rank           = final_rank,
                source_doc     = base.source_doc,
                retrieval_mode = "hybrid",
                sparse_rank    = base.sparse_rank,
                dense_rank     = base.dense_rank,
                metadata       = base.metadata,
            ))

        return fused

    # ── BM25 Index Builder ────────────────────────────────────────────────────

    async def build_bm25_index(
        self,
        corpus_id:  str,
        db:         AsyncSession,
    ) -> None:
        """
        Build an in-memory BM25 index for a corpus from the database.

        Should be called after corpus ingestion. The BM25 index lives in RAM
        and needs to be rebuilt on server restart.

        Args:
            corpus_id: Corpus to index.
            db:        Database session.
        """
        import asyncio

        from rank_bm25 import BM25Okapi

        from backend.models.corpus import Chunk, Corpus

        result = await db.execute(
            __import__("sqlalchemy", fromlist=["select"]).select(Corpus).where(
                Corpus.corpus_id == corpus_id
            )
        )
        corpus = result.scalar_one_or_none()
        if corpus is None:
            raise ValueError(f"Corpus '{corpus_id}' not found")

        chunk_result = await db.execute(
            __import__("sqlalchemy", fromlist=["select"]).select(Chunk)
            .where(Chunk.corpus_id == corpus.id)
            .order_by(Chunk.chunk_index)
        )
        chunks = chunk_result.scalars().all()

        chunk_ids = [str(c.id)   for c in chunks]
        texts     = [c.text      for c in chunks]
        tokenized = [t.lower().split() for t in texts]

        def _build():
            return BM25Okapi(tokenized)

        bm25 = await asyncio.get_event_loop().run_in_executor(None, _build)

        self.bm25_indexes[corpus_id] = {
            "bm25":      bm25,
            "chunk_ids": chunk_ids,
            "texts":     texts,
        }

        logger.info("bm25_index_built", corpus_id=corpus_id, chunks=len(chunks))
