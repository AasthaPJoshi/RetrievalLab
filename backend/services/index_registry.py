# =============================================================================
# RetrievalLab — backend/services/index_registry.py
# =============================================================================
# PURPOSE : IndexRegistry manages multiple vector index backends.
#           It provides a single interface for building, saving, loading,
#           and querying vector indexes regardless of the backend.
#
# SUPPORTED BACKENDS:
#   faiss       — Facebook AI Similarity Search (in-process, fastest)
#   chromadb    — Chroma local vector DB (persistent, easy dev setup)
#   pgvector    — PostgreSQL pgvector (SQL + vector in one DB)
#   elasticsearch — Elasticsearch dense vector + BM25 (for hybrid)
#
# DESIGN PATTERN:
#   VectorIndex (ABC) ← backend implementations (FaissIndex, ChromaIndex, ...)
#   IndexRegistry holds registered indexes; routes build/search calls.
#
# HOW TO USE:
#   registry = IndexRegistry()
#   # Build index from corpus chunks
#   await registry.build("healthcare_v1", backend="faiss", db=session)
#   # Search
#   results = await registry.search("healthcare_v1", query_vector=[...], top_k=10)
#
# INPUT  : Chunk embeddings from EmbedHub + corpus metadata from PostgreSQL
# OUTPUT : IndexSearchResult list (chunk_id, text, score, metadata)
#
# AFTER THIS FILE:
#   IndexRegistry is queried by → RetrieverCore (sparse + dense + hybrid)
#   which then merges results and passes to → EvalEngine (Day 3)
# =============================================================================

from __future__ import annotations

import abc
import pickle
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


# ─── Data Classes ─────────────────────────────────────────────────────────────


@dataclass
class IndexSearchResult:
    """
    Single result from a vector index search.

    Attributes:
        chunk_id:   UUID of the matching chunk.
        text:       Text content of the chunk.
        score:      Similarity score (0.0–1.0 for cosine; can exceed 1.0 for BM25).
        rank:       1-based rank within this search result set.
        source_doc: Source document ID for provenance.
        metadata:   Chunk metadata dict (section headers, page numbers, etc.)
    """

    chunk_id: str
    text: str
    score: float
    rank: int
    source_doc: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        preview = self.text[:80].replace("\n", " ")
        return f"IndexSearchResult(rank={self.rank}, score={self.score:.4f}, text={preview!r})"


# ─── Abstract Base ────────────────────────────────────────────────────────────


class VectorIndex(abc.ABC):
    """
    Abstract base class for all vector index backends.

    Subclasses implement:
        build(chunks, vectors) — index all vectors
        search(query_vector, top_k) — return top_k results
        save(path) / load(path) — persist index to disk

    All methods are async-compatible (sync backends use run_in_executor).
    """

    @property
    @abc.abstractmethod
    def backend_name(self) -> str:
        """Short identifier (e.g., 'faiss', 'chromadb')."""
        ...

    @property
    @abc.abstractmethod
    def dimensions(self) -> int:
        """Expected vector dimensions."""
        ...

    @abc.abstractmethod
    async def build(
        self,
        chunk_ids: list[str],
        texts: list[str],
        vectors: list[list[float]],
        metadata: list[dict],
    ) -> int:
        """
        Build the index from chunk data.

        Args:
            chunk_ids: Ordered list of chunk UUIDs.
            texts:     Text content of each chunk (for retrieval).
            vectors:   Dense embedding vectors (same order as chunk_ids).
            metadata:  Per-chunk metadata dicts.

        Returns:
            Number of vectors indexed.
        """
        ...

    @abc.abstractmethod
    async def search(
        self,
        query_vector: list[float],
        top_k: int = 10,
    ) -> list[IndexSearchResult]:
        """
        Search for the top_k most similar chunks.

        Args:
            query_vector: Query embedding vector.
            top_k:        Number of results to return.

        Returns:
            Ranked list of IndexSearchResult (rank 1 = most similar).
        """
        ...

    @abc.abstractmethod
    async def save(self, path: str) -> None:
        """Persist index to disk at the given path."""
        ...

    @abc.abstractmethod
    async def load(self, path: str) -> None:
        """Load index from disk."""
        ...

    @property
    def is_built(self) -> bool:
        """Return True if the index has been built and is ready to search."""
        return False


# ─── FAISS Backend ────────────────────────────────────────────────────────────


