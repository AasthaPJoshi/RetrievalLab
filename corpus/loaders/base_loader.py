# =============================================================================
# RetrievalLab — corpus/loaders/base_loader.py
# =============================================================================
# PURPOSE : Defines the abstract base class that every document loader
#           (PDF, DOCX, HTML, TXT, Markdown) must implement.
#
# WHY AN ABSTRACT BASE:
#   All loaders return the same `ParsedDocument` dataclass regardless of
#   source format. This means the ChunkEngine, EvalEngine, and API don't
#   need to know what format a document was — they just work with
#   ParsedDocument objects. Adding a new source format (e.g., JSON, EPUB)
#   is a matter of subclassing BaseLoader, not changing downstream code.
#
# DESIGN PATTERN:
#   Template Method — BaseLoader defines `load()` which calls `_parse()`.
#   Subclasses implement `_parse()` and `supports()`.
#   BaseLoader handles retries, logging, and error normalization.
#
# INPUT  : File path or URL string pointing to a document
# OUTPUT : List[ParsedDocument] — one or more parsed documents with metadata
#
# EXAMPLE:
#   from corpus.loaders.pdf_loader import PDFLoader
#   loader = PDFLoader()
#   docs = loader.load("research_paper.pdf")
#   print(docs[0].text[:200])
#   print(docs[0].metadata)
# =============================================================================

from __future__ import annotations

import abc
import hashlib
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


# ─── Data Classes ─────────────────────────────────────────────────────────────


@dataclass
class ParsedDocument:
    """
    Unified representation of a parsed document, regardless of source format.

    Every loader returns List[ParsedDocument]. The downstream ChunkEngine
    consumes this type directly, maintaining a clean separation between
    parsing (loaders) and splitting (chunkers).

    Attributes:
        text:        Full extracted text content (UTF-8 string).
        source:      Original file path or URL (for provenance tracking).
        doc_id:      Stable identifier derived from source path (SHA-256 prefix).
        page_count:  Number of pages (PDFs) or sections (HTML/DOCX). None if N/A.
        language:    Detected or declared language code (e.g., "en", "fr").
        metadata:    Source-specific structured data (title, author, date, etc.)
        tables:      Extracted tables as list of list-of-strings (row × col).
        images:      List of image descriptions or extracted alt text (if any).
        parse_time_s: Wall-clock seconds spent parsing this document.
        error:       Non-None if partial parse succeeded with warnings.
    """

    text: str
    source: str
    doc_id: str = field(default="")
    page_count: int | None = field(default=None)
    language: str = field(default="en")
    metadata: dict[str, Any] = field(default_factory=dict)
    tables: list[list[list[str]]] = field(default_factory=list)
    images: list[str] = field(default_factory=list)
    parse_time_s: float = field(default=0.0)
    error: str | None = field(default=None)

    def __post_init__(self) -> None:
        # Auto-generate doc_id from source path if not set
        if not self.doc_id:
            self.doc_id = hashlib.sha256(self.source.encode()).hexdigest()[:16]

    @property
    def word_count(self) -> int:
        """Approximate word count (split on whitespace)."""
        return len(self.text.split())

    @property
    def char_count(self) -> int:
        """Character count of text content."""
        return len(self.text)

    @property
    def has_tables(self) -> bool:
        return len(self.tables) > 0

    @property
    def is_empty(self) -> bool:
        return len(self.text.strip()) == 0

    def __repr__(self) -> str:
        return (
            f"ParsedDocument(source={self.source!r}, "
            f"words={self.word_count}, "
            f"tables={len(self.tables)}, "
            f"error={self.error!r})"
        )


@dataclass
class LoaderResult:
    """
    Container for the output of a loader.load() call.

    Separates successful parses from failures so the pipeline can continue
    with partial results and report failures without crashing.

    Attributes:
        documents:   Successfully parsed documents.
        failures:    (source, error_message) pairs for files that failed.
        total_files: Number of files attempted.
        duration_s:  Total wall-clock time for the load operation.
    """

    documents: list[ParsedDocument]
    failures: list[tuple[str, str]]  # (source, error_message)
    total_files: int
    duration_s: float

    @property
    def success_count(self) -> int:
        return len(self.documents)

    @property
    def failure_count(self) -> int:
        return len(self.failures)

    @property
    def success_rate(self) -> float:
        if self.total_files == 0:
            return 0.0
        return self.success_count / self.total_files

    def __repr__(self) -> str:
        return (
            f"LoaderResult("
            f"success={self.success_count}/{self.total_files}, "
            f"failures={self.failure_count}, "
            f"duration={self.duration_s:.2f}s)"
        )


# ─── Abstract Base Loader ─────────────────────────────────────────────────────


