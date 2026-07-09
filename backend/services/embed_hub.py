# =============================================================================
# RetrievalLab — backend/services/embed_hub.py
# =============================================================================
# PURPOSE : EmbedHub manages all embedding generation across the platform.
#           It supports multiple embedding providers (OpenAI, Anthropic via
#           Cohere, local HuggingFace models) and caches embeddings in Redis
#           to avoid re-computing the same text multiple times.
#
# WHAT THIS FILE DOES:
#   • Provides a unified embed(texts) interface regardless of provider
#   • Implements Redis-based embedding cache (TTL: 24 hours by default)
#   • Supports batch embedding for efficiency (up to 2048 texts per batch)
#   • Routes to the correct provider based on model name
#   • Embeds all Chunk records in a corpus after ingestion
#   • Updates Chunk.embedding column in PostgreSQL (pgvector)
#
# SUPPORTED MODELS:
#   OpenAI:    text-embedding-3-small (1536d), text-embedding-3-large (3072d)
#   Cohere:    embed-english-v3.0 (1024d), embed-multilingual-v3.0 (1024d)
#   Local:     BAAI/bge-m3 (1024d), paraphrase-MiniLM-L6-v2 (384d), etc.
#   Any sentence-transformers model can be used for local inference.
#
# CACHE STRATEGY:
#   Cache key = sha256(model_name + text)
#   Cache value = JSON-serialized list[float] (the embedding vector)
#   TTL = 24 hours (configurable via EMBED_CACHE_TTL_SECONDS)
#
# HOW TO USE:
#   hub = EmbedHub()
#   vectors = await hub.embed(["query text", "another text"])
#   # or embed a full corpus:
#   await hub.embed_corpus(corpus_id="healthcare_v1", db=session)
#
# INPUT  : List of strings (texts to embed)
# OUTPUT : List of List[float] (embedding vectors, same order as input)
#
# AFTER THIS FILE:
#   Vectors → IndexRegistry (stored in FAISS/Chroma/pgvector) → RetrieverCore
# =============================================================================

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any

import numpy as np
import structlog
from config.settings import get_settings
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)
settings = get_settings()


# ─── Model Configuration ─────────────────────────────────────────────────────


@dataclass
class ModelConfig:
    """Configuration for a single embedding model."""

    name: str  # canonical model name (used as cache key prefix)
    provider: str  # "openai" | "cohere" | "local"
    dimensions: int  # output vector dimensions
    max_batch: int = 512  # max texts per API call
    max_tokens: int = 8191  # max tokens per text (truncate if exceeded)
    requires_key: str | None = None  # env var name for API key


SUPPORTED_MODELS: dict[str, ModelConfig] = {
    # OpenAI models
    "text-embedding-3-small": ModelConfig(
        name="text-embedding-3-small",
        provider="openai",
        dimensions=1536,
        max_batch=2048,
        requires_key="OPENAI_API_KEY",
    ),
    "text-embedding-3-large": ModelConfig(
        name="text-embedding-3-large",
        provider="openai",
        dimensions=3072,
        max_batch=2048,
        requires_key="OPENAI_API_KEY",
    ),
    # Cohere models
    "embed-english-v3.0": ModelConfig(
        name="embed-english-v3.0",
        provider="cohere",
        dimensions=1024,
        max_batch=96,
        requires_key="COHERE_API_KEY",
    ),
    "embed-multilingual-v3.0": ModelConfig(
        name="embed-multilingual-v3.0",
        provider="cohere",
        dimensions=1024,
        max_batch=96,
        requires_key="COHERE_API_KEY",
    ),
    # Local HuggingFace models (no API key needed, runs on CPU/GPU)
    "BAAI/bge-m3": ModelConfig(
        name="BAAI/bge-m3",
        provider="local",
        dimensions=1024,
        max_batch=64,
    ),
    "paraphrase-MiniLM-L6-v2": ModelConfig(
        name="paraphrase-MiniLM-L6-v2",
        provider="local",
        dimensions=384,
        max_batch=256,
    ),
    "all-MiniLM-L6-v2": ModelConfig(
        name="all-MiniLM-L6-v2",
        provider="local",
        dimensions=384,
        max_batch=256,
    ),
}


