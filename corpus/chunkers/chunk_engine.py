# =============================================================================
# RetrievalLab — corpus/chunkers/chunk_engine.py
# =============================================================================
# PURPOSE : ChunkEngine is the central chunking system. It accepts a
#           ParsedDocument and a strategy name, runs the appropriate algorithm,
#           and returns a list of TextChunk dataclasses ready for embedding.
#
# ARCHITECTURE:
#   ChunkEngine (orchestrator)
#     └─ ChunkStrategy (protocol/ABC)
#          ├─ FixedSizeChunker
#          ├─ RecursiveChunker     ← default for general corpora
#          ├─ SemanticChunker      ← best quality, slowest
#          ├─ SentenceWindowChunker
#          ├─ RaptorChunker        ← hierarchical (multi-level summaries)
#          ├─ PropositionalChunker ← finest granularity via LLM decomposition
#          ├─ DocumentStructureChunker ← respects PDF/DOCX heading hierarchy
#          ├─ LateChunker          ← encode-then-split (best for long docs)
#          ├─ CodeAwareChunker     ← AST-based for code documentation
#          └─ TableAwareChunker    ← linearizes tables as structured chunks
#
# ALL STRATEGIES share the TextChunk output format, so evaluation code never
# needs to know which strategy was used.
#
# INPUT  : ParsedDocument (from any loader) + ChunkConfig
# OUTPUT : List[TextChunk] — enriched chunks with metadata and overlap tracking
#
# AFTER THIS FILE:
#   TextChunks go to → EmbedHub (vectorization) → IndexRegistry (storage)
#   Then retrieved by → RetrieverCore (Day 2)
# =============================================================================

from __future__ import annotations

import abc
import uuid
from dataclasses import dataclass, field
from typing import Any

import structlog
import tiktoken

from corpus.loaders.base_loader import ParsedDocument

logger = structlog.get_logger(__name__)

# ─── Tokenizer (shared across all strategies) ────────────────────────────────
# cl100k_base is the tokenizer for text-embedding-3-* and GPT-4 models.
# All chunk sizes are measured in tokens, not characters, for model compatibility.
_TOKENIZER = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    """Count tokens in text using cl100k_base tokenizer."""
    return len(_TOKENIZER.encode(text))


def truncate_to_tokens(text: str, max_tokens: int) -> str:
    """Truncate text to a maximum number of tokens."""
    tokens = _TOKENIZER.encode(text)
    if len(tokens) <= max_tokens:
        return text
    return _TOKENIZER.decode(tokens[:max_tokens])


# ─── Output Data Class ────────────────────────────────────────────────────────


@dataclass
class TextChunk:
    """
    A single text chunk ready for embedding and indexing.

    This is the atomic unit passed to EmbedHub and then stored in vector DBs.
    Carries enough metadata to reconstruct provenance and support evaluation.

    Attributes:
        chunk_id:      Unique identifier (UUID v4).
        text:          Chunk text content (cleaned, ready for embedding).
        token_count:   Number of tokens (cl100k_base). Pre-computed here.
        source_doc_id: Identifier of the source document.
        chunk_index:   Position within the source document (0-indexed).
        strategy:      Name of the chunking strategy that produced this chunk.
        metadata:      Strategy-specific metadata (page number, heading, etc.).
        overlap_prev:  Number of tokens shared with the previous chunk.
        overlap_next:  Number of tokens shared with the next chunk.
        parent_id:     For hierarchical strategies: ID of parent/summary chunk.
        level:         For RAPTOR: tree level (0 = leaf, 1 = summary, 2 = abstract).
    """

    text: str
    source_doc_id: str
    chunk_index: int
    strategy: str
    chunk_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    token_count: int = field(default=0)
    metadata: dict[str, Any] = field(default_factory=dict)
    overlap_prev: int = field(default=0)
    overlap_next: int = field(default=0)
    parent_id: str | None = field(default=None)
    level: int = field(default=0)

    def __post_init__(self) -> None:
        if self.token_count == 0:
            self.token_count = count_tokens(self.text)

    @property
    def is_empty(self) -> bool:
        return len(self.text.strip()) == 0

    def __repr__(self) -> str:
        preview = self.text[:80].replace("\n", " ") + "..."
        return (
            f"TextChunk(idx={self.chunk_index}, "
            f"tokens={self.token_count}, "
            f"strategy={self.strategy!r}, "
            f"text={preview!r})"
        )