class FaissIndex(VectorIndex):
    """
    FAISS in-process vector index.

    Fastest option for single-node deployments. Index lives in RAM.
    Supports IVFFlat (approximate, fast) and Flat (exact, slower) modes.

    Args:
        dim:         Vector dimensions (must match embedding model output).
        index_type:  "flat" (exact search) or "ivf" (approximate search, faster).
        nlist:       Number of IVF clusters (only for ivf mode). Default 100.

    Notes:
        • Flat: exact L2 search, O(n) per query. Best for < 100k vectors.
        • IVF:  approximate cosine, O(nlist) per query. Best for > 100k vectors.
        • FAISS is not persistent by default — call save() after build().
    """

    def __init__(
        self,
        dim: int = 1536,
        index_type: str = "flat",
        nlist: int = 100,
    ) -> None:
        self._dim = dim
        self._index_type = index_type
        self._nlist = nlist
        self._index = None  # faiss.Index — built lazily
        self._chunk_ids: list[str] = []
        self._texts: list[str] = []
        self._metadata: list[dict] = []
        self._is_built = False

    @property
    def backend_name(self) -> str:
        return "faiss"

    @property
    def dimensions(self) -> int:
        return self._dim

    @property
    def is_built(self) -> bool:
        return self._is_built

    async def build(
        self,
        chunk_ids: list[str],
        texts: list[str],
        vectors: list[list[float]],
        metadata: list[dict],
    ) -> int:
        """Build FAISS index from numpy float32 vectors."""
        import asyncio

        return await asyncio.get_event_loop().run_in_executor(
            None, self._build_sync, chunk_ids, texts, vectors, metadata
        )

    def _build_sync(
        self,
        chunk_ids: list[str],
        texts: list[str],
        vectors: list[list[float]],
        metadata: list[dict],
    ) -> int:
        """Synchronous FAISS build (runs in thread pool)."""
        try:
            import faiss
        except ImportError as err:
            raise ImportError("faiss-cpu required: pip install faiss-cpu") from err


        vecs = np.array(vectors, dtype=np.float32)

        # L2-normalize for cosine similarity via inner product
        faiss.normalize_L2(vecs)

        if self._index_type == "flat":
            self._index = faiss.IndexFlatIP(self._dim)  # Inner Product = cosine on normalized
        else:
            quantizer = faiss.IndexFlatIP(self._dim)
            self._index = faiss.IndexIVFFlat(quantizer, self._dim, self._nlist)
            self._index.train(vecs)

        self._index.add(vecs)
        self._chunk_ids = chunk_ids
        self._texts = texts
        self._metadata = metadata
        self._is_built = True

        logger.info("faiss_index_built", vectors=len(vectors), type=self._index_type)
        return len(vectors)

    async def search(
        self,
        query_vector: list[float],
        top_k: int = 10,
    ) -> list[IndexSearchResult]:
        """Synchronous FAISS search wrapped in thread pool."""
        import asyncio

        return await asyncio.get_event_loop().run_in_executor(
            None, self._search_sync, query_vector, top_k
        )

    def _search_sync(
        self,
        query_vector: list[float],
        top_k: int,
    ) -> list[IndexSearchResult]:
        """Inner sync search — normalize query and run faiss.search()."""
        import faiss

        if not self._is_built:
            raise RuntimeError("Index not built. Call build() first.")

        q = np.array([query_vector], dtype=np.float32)
        faiss.normalize_L2(q)

        k = min(top_k, len(self._chunk_ids))
        scores, indices = self._index.search(q, k)

        results = []
        for rank, (score, idx) in enumerate(zip(scores[0], indices[0], strict=False), start=1):
            if idx == -1:
                continue  # FAISS returns -1 for empty slots
            results.append(
                IndexSearchResult(
                    chunk_id=self._chunk_ids[idx],
                    text=self._texts[idx],
                    score=float(score),
                    rank=rank,
                    metadata=self._metadata[idx],
                )
            )
        return results

    async def save(self, path: str) -> None:
        """Save FAISS index + metadata to disk."""
        import asyncio

        import faiss

        p = Path(path)
        p.mkdir(parents=True, exist_ok=True)
        await asyncio.get_event_loop().run_in_executor(
            None, lambda: faiss.write_index(self._index, str(p / "index.faiss"))
        )
        with open(p / "meta.pkl", "wb") as f:
            pickle.dump(
                {
                    "chunk_ids": self._chunk_ids,
                    "texts": self._texts,
                    "metadata": self._metadata,
                    "dim": self._dim,
                },
                f,
            )
        logger.info("faiss_index_saved", path=str(path))

    async def load(self, path: str) -> None:
        """Load FAISS index + metadata from disk."""
        import faiss

        p = Path(path)
        self._index = faiss.read_index(str(p / "index.faiss"))
        with open(p / "meta.pkl", "rb") as f:
            meta = pickle.load(f)
        self._chunk_ids = meta["chunk_ids"]
        self._texts = meta["texts"]
        self._metadata = meta["metadata"]
        self._is_built = True
        logger.info("faiss_index_loaded", path=str(path), vectors=self._index.ntotal)