# ─── EmbedHub ────────────────────────────────────────────────────────────────


class EmbedHub:
    """
    Unified embedding service with multi-provider support and Redis cache.

    Design pattern: Facade — hides the complexity of multiple providers
    behind a single embed() interface.

    Args:
        model_name:  Embedding model to use (must be in SUPPORTED_MODELS).
        cache_ttl:   Redis cache TTL in seconds (default: 24 hours).
        use_cache:   Whether to use Redis cache (disable for testing).

    Example:
        hub = EmbedHub(model_name="text-embedding-3-small")

        # Embed a list of texts
        vectors = await hub.embed(["hello world", "retrieval augmented generation"])
        print(len(vectors))      # 2
        print(len(vectors[0]))   # 1536 (for text-embedding-3-small)

        # Embed an entire corpus (updates DB)
        stats = await hub.embed_corpus(corpus_id="healthcare_v1", db=session)
        print(f"Embedded {stats['embedded']} chunks in {stats['duration_s']:.1f}s")
    """

    def __init__(
        self,
        model_name: str = "text-embedding-3-small",
        cache_ttl: int = 86400,
        use_cache: bool = True,
    ) -> None:
        if model_name not in SUPPORTED_MODELS:
            raise ValueError(
                f"Model {model_name!r} not supported. Available: {list(SUPPORTED_MODELS.keys())}"
            )

        self.model_config = SUPPORTED_MODELS[model_name]
        self.cache_ttl = cache_ttl
        self.use_cache = use_cache
        self._redis = None  # lazy-loaded
        self._local_model = None  # lazy-loaded for local models
        self._log = structlog.get_logger(self.__class__.__name__).bind(model=model_name)

    # ── Public API ────────────────────────────────────────────────────────────

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """
        Embed a list of texts and return their vectors.

        Uses Redis cache: cache hit = instant; cache miss = API call + cache store.
        Handles batching automatically based on model's max_batch setting.

        Args:
            texts: List of text strings to embed. Empty strings are skipped
                   (returns zero vector of correct dimension).

        Returns:
            List of embedding vectors in the same order as input texts.
            Each vector is a list[float] of length model.dimensions.

        Raises:
            RuntimeError: If the embedding API returns an error.
        """
        if not texts:
            return []

        start = time.perf_counter()

        # Separate cached and uncached texts
        cache_keys = [self._cache_key(t) for t in texts]
        cached_vecs = await self._cache_get_many(cache_keys)
        uncached_idx = [i for i, v in enumerate(cached_vecs) if v is None]

        self._log.debug(
            "embed_request",
            total=len(texts),
            cache_hits=len(texts) - len(uncached_idx),
            cache_misses=len(uncached_idx),
        )

        # Fetch uncached vectors from provider
        if uncached_idx:
            uncached_texts = [texts[i] for i in uncached_idx]
            new_vectors = await self._embed_batched(uncached_texts)

            # Store new vectors in cache and results
            for list_idx, vec in zip(uncached_idx, new_vectors, strict=False):
                cached_vecs[list_idx] = vec
                await self._cache_set(cache_keys[list_idx], vec)

        # Fill zero vectors for empty texts
        result: list[list[float]] = []
        for vec in cached_vecs:
            if vec is None:
                result.append([0.0] * self.model_config.dimensions)
            else:
                result.append(vec)

        self._log.info(
            "embed_complete",
            count=len(result),
            duration_ms=round((time.perf_counter() - start) * 1000, 1),
        )
        return result

    async def embed_single(self, text: str) -> list[float]:
        """Convenience method to embed a single text."""
        results = await self.embed([text])
        return results[0]

    async def embed_corpus(
        self,
        corpus_id: str,
        db: AsyncSession,
        batch_size: int = 100,
    ) -> dict[str, Any]:
        """
        Embed all unembedded chunks in a corpus and update PostgreSQL.

        This is called after corpus ingestion completes (CorpusForge sets
        status to READY, then EmbedHub runs to populate the embedding column).

        Args:
            corpus_id:  corpus_id string (e.g., 'healthcare_pubmed_v1').
            db:         Async database session.
            batch_size: How many chunks to embed and commit per batch.

        Returns:
            dict with keys: embedded, skipped, failed, duration_s

        Example:
            stats = await hub.embed_corpus("finance_sec_v1", db=session)
            print(f"Embedded {stats['embedded']} / {stats['embedded'] + stats['skipped']}")
        """
        from datetime import UTC, datetime

        from backend.models.corpus import Chunk, Corpus, CorpusStatus

        start = time.perf_counter()

        # Look up corpus
        result = await db.execute(select(Corpus).where(Corpus.corpus_id == corpus_id))
        corpus = result.scalar_one_or_none()
        if corpus is None:
            raise ValueError(f"Corpus '{corpus_id}' not found")

        # Update status
        corpus.status = CorpusStatus.EMBEDDING
        await db.commit()

        # Fetch unembedded chunks in batches
        offset = 0
        total_embedded = 0
        total_failed = 0

        while True:
            chunk_result = await db.execute(
                select(Chunk)
                .where(Chunk.corpus_id == corpus.id)
                .where(Chunk.embedding.is_(None))  # only unembedded
                .order_by(Chunk.chunk_index)
                .limit(batch_size)
                .offset(offset)
            )
            chunks = chunk_result.scalars().all()

            if not chunks:
                break

            texts = [c.text for c in chunks]

            try:
                vectors = await self.embed(texts)

                for chunk, vector in zip(chunks, vectors, strict=False):
                    chunk.embedding = vector
                    chunk.embedding_model = self.model_config.name
                    chunk.embedding_created_at = datetime.now(UTC)

                await db.commit()
                total_embedded += len(chunks)

                self._log.info(
                    "corpus_embed_batch_done",
                    corpus_id=corpus_id,
                    batch_size=len(chunks),
                    total_so_far=total_embedded,
                )

            except Exception as exc:
                self._log.error("embed_batch_failed", error=str(exc))
                total_failed += len(chunks)
                await db.rollback()

            offset += batch_size

        # Update corpus status back to READY
        corpus.status = CorpusStatus.READY
        await db.commit()

        duration = time.perf_counter() - start
        self._log.info(
            "corpus_embed_complete",
            corpus_id=corpus_id,
            embedded=total_embedded,
            failed=total_failed,
            duration_s=round(duration, 2),
        )

        return {
            "corpus_id": corpus_id,
            "embedded": total_embedded,
            "failed": total_failed,
            "duration_s": round(duration, 2),
        }

    # ── Provider Routing ──────────────────────────────────────────────────────

    async def _embed_batched(self, texts: list[str]) -> list[list[float]]:
        """
        Split texts into provider-appropriate batches and embed each.

        Concatenates results maintaining original order.
        """
        max_batch = self.model_config.max_batch
        all_vectors: list[list[float]] = []

        for i in range(0, len(texts), max_batch):
            batch = texts[i : i + max_batch]
            vectors = await self._embed_provider(batch)
            all_vectors.extend(vectors)

        return all_vectors

    async def _embed_provider(self, texts: list[str]) -> list[list[float]]:
        """Route embedding call to the correct provider."""
        provider = self.model_config.provider

        if provider == "openai":
            return await self._embed_openai(texts)
        elif provider == "cohere":
            return await self._embed_cohere(texts)
        elif provider == "local":
            return await self._embed_local(texts)
        else:
            raise ValueError(f"Unknown provider: {provider!r}")

    async def _embed_openai(self, texts: list[str]) -> list[list[float]]:
        """Embed using OpenAI API (async via httpx)."""
        try:
            from openai import AsyncOpenAI
        except ImportError as err:
            raise ImportError("openai package required: pip install openai") from err

        api_key = settings.llm.openai_api_key
        if api_key is None:
            raise RuntimeError("OPENAI_API_KEY not set in .env")

        client = AsyncOpenAI(api_key=api_key.get_secret_value())
        response = await client.embeddings.create(
            model=self.model_config.name,
            input=texts,
            encoding_format="float",
        )
        # Response items are returned in the same order as input
        return [item.embedding for item in response.data]

    async def _embed_cohere(self, texts: list[str]) -> list[list[float]]:
        """Embed using Cohere API."""
        try:
            import cohere
        except ImportError as err:
            raise ImportError("cohere package required: pip install cohere") from err

        api_key = settings.llm.cohere_api_key
        if api_key is None:
            raise RuntimeError("COHERE_API_KEY not set in .env")

        # Cohere is sync — run in thread pool to avoid blocking event loop
        co = cohere.Client(api_key=api_key.get_secret_value())

        def _sync_embed():
            response = co.embed(
                texts=texts,
                model=self.model_config.name,
                input_type="search_document",
                embedding_types=["float"],
            )
            return [list(e) for e in response.embeddings.float]

        vectors = await asyncio.get_event_loop().run_in_executor(None, _sync_embed)
        return vectors

    async def _embed_local(self, texts: list[str]) -> list[list[float]]:
        """
        Embed using a local sentence-transformers model.

        First call downloads the model (~100-400 MB). Subsequent calls use cache.
        Runs in a thread pool to avoid blocking the async event loop.
        """

        def _sync_encode():
            if self._local_model is None:
                from sentence_transformers import SentenceTransformer

                self._local_model = SentenceTransformer(self.model_config.name)
            vectors = self._local_model.encode(
                texts,
                batch_size=min(self.model_config.max_batch, 64),
                show_progress_bar=False,
                normalize_embeddings=True,
            )
            return vectors.tolist()

        vectors = await asyncio.get_event_loop().run_in_executor(None, _sync_encode)
        return vectors

    # ── Redis Cache ───────────────────────────────────────────────────────────

    async def _get_redis(self):
        """Lazy-initialize Redis connection."""
        if self._redis is None:
            try:
                import redis.asyncio as aioredis

                self._redis = aioredis.from_url(
                    settings.redis.url,
                    encoding="utf-8",
                    decode_responses=True,
                )
            except Exception as exc:
                self._log.warning("redis_unavailable_cache_disabled", error=str(exc))
                self.use_cache = False
                return None
        return self._redis

    def _cache_key(self, text: str) -> str:
        """Generate a deterministic cache key for a text + model combination."""
        content = f"{self.model_config.name}:{text}"
        return f"embed:{hashlib.sha256(content.encode()).hexdigest()}"

    async def _cache_get_many(self, keys: list[str]) -> list[list[float] | None]:
        """Batch-fetch embedding vectors from Redis. Returns None for misses."""
        if not self.use_cache:
            return [None] * len(keys)

        redis = await self._get_redis()
        if redis is None:
            return [None] * len(keys)

        try:
            values = await redis.mget(keys)
            return [json.loads(v) if v is not None else None for v in values]
        except Exception:
            return [None] * len(keys)

    async def _cache_set(self, key: str, vector: list[float]) -> None:
        """Store an embedding vector in Redis with TTL."""
        if not self.use_cache:
            return

        redis = await self._get_redis()
        if redis is None:
            return

        try:
            await redis.setex(key, self.cache_ttl, json.dumps(vector))
        except Exception as exc:
            self._log.debug("cache_set_failed", error=str(exc))

    async def similarity(
        self,
        vec_a: list[float],
        vec_b: list[float],
    ) -> float:
        """Compute cosine similarity between two embedding vectors."""
        a = np.array(vec_a, dtype=np.float32)
        b = np.array(vec_b, dtype=np.float32)
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))
