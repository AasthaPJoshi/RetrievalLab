# =============================================================================
# RetrievalLab — corpus/loaders/loader_registry.py
# =============================================================================
# PURPOSE : Registry that routes any document to the correct loader based on
#           file extension — callers don't need to know which loader to use.
#
# PATTERN : Registry (also known as Plugin Registry or Strategy Selector).
#           Loaders register themselves at class definition time via decorators
#           OR are pre-registered in DEFAULT_LOADERS below.
#
# HOW IT WORKS:
#   1. LoaderRegistry holds a list of (BaseLoader, priority) pairs.
#   2. load_path() iterates loaders in priority order, picks first match.
#   3. load_directory() loads all supported files in a directory tree.
#
# ADDING A NEW LOADER:
#   1. Create MyFormatLoader(BaseLoader) in corpus/loaders/
#   2. Add to DEFAULT_LOADERS list below — zero changes elsewhere.
#
# INPUT  : File path(s) — any mix of PDF, DOCX, HTML, TXT, Markdown
# OUTPUT : LoaderResult with all successfully parsed ParsedDocuments
#
# AFTER THIS FILE: Results go to CorpusForge → ChunkEngine → EmbedHub
# =============================================================================

from __future__ import annotations

import time
from pathlib import Path

import structlog

from corpus.loaders.base_loader import BaseLoader, LoaderResult, ParsedDocument
from corpus.loaders.pdf_loader import PDFLoader
from corpus.loaders.text_loader import DocxLoader, HTMLLoader, MarkdownLoader, TextLoader

logger = structlog.get_logger(__name__)


class LoaderRegistry:
    """
    Routes document files to the appropriate loader based on file extension.

    Usage:
        registry = LoaderRegistry()
        result = registry.load("data/corpus/")
        for doc in result.documents:
            print(doc.source, doc.word_count)

        # Or for a single file:
        result = registry.load("report.pdf")
        doc = result.documents[0]
    """

    def __init__(self) -> None:
        # List of (loader, priority) — higher priority checked first.
        # Priority matters when two loaders could handle the same extension.
        self._loaders: list[tuple[BaseLoader, int]] = []
        self._register_defaults()

    def _register_defaults(self) -> None:
        """Register all built-in loaders with default priorities."""
        self.register(PDFLoader(extract_tables=True),  priority=100)
        self.register(DocxLoader(),                    priority=90)
        self.register(HTMLLoader(),                    priority=80)
        self.register(MarkdownLoader(),                priority=70)
        self.register(TextLoader(),                    priority=60)

    def register(self, loader: BaseLoader, priority: int = 50) -> None:
        """
        Register a loader. Higher priority = checked first.

        Args:
            loader:   Instantiated loader implementing BaseLoader.
            priority: Integer priority (0–100). Defaults to 50.
        """
        self._loaders.append((loader, priority))
        # Sort descending by priority so highest-priority loaders are tried first
        self._loaders.sort(key=lambda x: x[1], reverse=True)
        logger.debug("loader_registered", loader=type(loader).__name__, priority=priority)

    def get_loader_for(self, path: Path) -> BaseLoader | None:
        """
        Find the appropriate loader for a file.

        Args:
            path: File path to match.

        Returns:
            First loader whose supports() returns True, or None if no match.
        """
        for loader, _ in self._loaders:
            if loader.supports(path):
                return loader
        return None

    @property
    def supported_extensions(self) -> set[str]:
        """Return all file extensions handled by registered loaders."""
        exts: set[str] = set()
        for loader, _ in self._loaders:
            if hasattr(loader, "SUPPORTED_EXTENSIONS"):
                exts.update(loader.SUPPORTED_EXTENSIONS)
        return exts

    def load(self, source: str | Path) -> LoaderResult:
        """
        Load one file or all supported files in a directory.

        Args:
            source: Path to a file or directory.

        Returns:
            LoaderResult aggregating results from all matched loaders.

        Example:
            registry = LoaderRegistry()
            result = registry.load("data/legal_contracts/")
            print(f"Loaded {result.success_count} documents in {result.duration_s:.1f}s")
            print(f"Failed: {result.failure_count}")
            for src, err in result.failures:
                print(f"  FAIL: {src} — {err}")
        """
        start = time.perf_counter()
        source_path = Path(source)

        if source_path.is_file():
            return self._load_single_file(source_path, start)

        if source_path.is_dir():
            return self._load_directory(source_path, start)

        return LoaderResult(
            documents=[],
            failures=[(str(source), "Path does not exist")],
            total_files=0,
            duration_s=0.0,
        )

    def _load_single_file(self, path: Path, start: float) -> LoaderResult:
        """Load exactly one file using the matched loader."""
        loader = self.get_loader_for(path)
        if loader is None:
            ext = path.suffix.lower()
            return LoaderResult(
                documents=[],
                failures=[(str(path), f"No loader for extension {ext!r}")],
                total_files=1,
                duration_s=time.perf_counter() - start,
            )
        return loader.load(path)

    def _load_directory(self, directory: Path, start: float) -> LoaderResult:
        """
        Load all supported files in a directory (recursive).

        Files with no matching loader are silently skipped (not counted as failures).
        """
        all_documents: list[ParsedDocument] = []
        all_failures:  list[tuple[str, str]] = []
        total_files = 0

        for file_path in sorted(directory.rglob("*")):
            if not file_path.is_file():
                continue

            loader = self.get_loader_for(file_path)
            if loader is None:
                continue  # skip unsupported formats silently

            total_files += 1
            try:
                result = loader.load(file_path)
                all_documents.extend(result.documents)
                all_failures.extend(result.failures)
            except Exception as exc:
                all_failures.append((str(file_path), str(exc)))

        duration = time.perf_counter() - start
        logger.info(
            "directory_load_complete",
            directory=str(directory),
            total_files=total_files,
            success=len(all_documents),
            failed=len(all_failures),
            duration_s=round(duration, 2),
        )

        return LoaderResult(
            documents=all_documents,
            failures=all_failures,
            total_files=total_files,
            duration_s=duration,
        )


# ─── Module-level singleton ───────────────────────────────────────────────────
# Most code should use this shared instance to avoid re-instantiating loaders.
# Tests can create fresh instances: LoaderRegistry()
default_registry = LoaderRegistry()
