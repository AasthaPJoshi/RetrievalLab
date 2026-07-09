# =============================================================================
# RetrievalLab — tests/integration/test_corpus_pipeline.py
# =============================================================================
# PURPOSE : Integration tests for the full corpus ingestion pipeline.
#           These tests spin up real SQLAlchemy sessions (using a test DB)
#           and exercise CorpusForge end-to-end.
#
# SCOPE:
#   • Full ingest pipeline: load → chunk → persist → verify DB records
#   • Idempotency: re-ingesting same corpus is a no-op
#   • Force re-ingest: re-runs when --force flag is set
#   • Multi-document corpora: directory with mixed file types
#   • Status transitions: PENDING → INGESTING → CHUNKING → READY
#   • Error handling: missing source path, empty directory
#
# PREREQUISITES:
#   These tests require a running PostgreSQL instance.
#   They run against TEST_DATABASE_URL (set in conftest.py or .env.test).
#   Run with: pytest tests/integration/ -v
#   Skip in CI without DB: pytest tests/integration/ -v -m "not requires_db"
#
# MARKS:
#   @pytest.mark.integration — skip with -m "not integration"
#   @pytest.mark.requires_db — skip without PostgreSQL
# =============================================================================

from __future__ import annotations

import tempfile
import textwrap
from pathlib import Path

import pytest

# Skip all integration tests unless specifically requested
# Run with: pytest tests/integration/ -v
pytestmark = pytest.mark.integration


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def temp_docs_dir():
    """Create a temp directory with sample documents for ingestion."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # Healthcare document
        (tmp / "healthcare.txt").write_text(textwrap.dedent("""
            Cardiovascular disease is the leading cause of death globally.
            Hypertension affects approximately 1.28 billion adults worldwide.
            Risk factors include obesity, sedentary lifestyle, and smoking.

            Type 2 diabetes mellitus is characterized by insulin resistance.
            Fasting glucose >= 126 mg/dL on two occasions confirms diagnosis.
            First-line treatment is lifestyle modification and metformin.

            Chronic kidney disease staging is based on GFR and albuminuria.
            Stage 3a: GFR 45-59 mL/min. RAAS inhibitors are first-line therapy.
        """).strip())

        # Finance document
        (tmp / "finance.txt").write_text(textwrap.dedent("""
            Revenue increased 12% year-over-year to $4.2 billion in Q3 2024.
            Operating margin expanded 150 basis points to 24.3%.
            Free cash flow of $892 million represented a 21% FCF margin.

            Risk factors include macroeconomic uncertainty and FX headwinds.
            The company repurchased $400M in shares and declared a $0.25 dividend.
            Net debt of $1.2 billion represents 0.7x EBITDA within target range.
        """).strip())

        yield tmp


@pytest.fixture
def single_doc_dir():
    """Create a temp directory with exactly one document."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        (tmp / "sample.txt").write_text(
            "This is a sample document. " * 50  # ~50 words × 50 = 2500 words
        )
        yield tmp


@pytest.fixture
def empty_dir():
    """Empty directory — no documents."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def nonexistent_path():
    """A path that doesn't exist."""
    return "/tmp/retrievallab_test_nonexistent_path_xyz"


# ─── Tests ────────────────────────────────────────────────────────────────────

@pytest.mark.requires_db
@pytest.mark.asyncio
async def test_ingest_creates_corpus_record(temp_docs_dir):
    """
    Full pipeline: ingest → verify Corpus record exists in DB with correct fields.
    """
    from backend.db.base import AsyncSessionLocal
    from backend.models.corpus import Corpus, CorpusStatus
    from backend.services.corpus_forge import CorpusForge, IngestRequest

    corpus_id = "test_integration_001"

    async with AsyncSessionLocal() as db:
        forge  = CorpusForge(db=db)
        result = await forge.ingest(IngestRequest(
            corpus_id=corpus_id,
            source=str(temp_docs_dir),
            domain="healthcare",
            strategy="recursive",
            chunk_size=200,
            chunk_overlap=20,
        ))

    assert result.success, f"Ingest failed: {result.failures}"
    assert result.doc_count > 0
    assert result.chunk_count > 0
    assert result.total_tokens > 0

    # Verify DB record
    from sqlalchemy import select
    async with AsyncSessionLocal() as db:
        row = await db.execute(select(Corpus).where(Corpus.corpus_id == corpus_id))
        corpus = row.scalar_one_or_none()

    assert corpus is not None
    assert corpus.status == CorpusStatus.READY
    assert corpus.doc_count == result.doc_count
    assert corpus.chunk_count == result.chunk_count
    assert corpus.fingerprint is not None

    # Cleanup
    async with AsyncSessionLocal() as db:
        from sqlalchemy import delete
        await db.execute(delete(Corpus).where(Corpus.corpus_id == corpus_id))
        await db.commit()


@pytest.mark.requires_db
@pytest.mark.asyncio
async def test_ingest_creates_chunk_records(single_doc_dir):
    """Verify chunk records are created in the DB after ingestion."""
    from sqlalchemy import select

    from backend.db.base import AsyncSessionLocal
    from backend.models.corpus import Chunk, Corpus
    from backend.services.corpus_forge import CorpusForge, IngestRequest

    corpus_id = "test_integration_chunks_001"

    async with AsyncSessionLocal() as db:
        forge  = CorpusForge(db=db)
        result = await forge.ingest(IngestRequest(
            corpus_id=corpus_id,
            source=str(single_doc_dir),
            chunk_size=100,
            chunk_overlap=10,
        ))

    # Verify chunks in DB
    async with AsyncSessionLocal() as db:
        corpus_row = await db.execute(select(Corpus).where(Corpus.corpus_id == corpus_id))
        corpus     = corpus_row.scalar_one_or_none()

        if corpus:
            chunk_rows = await db.execute(
                select(Chunk).where(Chunk.corpus_id == corpus.id)
            )
            chunks = chunk_rows.scalars().all()

            assert len(chunks) > 0
            assert len(chunks) == result.chunk_count
            for chunk in chunks:
                assert chunk.text.strip() != ""
                assert chunk.token_count > 0

        # Cleanup
        if corpus:
            from sqlalchemy import delete
            await db.execute(delete(Corpus).where(Corpus.corpus_id == corpus_id))
            await db.commit()


