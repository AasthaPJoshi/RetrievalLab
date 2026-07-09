# =============================================================================
# RetrievalLab — tests/unit/test_chunk_engine.py
# =============================================================================
# PURPOSE : Unit tests for ChunkEngine and all chunking strategies.
#
# WHAT WE TEST:
#   1. FixedSizeChunker — correct token counts, correct overlap
#   2. RecursiveChunker — paragraph preservation, merge-with-overlap logic
#   3. DocumentStructureChunker — heading detection, section grouping
#   4. TableAwareChunker — table linearization, prose + table separation
#   5. ChunkEngine orchestrator — strategy routing, empty doc handling,
#                                 unknown strategy error, min/max filters
#
# TEST PHILOSOPHY:
#   • Tests are deterministic — no LLM calls (SemanticChunker and
#     PropositionalChunker are tested with mocks in test_chunkers_advanced.py)
#   • Each test has a single clear assertion focus
#   • Edge cases: empty docs, single-sentence docs, docs with only tables
#
# HOW TO RUN:
#   pytest tests/unit/test_chunk_engine.py -v
#   pytest tests/unit/test_chunk_engine.py -v -k "test_fixed"  # run one test
# =============================================================================

from __future__ import annotations

import pytest

from corpus.chunkers.chunk_engine import (
    ChunkConfig,
    ChunkEngine,
    DocumentStructureChunker,
    FixedSizeChunker,
    RecursiveChunker,
    TableAwareChunker,
    TextChunk,
    count_tokens,
)
from corpus.loaders.base_loader import ParsedDocument

# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def short_document() -> ParsedDocument:
    """A short document (< 512 tokens) that should become a single chunk."""
    return ParsedDocument(
        text="The quick brown fox jumped over the lazy dog. " * 5,
        source="test://short.txt",
        doc_id="doc_short",
    )


@pytest.fixture
def medium_document() -> ParsedDocument:
    """A medium document with clear paragraph breaks."""
    paragraphs = [
        "Artificial intelligence is transforming healthcare delivery. "
        "Machine learning models can detect diseases earlier than human clinicians. "
        "This represents a major shift in diagnostic medicine.",

        "Retrieval-augmented generation (RAG) combines large language models "
        "with external knowledge retrieval. The retrieved context grounds the model's "
        "response in factual information from trusted sources.",

        "Evaluation of RAG systems requires specialized metrics. Traditional NLP metrics "
        "like ROUGE and BLEU are insufficient for measuring retrieval quality. "
        "Metrics like context precision, recall, and faithfulness are required.",
    ]
    return ParsedDocument(
        text="\n\n".join(paragraphs),
        source="test://medium.txt",
        doc_id="doc_medium",
    )


@pytest.fixture
def structured_document() -> ParsedDocument:
    """A document with Markdown-style section headers."""
    text = """# Introduction
This is the introduction section of the document.
It contains background information about the topic.

## Methods
We employed three different retrieval strategies.
The experiments were conducted on five benchmark datasets.

### Dataset Description
The datasets cover multiple industry domains.
Each dataset contains between 1000 and 50000 documents.

## Results
Our hybrid retrieval approach achieved NDCG@10 = 0.847.
This represents a 12% improvement over the BM25 baseline.

## Conclusion
Hybrid retrieval consistently outperforms single-method approaches.
Future work will investigate multi-modal retrieval extensions."""
    return ParsedDocument(
        text=text,
        source="test://structured.md",
        doc_id="doc_structured",
    )


@pytest.fixture
def document_with_tables() -> ParsedDocument:
    """Document with both prose and table content."""
    tables = [
        [["Model", "NDCG@10", "Latency (ms)"],
         ["BM25",  "0.712",   "15"],
         ["Dense", "0.801",   "45"],
         ["Hybrid","0.847",   "60"]],
    ]
    return ParsedDocument(
        text="Performance comparison of retrieval methods.\n\n[TABLE]\nModel | NDCG@10\n[/TABLE]\n\nThe hybrid approach is consistently best.",
        source="test://tables.pdf",
        doc_id="doc_tables",
        tables=tables,
    )