# ─── ChromaDB Backend ─────────────────────────────────────────────────────────


class ChromaIndex(VectorIndex):
    """
    ChromaDB persistent vector index.

    Best for: development, small-medium corpora (< 500k vectors).
    Persists automatically; no explicit save() needed.
    Supports metadata filtering natively.

    Args:
        collection_name: Name of the Chroma collection.
        host, port:      ChromaDB server address.
        dim:             Vector dimensions.
    """

    def __init__(
        self,
        collection_name: str,
        host: str = "localhost",
        port: int = 8001,
        dim: int = 1536,
    ) -> None:
        self._collection_name = collection_name
        self._host = host
        self._port = port
        self._dim = dim
        self._collection = None
        self._is_built = False

    @property
    def backend_name(self) -> str:
        return "chromadb"

    @property
    def dimensions(self) -> int:
        return self._dim

    @property
    def is_built(self) -> bool:
        return self._is_built

    def _get_collection(self):
        """Lazy-initialize ChromaDB collection."""
        if self._collection is None:
            import chromadb

            client = chromadb.HttpClient(host=self._host, port=self._port)
            self._collection = client.get_or_create_collection(
                name=self._collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    async def build(
        self,
        chunk_ids: list[str],
        texts: list[str],
        vectors: list[list[float]],
        metadata: list[dict],
    ) -> int:
        """Add vectors to ChromaDB collection in batches."""
        import asyncio

        def _sync_build():
            collection = self._get_collection()
            BATCH = 500
            for i in range(0, len(chunk_ids), BATCH):
                collection.add(
                    ids=chunk_ids[i : i + BATCH],
                    embeddings=vectors[i : i + BATCH],
                    documents=texts[i : i + BATCH],
                    metadatas=metadata[i : i + BATCH],
                )
            return len(chunk_ids)

        count = await asyncio.get_event_loop().run_in_executor(None, _sync_build)
        self._is_built = True
        return count

    async def search(
        self,
        query_vector: list[float],
        top_k: int = 10,
    ) -> list[IndexSearchResult]:
        """Query ChromaDB for top_k nearest neighbors."""
        import asyncio

        def _sync_search():
            collection = self._get_collection()
            results = collection.query(
                query_embeddings=[query_vector],
                n_results=top_k,
                include=["documents", "metadatas", "distances"],
            )
            out = []
            for rank, (cid, doc, meta, dist) in enumerate(
                zip(
                    results["ids"][0],
                    results["documents"][0],
                    results["metadatas"][0],
                    results["distances"][0],
                , strict=False),
                start=1,
            ):
                out.append(
                    IndexSearchResult(
                        chunk_id=cid,
                        text=doc,
                        score=1.0 - dist,  # Chroma returns distance, not similarity
                        rank=rank,
                        metadata=meta or {},
                    )
                )
            return out

        return await asyncio.get_event_loop().run_in_executor(None, _sync_search)

    async def save(self, path: str) -> None:
        """ChromaDB persists automatically — no-op."""
        logger.debug("chromadb_persist_noop")

    async def load(self, path: str) -> None:
        """ChromaDB loads from server — just re-connect."""
        self._collection = None
        self._is_built = True


# ─── IndexRegistry ────────────────────────────────────────────────────────────


class IndexRegistry:
    """
    Registry that manages multiple vector indexes (one per corpus × backend).

    Naming convention: indexes are keyed by "{corpus_id}:{backend}".

    Usage:
        registry = IndexRegistry()

        # Build FAISS index for a corpus
        await registry.build_from_db(
            corpus_id="healthcare_v1",
            backend="faiss",
            embed_model="text-embedding-3-small",
            db=session,
        )

        # Search
        results = await registry.search(
            corpus_id="healthcare_v1",
            backend="faiss",
            query_vector=embed_hub.embed_single("cardiac arrest symptoms"),
            top_k=10,
        )
    """

    def __init__(self) -> None:
        self._indexes: dict[str, VectorIndex] = {}

    def _key(self, corpus_id: str, backend: str) -> str:
        return f"{corpus_id}:{backend}"

    def register(self, corpus_id: str, backend: str, index: VectorIndex) -> None:
        """Manually register a pre-built index."""
        self._indexes[self._key(corpus_id, backend)] = index

    def get(self, corpus_id: str, backend: str) -> VectorIndex | None:
        """Get a registered index, or None if not built."""
        return self._indexes.get(self._key(corpus_id, backend))

    async def build_from_db(
        self,
        corpus_id: str,
        backend: str,
        embed_model: str,
        db: AsyncSession,
        index_kwargs: dict | None = None,
    ) -> VectorIndex:
        """
        Build a vector index from embeddings stored in PostgreSQL.

        Fetches all chunks with non-null embeddings and builds the specified
        backend index. The index is stored in registry memory and can be
        optionally saved to disk.

        Args:
            corpus_id:    Corpus identifier to index.
            backend:      "faiss" or "chromadb".
            embed_model:  Embedding model name (determines dimensions).
            db:           Database session.
            index_kwargs: Extra kwargs for the index constructor.

        Returns:
            Built VectorIndex instance.

        Raises:
            ValueError: If corpus not found or has no embeddings.
        """
        from backend.models.corpus import Chunk, Corpus
        from backend.services.embed_hub import SUPPORTED_MODELS

        start = time.perf_counter()

        # Get corpus
        result = await db.execute(select(Corpus).where(Corpus.corpus_id == corpus_id))
        corpus = result.scalar_one_or_none()
        if corpus is None:
            raise ValueError(f"Corpus '{corpus_id}' not found")

        # Fetch embedded chunks
        chunk_result = await db.execute(
            select(Chunk)
            .where(Chunk.corpus_id == corpus.id)
            .where(Chunk.embedding.isnot(None))
            .order_by(Chunk.chunk_index)
        )
        chunks = chunk_result.scalars().all()

        if not chunks:
            raise ValueError(f"No embedded chunks found for corpus '{corpus_id}'")

        # Determine dimensions from model config
        model_cfg = SUPPORTED_MODELS.get(embed_model)
        dimensions = model_cfg.dimensions if model_cfg else 1536

        # Prepare data arrays
        chunk_ids = [str(c.id) for c in chunks]
        texts = [c.text for c in chunks]
        vectors = [list(c.embedding) for c in chunks]
        metadatas = [c.chunk_metadata or {} for c in chunks]

        # Build the appropriate index
        kwargs = index_kwargs or {}
        if backend == "faiss":
            index = FaissIndex(dim=dimensions, **kwargs)
        elif backend == "chromadb":
            index = ChromaIndex(
                collection_name=f"rl_{corpus_id}",
                dim=dimensions,
                **kwargs,
            )
        else:
            raise ValueError(f"Unknown backend: {backend!r}. Use 'faiss' or 'chromadb'.")

        count = await index.build(chunk_ids, texts, vectors, metadatas)
        self.register(corpus_id, backend, index)

        duration = time.perf_counter() - start
        logger.info(
            "index_built",
            corpus_id=corpus_id,
            backend=backend,
            count=count,
            duration_s=round(duration, 2),
        )

        return index

    async def search(
        self,
        corpus_id: str,
        backend: str,
        query_vector: list[float],
        top_k: int = 10,
    ) -> list[IndexSearchResult]:
        """
        Search a registered index.

        Args:
            corpus_id:    Corpus to search.
            backend:      Which backend index to query.
            query_vector: Dense query embedding.
            top_k:        Number of results to return.

        Returns:
            Ranked list of IndexSearchResult.

        Raises:
            KeyError: If the index hasn't been built yet.
        """
        index = self.get(corpus_id, backend)
        if index is None:
            raise KeyError(
                f"No {backend!r} index for corpus '{corpus_id}'. Call build_from_db() first."
            )
        return await index.search(query_vector, top_k=top_k)