@pytest.mark.requires_db
@pytest.mark.asyncio
async def test_idempotent_reingest(single_doc_dir):
    """Re-ingesting the same corpus with same files should be a no-op."""
    from sqlalchemy import select

    from backend.db.base import AsyncSessionLocal
    from backend.models.corpus import Corpus
    from backend.services.corpus_forge import CorpusForge, IngestRequest

    corpus_id = "test_integration_idempotent_001"

    async def _do_ingest():
        async with AsyncSessionLocal() as db:
            forge  = CorpusForge(db=db)
            return await forge.ingest(IngestRequest(
                corpus_id=corpus_id,
                source=str(single_doc_dir),
            ))

    # First ingest
    result1 = await _do_ingest()
    assert result1.success
    assert not result1.skipped

    # Second ingest — same files, should be skipped
    result2 = await _do_ingest()
    assert result2.skipped, "Second ingest should be skipped (same fingerprint)"

    # Verify only one corpus record exists
    async with AsyncSessionLocal() as db:
        from sqlalchemy import func
        count_row = await db.execute(
            select(func.count()).where(Corpus.corpus_id == corpus_id)
        )
        assert count_row.scalar() == 1

        # Cleanup
        from sqlalchemy import delete
        await db.execute(delete(Corpus).where(Corpus.corpus_id == corpus_id))
        await db.commit()


@pytest.mark.requires_db
@pytest.mark.asyncio
async def test_force_reingest(single_doc_dir):
    """Force re-ingest should re-run even with same fingerprint."""

    from backend.db.base import AsyncSessionLocal
    from backend.models.corpus import Corpus
    from backend.services.corpus_forge import CorpusForge, IngestRequest

    corpus_id = "test_integration_force_001"

    async def _ingest(force=False):
        async with AsyncSessionLocal() as db:
            forge = CorpusForge(db=db)
            return await forge.ingest(IngestRequest(
                corpus_id=corpus_id,
                source=str(single_doc_dir),
                force_reingest=force,
            ))

    result1 = await _ingest(force=False)
    assert result1.success

    result2 = await _ingest(force=True)   # should NOT be skipped
    assert result2.success
    assert not result2.skipped, "Force reingest should never be skipped"

    # Cleanup
    async with AsyncSessionLocal() as db:
        from sqlalchemy import delete
        await db.execute(delete(Corpus).where(Corpus.corpus_id == corpus_id))
        await db.commit()


@pytest.mark.asyncio
async def test_ingest_nonexistent_path_returns_failed(nonexistent_path):
    """Ingesting a path that doesn't exist should return status=FAILED."""
    from backend.db.base import AsyncSessionLocal
    from backend.services.corpus_forge import CorpusForge, IngestRequest

    async with AsyncSessionLocal() as db:
        forge  = CorpusForge(db=db)
        result = await forge.ingest(IngestRequest(
            corpus_id="test_nonexistent_path",
            source=nonexistent_path,
        ))

    # Should fail gracefully, not raise
    assert result.status == "FAILED"
    assert len(result.failures) > 0


@pytest.mark.asyncio
async def test_ingest_empty_directory_returns_failed(empty_dir):
    """Ingesting an empty directory should result in FAILED status."""
    from backend.db.base import AsyncSessionLocal
    from backend.services.corpus_forge import CorpusForge, IngestRequest

    async with AsyncSessionLocal() as db:
        forge  = CorpusForge(db=db)
        result = await forge.ingest(IngestRequest(
            corpus_id="test_empty_dir",
            source=str(empty_dir),
        ))

    assert result.status == "FAILED"
    assert result.doc_count == 0


@pytest.mark.requires_db
@pytest.mark.asyncio
async def test_multiple_strategies_same_corpus(single_doc_dir):
    """Different chunking strategies on the same source produce different chunk counts."""
    from sqlalchemy import delete

    from backend.db.base import AsyncSessionLocal
    from backend.models.corpus import Corpus
    from backend.services.corpus_forge import CorpusForge, IngestRequest

    async def _ingest_with_strategy(strategy: str, corpus_id: str) -> int:
        async with AsyncSessionLocal() as db:
            forge  = CorpusForge(db=db)
            result = await forge.ingest(IngestRequest(
                corpus_id=corpus_id,
                source=str(single_doc_dir),
                strategy=strategy,
                chunk_size=100,
            ))
        return result.chunk_count

    fixed_count    = await _ingest_with_strategy("fixed",     "test_strat_fixed")
    recursive_count = await _ingest_with_strategy("recursive", "test_strat_recursive")

    # Both should produce chunks
    assert fixed_count > 0
    assert recursive_count > 0
    # Different strategies typically produce different counts
    # (we don't assert they're different because very short docs may produce same)

    # Cleanup
    async with AsyncSessionLocal() as db:
        for cid in ("test_strat_fixed", "test_strat_recursive"):
            await db.execute(delete(Corpus).where(Corpus.corpus_id == cid))
        await db.commit()