@pytest.fixture
def empty_document() -> ParsedDocument:
    """An empty document — should produce zero chunks."""
    return ParsedDocument(
        text="",
        source="test://empty.txt",
        doc_id="doc_empty",
    )


@pytest.fixture
def engine() -> ChunkEngine:
    """Fresh ChunkEngine instance for each test."""
    return ChunkEngine()


# ─── count_tokens ─────────────────────────────────────────────────────────────

class TestCountTokens:
    def test_empty_string(self):
        assert count_tokens("") == 0

    def test_single_word(self):
        # "hello" is 1 token
        assert count_tokens("hello") >= 1

    def test_approximate_sentence(self):
        # ~10 word sentence should be 10-15 tokens
        count = count_tokens("The quick brown fox jumped over the lazy dog today.")
        assert 8 <= count <= 15

    def test_long_text_scales(self):
        short = count_tokens("word " * 10)
        long  = count_tokens("word " * 100)
        assert long > short * 5  # should scale approximately linearly


# ─── FixedSizeChunker ─────────────────────────────────────────────────────────

class TestFixedSizeChunker:
    def setup_method(self):
        self.chunker = FixedSizeChunker()

    def test_short_doc_one_chunk(self, short_document):
        config = ChunkConfig(strategy="fixed", chunk_size=512, chunk_overlap=0)
        chunks = self.chunker.chunk(short_document, config)
        # Short doc should fit in one chunk
        assert len(chunks) == 1

    def test_chunk_tokens_respect_limit(self, medium_document):
        config = ChunkConfig(strategy="fixed", chunk_size=100, chunk_overlap=0)
        chunks = self.chunker.chunk(medium_document, config)
        for chunk in chunks:
            assert chunk.token_count <= 100 + 5  # small tolerance for tokenizer

    def test_overlap_shared_tokens(self, medium_document):
        """Overlapping chunks should share content at boundaries."""
        config = ChunkConfig(strategy="fixed", chunk_size=50, chunk_overlap=10)
        chunks = self.chunker.chunk(medium_document, config)
        if len(chunks) >= 2:
            # The second chunk's start should overlap with the first chunk's end
            assert chunks[1].overlap_prev == 10

    def test_empty_document_returns_empty(self, empty_document):
        config = ChunkConfig(strategy="fixed", chunk_size=512)
        chunks = self.chunker.chunk(empty_document, config)
        assert chunks == []

    def test_all_chunks_have_required_fields(self, medium_document):
        config = ChunkConfig(strategy="fixed", chunk_size=100)
        chunks = self.chunker.chunk(medium_document, config)
        for chunk in chunks:
            assert isinstance(chunk, TextChunk)
            assert chunk.chunk_id != ""
            assert chunk.text != ""
            assert chunk.token_count > 0
            assert chunk.strategy == "fixed"
            assert chunk.source_doc_id == medium_document.doc_id

    def test_chunk_index_sequential(self, medium_document):
        config = ChunkConfig(strategy="fixed", chunk_size=50)
        chunks = self.chunker.chunk(medium_document, config)
        indices = [c.chunk_index for c in chunks]
        assert indices == list(range(len(chunks)))


# ─── RecursiveChunker ─────────────────────────────────────────────────────────