class BaseLoader(abc.ABC):
    """
    Abstract base class for all document loaders.

    Subclasses must implement:
        _parse(path: Path) -> ParsedDocument
        supports(path: Path) -> bool

    Subclasses may optionally override:
        _preprocess_text(text: str) -> str
        _extract_metadata(path: Path) -> dict

    Template method `load()` handles:
        • Glob expansion for directory inputs
        • Filtering to supported file types
        • Per-file error catching (partial success)
        • Timing measurement
        • Structured logging
    """

    # Maximum file size to attempt parsing (default: 50 MB)
    MAX_FILE_SIZE_BYTES: int = 50 * 1024 * 1024

    def __init__(self, max_file_size_bytes: int | None = None) -> None:
        self.max_file_size_bytes = max_file_size_bytes or self.MAX_FILE_SIZE_BYTES
        self._log = structlog.get_logger(self.__class__.__name__)

    # ── Abstract interface ────────────────────────────────────────────────────

    @abc.abstractmethod
    def supports(self, path: Path) -> bool:
        """
        Return True if this loader can handle the given file.

        Used by LoaderRegistry to route files to the correct loader.

        Args:
            path: File path to check.

        Returns:
            True if this loader can parse the file.
        """
        ...

    @abc.abstractmethod
    def _parse(self, path: Path) -> ParsedDocument:
        """
        Parse a single file and return a ParsedDocument.

        Implementations should:
        1. Extract all text content.
        2. Detect or declare language.
        3. Extract structured metadata (title, author, dates, etc.)
        4. Extract tables if format supports them.

        Args:
            path: Validated, existing file path.

        Returns:
            ParsedDocument with populated text and metadata.

        Raises:
            Any exception on parse failure — caught by load() and recorded.
        """
        ...

    # ── Template method ───────────────────────────────────────────────────────

    def load(self, source: str | Path) -> LoaderResult:
        """
        Load one or more documents from a file path or directory.

        Handles glob expansion, size validation, and per-file error isolation.

        Args:
            source: Path to a single file OR a directory (all supported files loaded).

        Returns:
            LoaderResult with successful ParsedDocuments and failure records.

        Example:
            loader = PDFLoader()
            result = loader.load("data/papers/")
            print(f"Loaded {result.success_count} / {result.total_files}")
            for doc in result.documents:
                print(doc.word_count)
        """
        start = time.perf_counter()
        source_path = Path(source)

        # ── Resolve file list ─────────────────────────────────────────────
        if source_path.is_dir():
            candidates = [p for p in source_path.rglob("*") if p.is_file()]
        elif source_path.is_file():
            candidates = [source_path]
        else:
            self._log.error("source_not_found", source=str(source))
            return LoaderResult([], [(str(source), "Path not found")], 0, 0.0)

        # Filter to files this loader supports
        files = [p for p in candidates if self.supports(p)]
        self._log.info("load_started", total_files=len(files), source=str(source))

        # ── Parse each file ───────────────────────────────────────────────
        documents: list[ParsedDocument] = []
        failures: list[tuple[str, str]] = []

        for file_path in files:
            try:
                doc = self._load_single(file_path)
                if doc is not None:
                    documents.append(doc)
            except Exception as exc:
                failure_msg = f"{type(exc).__name__}: {exc}"
                failures.append((str(file_path), failure_msg))
                self._log.warning(
                    "file_parse_failed",
                    file=str(file_path),
                    error=failure_msg,
                )

        duration = time.perf_counter() - start
        self._log.info(
            "load_complete",
            success=len(documents),
            failed=len(failures),
            duration_s=round(duration, 2),
        )

        return LoaderResult(
            documents=documents,
            failures=failures,
            total_files=len(files),
            duration_s=duration,
        )

    def _load_single(self, path: Path) -> ParsedDocument | None:
        """
        Parse one file with size validation and timing.

        Returns None if file is empty; raises on parse errors (caught by load()).
        """
        # Size guard
        file_size = path.stat().st_size
        if file_size > self.max_file_size_bytes:
            raise ValueError(
                f"File too large: {file_size / 1024 / 1024:.1f} MB "
                f"(limit: {self.max_file_size_bytes / 1024 / 1024:.0f} MB)"
            )

        if file_size == 0:
            self._log.warning("empty_file_skipped", file=str(path))
            return None

        # Parse with timing
        t0 = time.perf_counter()
        doc = self._parse(path)
        doc.parse_time_s = time.perf_counter() - t0

        # Post-processing: clean whitespace, normalize unicode
        doc.text = self._preprocess_text(doc.text)

        if doc.is_empty:
            self._log.warning("empty_parse_result", file=str(path))
            return None

        self._log.debug(
            "file_parsed",
            file=str(path),
            words=doc.word_count,
            parse_time_s=round(doc.parse_time_s, 3),
        )
        return doc

    def _preprocess_text(self, text: str) -> str:
        """
        Clean extracted text before returning.

        Operations:
        - Normalize line endings to \\n
        - Collapse runs of 3+ blank lines to 2
        - Strip leading/trailing whitespace
        - Normalize unicode NFC

        Override in subclasses to apply format-specific cleaning.

        Args:
            text: Raw extracted text.

        Returns:
            Cleaned text string.
        """
        import re
        import unicodedata

        # Normalize unicode to NFC (composed form)
        text = unicodedata.normalize("NFC", text)

        # Normalize line endings
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # Collapse 3+ blank lines to 2
        text = re.sub(r"\n{3,}", "\n\n", text)

        # Remove null bytes (common in corrupted PDFs)
        text = text.replace("\x00", "")

        return text.strip()

    def _compute_file_hash(self, path: Path) -> str:
        """
        Compute SHA-256 hash of file contents.
        Used for corpus fingerprinting and change detection.
        """
        sha256 = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()