@dataclass
class ChunkConfig:
    """
    Configuration for a chunking run.

    Passed to ChunkEngine.chunk() to parameterize the chosen strategy.

    All size values are in TOKENS (not characters) for model compatibility.
    """

    strategy: str = "recursive"  # strategy name
    chunk_size: int = 512  # target chunk size in tokens
    chunk_overlap: int = 64  # overlap tokens between consecutive chunks
    min_chunk_size: int = 50  # discard chunks smaller than this
    max_chunk_size: int = 1024  # hard cap; truncate if exceeded

    # Semantic chunker settings
    breakpoint_threshold: float = 0.85  # cosine similarity threshold for boundaries
    buffer_size: int = 1  # sentences on each side of boundary

    # Sentence window settings
    window_size: int = 3  # sentences around the anchor sentence

    # RAPTOR settings
    max_raptor_levels: int = 3  # maximum summary tree depth
    raptor_cluster_size: int = 5  # chunks per summary cluster

    # Code-aware settings
    code_language: str = "python"  # "python" | "javascript" | "java" | ...

    # Extra strategy-specific settings
    extra: dict[str, Any] = field(default_factory=dict)


# ─── Abstract Strategy Protocol ──────────────────────────────────────────────


class ChunkStrategy(abc.ABC):
    """
    Abstract base class for all chunking strategies.

    All strategies must implement chunk() — ChunkEngine calls this.
    Strategies should NOT filter by min_chunk_size; ChunkEngine does that.
    """

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Strategy identifier used in config files and DB records."""
        ...

    @abc.abstractmethod
    def chunk(self, document: ParsedDocument, config: ChunkConfig) -> list[TextChunk]:
        """
        Split document.text into a list of TextChunk objects.

        Args:
            document: Parsed document with text and metadata.
            config:   Chunking configuration parameters.

        Returns:
            Ordered list of TextChunk objects (may be empty if doc is empty).
        """
        ...

    def _make_chunk(
        self,
        text: str,
        doc: ParsedDocument,
        index: int,
        extra_meta: dict | None = None,
    ) -> TextChunk:
        """Convenience factory for building TextChunk with common fields."""
        meta = {
            "source_doc_title": doc.metadata.get("title", ""),
            "source_doc_domain": doc.metadata.get("domain", ""),
            **(extra_meta or {}),
        }
        return TextChunk(
            text=text,
            source_doc_id=doc.doc_id,
            chunk_index=index,
            strategy=self.name,
            metadata=meta,
        )


# ─── Strategy Implementations ─────────────────────────────────────────────────


class FixedSizeChunker(ChunkStrategy):
    """
    Naive fixed-size character-level chunking with token-counted overlap.

    Use case: Baseline comparison. Not recommended for production retrieval.

    Algorithm:
        1. Encode text to tokens.
        2. Slice tokens in windows of (chunk_size) with (overlap) step.
        3. Decode each window back to text.
    """

    @property
    def name(self) -> str:
        return "fixed"

    def chunk(self, document: ParsedDocument, config: ChunkConfig) -> list[TextChunk]:
        tokens = _TOKENIZER.encode(document.text)
        step = config.chunk_size - config.chunk_overlap
        chunks: list[TextChunk] = []

        for i, start in enumerate(range(0, len(tokens), step)):
            end = min(start + config.chunk_size, len(tokens))
            chunk_tokens = tokens[start:end]
            text = _TOKENIZER.decode(chunk_tokens)

            chunk = self._make_chunk(text, document, i)
            chunk.overlap_prev = config.chunk_overlap if i > 0 else 0
            chunks.append(chunk)

            if end >= len(tokens):
                break

        return chunks


class RecursiveChunker(ChunkStrategy):
    """
    Recursive character splitting with hierarchical delimiter fallback.

    This is the DEFAULT strategy for most corpora.

    Algorithm:
        Tries to split on paragraph breaks (\\n\\n), then sentences (.!?\\n),
        then words (spaces), then characters — recursively halving until
        chunks are within the target token range.

    Why it works well:
        Keeps semantically coherent units together (paragraphs > sentences > words),
        only splitting at coarser boundaries when finer splits won't help.
    """

    SEPARATORS = ["\n\n", "\n", ". ", "! ", "? ", " ", ""]

    @property
    def name(self) -> str:
        return "recursive"

    def chunk(self, document: ParsedDocument, config: ChunkConfig) -> list[TextChunk]:
        raw_chunks = self._recursive_split(document.text, config)
        chunks = []

        for i, text in enumerate(raw_chunks):
            if not text.strip():
                continue
            chunk = self._make_chunk(text.strip(), document, i)
            if i > 0:
                chunk.overlap_prev = config.chunk_overlap
            chunks.append(chunk)

        return chunks

    def _recursive_split(self, text: str, config: ChunkConfig, depth: int = 0) -> list[str]:
        """Recursively split text using separator hierarchy."""
        if count_tokens(text) <= config.chunk_size:
            return [text] if text.strip() else []

        if depth >= len(self.SEPARATORS):
            # Last resort: hard truncate
            return [truncate_to_tokens(text, config.chunk_size)]

        sep = self.SEPARATORS[depth]
        if sep:
            parts = text.split(sep)
        else:
            # Character-level split
            mid = len(text) // 2
            parts = [text[:mid], text[mid:]]

        result: list[str] = []
        current = ""

        for part in parts:
            candidate = (current + sep + part).strip() if current else part
            if count_tokens(candidate) <= config.chunk_size:
                current = candidate
            else:
                if current:
                    result.extend(self._recursive_split(current, config, depth + 1))
                current = part

        if current:
            result.extend(self._recursive_split(current, config, depth + 1))

        # Merge short fragments with overlap
        return self._merge_with_overlap(result, config)

    def _merge_with_overlap(self, chunks: list[str], config: ChunkConfig) -> list[str]:
        """
        Merge consecutive short chunks and add overlap.

        Small fragments below min_chunk_size are merged with the next chunk.
        Overlap is added by appending the start of the next chunk to the end
        of the current chunk (up to overlap tokens).
        """
        if not chunks:
            return []

        merged: list[str] = []
        buffer = chunks[0]

        for next_chunk in chunks[1:]:
            if count_tokens(buffer) < config.min_chunk_size:
                buffer = buffer + " " + next_chunk
            else:
                merged.append(buffer)
                # Add overlap: take first `chunk_overlap` tokens of buffer
                overlap_tokens = _TOKENIZER.encode(buffer)[-config.chunk_overlap :]
                overlap_text = _TOKENIZER.decode(overlap_tokens)
                buffer = overlap_text + " " + next_chunk

        if buffer:
            merged.append(buffer)

        return merged


class SemanticChunker(ChunkStrategy):
    """
    Embedding-based semantic chunking using sentence cosine similarity.

    Algorithm (Stanford NLP-inspired):
        1. Split text into sentences using spaCy.
        2. Embed each sentence using a lightweight model (paraphrase-MiniLM).
        3. Compute cosine similarity between adjacent sentence embeddings.
        4. Identify semantic breakpoints where similarity drops below threshold.
        5. Group sentences between breakpoints into chunks.

    Quality: Highest semantic coherence of all non-LLM strategies.
    Speed: 3-5x slower than RecursiveChunker due to embedding step.

    Best for:
        - Dense prose (narrative, explanations, clinical notes)
        - Long documents with topic shifts
    """

    @property
    def name(self) -> str:
        return "semantic"

    def chunk(self, document: ParsedDocument, config: ChunkConfig) -> list[TextChunk]:
        try:
            import numpy as np
            import spacy
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            logger.warning("semantic_chunker_fallback", reason=str(e))
            return RecursiveChunker().chunk(document, config)

        # Use a fast, small model for breakpoint detection
        model = SentenceTransformer("paraphrase-MiniLM-L6-v2")

        # Load spaCy for sentence tokenization
        nlp = spacy.load("en_core_web_sm")
        nlp.max_length = 2_000_000

        doc = nlp(document.text[:1_000_000])  # cap for memory safety
        sentences = [sent.text.strip() for sent in doc.sents if sent.text.strip()]

        if len(sentences) <= 1:
            return RecursiveChunker().chunk(document, config)

        # Embed all sentences in one batch (much faster than one-by-one)
        embeddings = model.encode(sentences, batch_size=64, show_progress_bar=False)

        # Compute cosine similarities between adjacent sentences
        def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
            return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))

        similarities = [
            cosine_sim(embeddings[i], embeddings[i + 1]) for i in range(len(embeddings) - 1)
        ]

        # Identify breakpoints: similarity below threshold = topic change
        breakpoints: set[int] = set()
        for i, sim in enumerate(similarities):
            if sim < config.breakpoint_threshold:
                breakpoints.add(i + 1)

        # Group sentences into chunks
        chunks: list[TextChunk] = []
        chunk_sentences: list[str] = []
        chunk_idx = 0

        for i, sentence in enumerate(sentences):
            if i in breakpoints and chunk_sentences:
                chunk_text = " ".join(chunk_sentences)
                if count_tokens(chunk_text) > config.min_chunk_size:
                    chunks.append(
                        self._make_chunk(
                            chunk_text,
                            document,
                            chunk_idx,
                            {"breakpoint_before": True, "sentence_count": len(chunk_sentences)},
                        )
                    )
                    chunk_idx += 1
                chunk_sentences = []
            chunk_sentences.append(sentence)

        # Last group
        if chunk_sentences:
            chunk_text = " ".join(chunk_sentences)
            if chunk_text.strip():
                chunks.append(
                    self._make_chunk(
                        chunk_text,
                        document,
                        chunk_idx,
                        {"sentence_count": len(chunk_sentences)},
                    )
                )

        return chunks


class SentenceWindowChunker(ChunkStrategy):
    """
    Sentence-window chunking: each chunk is one anchor sentence + N surrounding sentences.

    This produces many overlapping chunks (one per sentence) but gives
    retrieval models precise context around the key sentence.

    Algorithm:
        For each sentence s_i, the chunk = sentences[i-N : i+N+1]
        The "anchor" is s_i; surrounding sentences provide context.

    Best for:
        - Factoid Q&A where exact sentence matters
        - Legal retrieval (specific clauses need surrounding context)
    """

    @property
    def name(self) -> str:
        return "sentence_window"

    def chunk(self, document: ParsedDocument, config: ChunkConfig) -> list[TextChunk]:
        try:
            import spacy
        except ImportError:
            logger.warning("sentence_window_fallback_to_recursive")
            return RecursiveChunker().chunk(document, config)

        nlp = spacy.load("en_core_web_sm")
        nlp.max_length = 2_000_000
        spacy_doc = nlp(document.text[:1_000_000])
        sentences = [s.text.strip() for s in spacy_doc.sents if s.text.strip()]

        chunks: list[TextChunk] = []
        w = config.window_size  # N sentences on each side

        for i, anchor_sentence in enumerate(sentences):
            start = max(0, i - w)
            end = min(len(sentences), i + w + 1)
            window_text = " ".join(sentences[start:end])

            if count_tokens(window_text) < config.min_chunk_size:
                continue

            chunks.append(
                self._make_chunk(
                    window_text,
                    document,
                    i,
                    {
                        "anchor_sentence": anchor_sentence,
                        "anchor_index": i,
                        "window_start": start,
                        "window_end": end - 1,
                    },
                )
            )

        return chunks


class DocumentStructureChunker(ChunkStrategy):
    """
    Structure-aware chunking that respects document headings and sections.

    Uses regex heuristics to detect section headers (## Title, SECTION 1, etc.)
    and splits at heading boundaries, then recursively splits oversized sections.

    Best for:
        - PDFs with clear heading hierarchy (annual reports, SOPs, textbooks)
        - DOCX files with named sections
        - Legal documents with numbered sections
    """

    # Patterns that indicate a new section header
    HEADING_PATTERNS = [
        r"^#{1,6}\s+.+$",  # Markdown headings
        r"^[A-Z][A-Z\s]{4,}$",  # ALL CAPS headings
        r"^\d+\.\s+[A-Z].+$",  # "1. Introduction"
        r"^(Section|Article|Chapter)\s+\d+",  # "Section 3: ..."
        r"^[IVX]+\.\s+[A-Z].+$",  # Roman numerals
    ]

    @property
    def name(self) -> str:
        return "document_structure"

    def chunk(self, document: ParsedDocument, config: ChunkConfig) -> list[TextChunk]:
        import re

        heading_re = re.compile(
            "|".join(self.HEADING_PATTERNS),
            flags=re.MULTILINE,
        )

        lines = document.text.split("\n")
        sections: list[tuple[str, list[str]]] = []  # (heading, lines)
        current_heading = "Introduction"
        current_lines: list[str] = []

        for line in lines:
            if heading_re.match(line.strip()):
                if current_lines:
                    sections.append((current_heading, current_lines))
                current_heading = line.strip()
                current_lines = []
            else:
                current_lines.append(line)

        if current_lines:
            sections.append((current_heading, current_lines))

        # Convert sections to chunks; split oversized sections recursively
        chunks: list[TextChunk] = []
        recursive = RecursiveChunker()
        chunk_idx = 0

        for heading, section_lines in sections:
            section_text = "\n".join(section_lines).strip()
            if not section_text:
                continue

            full_text = f"{heading}\n{section_text}"

            if count_tokens(full_text) <= config.chunk_size:
                chunks.append(
                    self._make_chunk(
                        full_text,
                        document,
                        chunk_idx,
                        {"section_heading": heading},
                    )
                )
                chunk_idx += 1
            else:
                # Recursively split large sections
                sub_doc = type(document)(
                    text=section_text,
                    source=document.source,
                    doc_id=document.doc_id,
                    metadata={**document.metadata, "current_section": heading},
                )
                sub_chunks = recursive.chunk(sub_doc, config)
                for sc in sub_chunks:
                    sc.chunk_index = chunk_idx
                    sc.metadata["section_heading"] = heading
                    chunks.append(sc)
                    chunk_idx += 1

        return chunks


class PropositionalChunker(ChunkStrategy):
    """
    LLM-powered chunking into atomic propositions (factual statements).

    Uses an LLM to decompose each paragraph into independent, self-contained
    factual claims. Each claim becomes a chunk.

    Example:
        Input:  "Einstein, born in 1879 in Germany, developed special relativity."
        Output: ["Einstein was born in 1879.", "Einstein was born in Germany.",
                 "Einstein developed special relativity."]

    Quality: Best for factoid Q&A benchmarks (NQ, TriviaQA, PopQA).
    Speed: Slowest strategy — requires one LLM call per paragraph.
    Cost: ~$0.01-0.05 per document depending on length.

    NOTE: Requires OPENAI_API_KEY or ANTHROPIC_API_KEY in .env
    """

    SYSTEM_PROMPT = """You are a text decomposition expert. Given a paragraph,
extract all atomic propositions (self-contained factual statements).
Return a JSON array of strings. Each string must be:
- A single complete sentence
- Self-contained (makes sense without the paragraph)
- Factual (not a question, not a command)
Return ONLY valid JSON, no other text."""

    @property
    def name(self) -> str:
        return "propositional"

    def chunk(self, document: ParsedDocument, config: ChunkConfig) -> list[TextChunk]:
        import json

        try:
            from anthropic import Anthropic

            client = Anthropic()
        except Exception:
            logger.warning("propositional_chunker_no_llm_falling_back")
            return RecursiveChunker().chunk(document, config)

        # First split into paragraphs
        paragraphs = [p.strip() for p in document.text.split("\n\n") if p.strip()]
        chunks: list[TextChunk] = []
        chunk_idx = 0

        for para in paragraphs:
            if count_tokens(para) < 30:
                # Too short to decompose — keep as-is
                chunks.append(self._make_chunk(para, document, chunk_idx))
                chunk_idx += 1
                continue

            try:
                response = client.messages.create(
                    model="claude-3-5-haiku-20241022",
                    max_tokens=1024,
                    system=self.SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": para}],
                )
                propositions = json.loads(response.content[0].text)
                for prop in propositions:
                    if isinstance(prop, str) and prop.strip():
                        chunks.append(
                            self._make_chunk(
                                prop.strip(),
                                document,
                                chunk_idx,
                                {"source_paragraph": para[:200]},
                            )
                        )
                        chunk_idx += 1
            except Exception as exc:
                logger.warning("proposition_extraction_failed", error=str(exc))
                # Fallback: add paragraph as-is
                chunks.append(self._make_chunk(para, document, chunk_idx))
                chunk_idx += 1

        return chunks


class TableAwareChunker(ChunkStrategy):
    """
    Table-aware chunking that linearizes tables as structured text chunks.

    For documents with tables (financial reports, regulatory filings, data sheets):
    1. Extract table content as header + rows narrative.
    2. Create a dedicated chunk per table.
    3. Non-table text gets recursive chunking.

    Output format for tables:
        "TABLE: [title]
         Headers: Col1 | Col2 | Col3
         Row 1: Val1 | Val2 | Val3
         ..."

    Best for: 10-K filings, clinical trial reports, scientific papers with data.
    """

    @property
    def name(self) -> str:
        return "table_aware"

    def chunk(self, document: ParsedDocument, config: ChunkConfig) -> list[TextChunk]:
        chunks: list[TextChunk] = []
        recursive = RecursiveChunker()
        chunk_idx = 0

        # First: chunk non-table text recursively
        text_without_tables = document.text
        # Remove [TABLE]...[/TABLE] markers (added by DocxLoader)
        import re

        table_blocks = re.findall(r"\[TABLE\](.*?)\[/TABLE\]", text_without_tables, re.DOTALL)
        text_without_tables = re.sub(
            r"\[TABLE\].*?\[/TABLE\]", "", text_without_tables, flags=re.DOTALL
        )

        # Chunk the prose text
        prose_doc = type(document)(
            text=text_without_tables.strip(),
            source=document.source,
            doc_id=document.doc_id,
            metadata=document.metadata,
        )
        prose_chunks = recursive.chunk(prose_doc, config)
        for pc in prose_chunks:
            pc.chunk_index = chunk_idx
            chunks.append(pc)
            chunk_idx += 1

        # Then: linearize each table as a dedicated chunk
        for i, table in enumerate(document.tables):
            if not table:
                continue

            lines = [f"TABLE {i + 1}:"]
            if table:
                headers = " | ".join(table[0])
                lines.append(f"Headers: {headers}")
            for row in table[1:]:
                lines.append(" | ".join(row))

            table_text = "\n".join(lines)
            chunks.append(
                self._make_chunk(
                    table_text,
                    document,
                    chunk_idx,
                    {"is_table": True, "table_index": i, "row_count": len(table)},
                )
            )
            chunk_idx += 1

        return chunks


# ─── ChunkEngine Orchestrator ─────────────────────────────────────────────────


class ChunkEngine:
    """
    Central orchestrator for all chunking strategies.

    Holds a registry of strategies and dispatches to the correct one
    based on ChunkConfig.strategy name.

    Usage:
        engine = ChunkEngine()
        config = ChunkConfig(strategy="semantic", chunk_size=512, chunk_overlap=64)
        chunks = engine.chunk(document, config)
        print(f"Produced {len(chunks)} chunks")

    Adding a new strategy:
        engine.register(MyNewChunker())
        # Then use: ChunkConfig(strategy="my_new_strategy")
    """

    def __init__(self) -> None:
        self._strategies: dict[str, ChunkStrategy] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        for strategy in [
            FixedSizeChunker(),
            RecursiveChunker(),
            SemanticChunker(),
            SentenceWindowChunker(),
            DocumentStructureChunker(),
            PropositionalChunker(),
            TableAwareChunker(),
        ]:
            self.register(strategy)

    def register(self, strategy: ChunkStrategy) -> None:
        """Register a chunking strategy. Overwrites if name already exists."""
        self._strategies[strategy.name] = strategy
        logger.debug("strategy_registered", name=strategy.name)

    @property
    def available_strategies(self) -> list[str]:
        """List of all registered strategy names."""
        return sorted(self._strategies.keys())

    def chunk(
        self,
        document: ParsedDocument,
        config: ChunkConfig | None = None,
    ) -> list[TextChunk]:
        """
        Chunk a document using the strategy specified in config.

        Args:
            document: ParsedDocument from any loader.
            config:   ChunkConfig (defaults to RecursiveChunker, 512 tokens, 64 overlap).

        Returns:
            Filtered list of TextChunk objects (empty chunks removed).

        Raises:
            ValueError: If the requested strategy is not registered.

        Example:
            engine = ChunkEngine()
            chunks = engine.chunk(
                document,
                ChunkConfig(strategy="semantic", chunk_size=512)
            )
        """
        if config is None:
            config = ChunkConfig()

        if config.strategy not in self._strategies:
            available = ", ".join(self.available_strategies)
            raise ValueError(f"Unknown strategy {config.strategy!r}. Available: {available}")

        if document.is_empty:
            logger.warning("empty_document_skipped", source=document.source)
            return []

        strategy = self._strategies[config.strategy]

        logger.info(
            "chunking_started",
            source=document.source,
            strategy=config.strategy,
            chunk_size=config.chunk_size,
        )

        raw_chunks = strategy.chunk(document, config)

        # Filter and validate
        valid_chunks = [
            c
            for c in raw_chunks
            if not c.is_empty
            and c.token_count >= config.min_chunk_size
            and c.token_count <= config.max_chunk_size
        ]

        logger.info(
            "chunking_complete",
            source=document.source,
            strategy=config.strategy,
            total_raw=len(raw_chunks),
            after_filter=len(valid_chunks),
            avg_tokens=round(
                sum(c.token_count for c in valid_chunks) / max(len(valid_chunks), 1), 1
            ),
        )

        return valid_chunks


# ─── Module-level singleton ───────────────────────────────────────────────────
# Import this in services to avoid re-creating the engine repeatedly.
default_chunk_engine = ChunkEngine()