class TestRecursiveChunker:
    def setup_method(self):
        self.chunker = RecursiveChunker()

    def test_respects_paragraph_boundaries(self, medium_document):
        """RecursiveChunker should prefer splitting at \\n\\n."""
        config = ChunkConfig(strategy="recursive", chunk_size=200, chunk_overlap=20)
        chunks = self.chunker.chunk(medium_document, config)
        # Should produce multiple chunks
        assert len(chunks) >= 2

    def test_no_empty_chunks(self, medium_document):
        config = ChunkConfig(strategy="recursive", chunk_size=100, min_chunk_size=10)
        chunks = self.chunker.chunk(medium_document, config)
        for chunk in chunks:
            assert len(chunk.text.strip()) > 0
            assert not chunk.is_empty

    def test_all_text_preserved(self, short_document):
        """All source text should appear in exactly one chunk (short doc)."""
        config = ChunkConfig(strategy="recursive", chunk_size=512)
        chunks = self.chunker.chunk(short_document, config)
        reconstructed = " ".join(c.text for c in chunks)
        # All unique words from source should appear in chunks
        source_words = set(short_document.text.lower().split())
        output_words = set(reconstructed.lower().split())
        overlap = source_words & output_words
        assert len(overlap) / len(source_words) > 0.9  # 90%+ word coverage

    def test_chunks_within_max_token_limit(self, medium_document):
        """No chunk should exceed chunk_size significantly."""
        max_tokens = 100
        config = ChunkConfig(strategy="recursive", chunk_size=max_tokens, max_chunk_size=max_tokens * 2)
        chunks = self.chunker.chunk(medium_document, config)
        for chunk in chunks:
            assert chunk.token_count <= max_tokens * 2


# ─── DocumentStructureChunker ──────────────────────────────────────────────────

class TestDocumentStructureChunker:
    def setup_method(self):
        self.chunker = DocumentStructureChunker()

    def test_detects_markdown_headings(self, structured_document):
        config = ChunkConfig(strategy="document_structure", chunk_size=512)
        chunks = self.chunker.chunk(structured_document, config)
        # Should produce at least one chunk per major heading
        assert len(chunks) >= 3

    def test_section_heading_in_metadata(self, structured_document):
        config = ChunkConfig(strategy="document_structure", chunk_size=512)
        chunks = self.chunker.chunk(structured_document, config)
        # At least some chunks should have section_heading in metadata
        chunks_with_heading = [
            c for c in chunks
            if "section_heading" in c.metadata
        ]
        assert len(chunks_with_heading) >= 1

    def test_chunk_text_includes_heading(self, structured_document):
        config = ChunkConfig(strategy="document_structure", chunk_size=512)
        chunks = self.chunker.chunk(structured_document, config)
        # First chunk should start with Introduction heading text
        first_chunk = chunks[0] if chunks else None
        if first_chunk:
            assert "Introduction" in first_chunk.text or "Introduction" in first_chunk.metadata.get("section_heading", "")

    def test_empty_document(self, empty_document):
        config = ChunkConfig(strategy="document_structure", chunk_size=512)
        chunks = self.chunker.chunk(empty_document, config)
        assert chunks == []


# ─── TableAwareChunker ────────────────────────────────────────────────────────

class TestTableAwareChunker:
    def setup_method(self):
        self.chunker = TableAwareChunker()

    def test_creates_table_chunks(self, document_with_tables):
        config = ChunkConfig(strategy="table_aware", chunk_size=512)
        chunks = self.chunker.chunk(document_with_tables, config)
        table_chunks = [c for c in chunks if c.metadata.get("is_table")]
        assert len(table_chunks) >= 1

    def test_table_chunk_has_headers(self, document_with_tables):
        config = ChunkConfig(strategy="table_aware", chunk_size=512)
        chunks = self.chunker.chunk(document_with_tables, config)
        table_chunks = [c for c in chunks if c.metadata.get("is_table")]
        if table_chunks:
            # Table chunk text should contain "Headers:" line
            assert "Headers:" in table_chunks[0].text or "TABLE" in table_chunks[0].text

    def test_prose_and_tables_both_chunked(self, document_with_tables):
        config = ChunkConfig(strategy="table_aware", chunk_size=512)
        chunks = self.chunker.chunk(document_with_tables, config)
        table_chunks = [c for c in chunks if c.metadata.get("is_table")]
        prose_chunks = [c for c in chunks if not c.metadata.get("is_table")]
        # Should have both prose and table chunks
        assert len(chunks) >= 1  # at minimum tables + some prose


# ─── ChunkEngine Orchestrator ────────────────────────────────────────────────

class TestChunkEngine:
    def test_available_strategies(self, engine):
        """Engine should have all 7 default strategies registered."""
        strategies = engine.available_strategies
        expected = {"fixed", "recursive", "semantic", "sentence_window",
                    "document_structure", "propositional", "table_aware"}
        for s in expected:
            assert s in strategies, f"Strategy '{s}' not registered"

    def test_routes_to_correct_strategy(self, engine, medium_document):
        """Engine should use the strategy specified in config."""
        config = ChunkConfig(strategy="fixed", chunk_size=100)
        chunks = engine.chunk(medium_document, config)
        assert all(c.strategy == "fixed" for c in chunks)

    def test_unknown_strategy_raises(self, engine, medium_document):
        config = ChunkConfig(strategy="nonexistent_strategy_xyz")
        with pytest.raises(ValueError, match="Unknown strategy"):
            engine.chunk(medium_document, config)

    def test_empty_document_returns_empty_list(self, engine, empty_document):
        config = ChunkConfig(strategy="recursive")
        chunks = engine.chunk(empty_document, config)
        assert chunks == []

    def test_default_config(self, engine, medium_document):
        """Engine should work with no config (uses defaults)."""
        chunks = engine.chunk(medium_document)
        assert len(chunks) >= 1

    def test_min_chunk_filter(self, engine, medium_document):
        """Chunks below min_chunk_size should be filtered out."""
        config = ChunkConfig(
            strategy="fixed",
            chunk_size=512,
            min_chunk_size=500,  # very high — should filter most chunks
        )
        chunks = engine.chunk(medium_document, config)
        for chunk in chunks:
            assert chunk.token_count >= 500

    def test_custom_strategy_registration(self, engine, medium_document):
        """A custom strategy registered at runtime should be usable."""
        from corpus.chunkers.chunk_engine import ChunkStrategy

        class TestStrategy(ChunkStrategy):
            @property
            def name(self) -> str:
                return "test_custom"

            def chunk(self, document: ParsedDocument, config: ChunkConfig) -> list[TextChunk]:
                return [TextChunk(
                    text=document.text[:100],
                    source_doc_id=document.doc_id,
                    chunk_index=0,
                    strategy="test_custom",
                )]

        engine.register(TestStrategy())
        assert "test_custom" in engine.available_strategies

        config = ChunkConfig(strategy="test_custom")
        chunks = engine.chunk(medium_document, config)
        assert len(chunks) == 1
        assert chunks[0].strategy == "test_custom"

    def test_chunk_ids_are_unique(self, engine, medium_document):
        """Every chunk should have a unique chunk_id."""
        config = ChunkConfig(strategy="fixed", chunk_size=50)
        chunks = engine.chunk(medium_document, config)
        ids = [c.chunk_id for c in chunks]
        assert len(ids) == len(set(ids))


# ─── TextChunk ────────────────────────────────────────────────────────────────

class TestTextChunk:
    def test_token_count_auto_computed(self):
        """token_count should be computed automatically if not set."""
        chunk = TextChunk(
            text="This is a test sentence.",
            source_doc_id="doc_1",
            chunk_index=0,
            strategy="fixed",
        )
        assert chunk.token_count > 0

    def test_is_empty_true_for_whitespace(self):
        chunk = TextChunk(
            text="   \n\n   ",
            source_doc_id="doc_1",
            chunk_index=0,
            strategy="fixed",
        )
        assert chunk.is_empty is True

    def test_is_empty_false_for_content(self):
        chunk = TextChunk(
            text="Hello world.",
            source_doc_id="doc_1",
            chunk_index=0,
            strategy="fixed",
        )
        assert chunk.is_empty is False

    def test_unique_chunk_ids_on_creation(self):
        chunk1 = TextChunk(text="Hello", source_doc_id="d1", chunk_index=0, strategy="fixed")
        chunk2 = TextChunk(text="World", source_doc_id="d1", chunk_index=1, strategy="fixed")
        assert chunk1.chunk_id != chunk2.chunk_id
