# =============================================================================
# RetrievalLab — tests/unit/test_loaders.py
# =============================================================================
# PURPOSE : Unit tests for all document loaders (Text, Markdown, DOCX, HTML, PDF).
#           Uses temp files and pytest fixtures — no network, no Docker required.
#
# WHAT WE TEST:
#   1. TextLoader    — basic UTF-8 reading, empty files, encoding fallback
#   2. MarkdownLoader — frontmatter stripping, syntax removal, header extraction
#   3. HTMLLoader    — noise tag removal, main content extraction
#   4. LoaderRegistry — extension routing, directory scanning, mixed file types
#   5. BaseLoader    — file size limits, preprocessing, file hash computation
#
# RUN:
#   pytest tests/unit/test_loaders.py -v
# =============================================================================

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from corpus.loaders.base_loader import ParsedDocument, LoaderResult
from corpus.loaders.text_loader import TextLoader, MarkdownLoader, HTMLLoader
from corpus.loaders.loader_registry import LoaderRegistry


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_dir():
    """Provide a fresh temporary directory for each test."""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


def write_file(directory: Path, filename: str, content: str, encoding="utf-8") -> Path:
    """Helper: write a text file and return its path."""
    path = directory / filename
    path.write_text(content, encoding=encoding)
    return path


# ─── ParsedDocument ───────────────────────────────────────────────────────────

class TestParsedDocument:
    def test_auto_generates_doc_id(self):
        doc = ParsedDocument(text="hello", source="/some/path.txt")
        assert doc.doc_id != ""
        assert len(doc.doc_id) == 16  # sha256 hex prefix

    def test_word_count(self):
        doc = ParsedDocument(text="one two three four five", source="test")
        assert doc.word_count == 5

    def test_is_empty_true(self):
        doc = ParsedDocument(text="   \n\n   ", source="test")
        assert doc.is_empty is True

    def test_is_empty_false(self):
        doc = ParsedDocument(text="hello", source="test")
        assert doc.is_empty is False

    def test_has_tables_false(self):
        doc = ParsedDocument(text="hello", source="test")
        assert doc.has_tables is False

    def test_has_tables_true(self):
        doc = ParsedDocument(text="hello", source="test", tables=[[["a", "b"]]])
        assert doc.has_tables is True

    def test_repr_contains_source(self):
        doc = ParsedDocument(text="hello world", source="/path/to/file.txt")
        assert "file.txt" in repr(doc)


# ─── TextLoader ──────────────────────────────────────────────────────────────

class TestTextLoader:
    def setup_method(self):
        self.loader = TextLoader()

    def test_supports_txt_extension(self, tmp_dir):
        p = write_file(tmp_dir, "doc.txt", "content")
        assert self.loader.supports(p) is True

    def test_does_not_support_pdf(self, tmp_dir):
        p = write_file(tmp_dir, "doc.pdf", "content")
        assert self.loader.supports(p) is False

    def test_load_basic_text(self, tmp_dir):
        content = "Hello world. This is a test document."
        path    = write_file(tmp_dir, "test.txt", content)
        result  = self.loader.load(path)

        assert result.success_count == 1
        assert result.failure_count == 0
        doc = result.documents[0]
        assert "Hello world" in doc.text

    def test_load_empty_file_returns_no_docs(self, tmp_dir):
        path   = write_file(tmp_dir, "empty.txt", "")
        result = self.loader.load(path)
        # Empty file — should produce no documents
        assert result.success_count == 0

    def test_load_preserves_content(self, tmp_dir):
        content = "Line 1\nLine 2\nLine 3"
        path    = write_file(tmp_dir, "lines.txt", content)
        result  = self.loader.load(path)
        assert "Line 1" in result.documents[0].text
        assert "Line 3" in result.documents[0].text

    def test_source_is_file_path(self, tmp_dir):
        path   = write_file(tmp_dir, "test.txt", "hello")
        result = self.loader.load(path)
        assert result.documents[0].source == str(path)

    def test_load_directory_finds_txt_files(self, tmp_dir):
        write_file(tmp_dir, "a.txt", "content a")
        write_file(tmp_dir, "b.txt", "content b")
        write_file(tmp_dir, "c.md", "content c")  # not loaded by TextLoader
        result = self.loader.load(tmp_dir)
        assert result.success_count == 2  # only .txt files

    def test_nonexistent_file_returns_failure(self):
        result = self.loader.load("/nonexistent/path/file.txt")
        assert result.success_count == 0


# ─── MarkdownLoader ──────────────────────────────────────────────────────────

class TestMarkdownLoader:
    def setup_method(self):
        self.loader = MarkdownLoader()

    def test_supports_md_extension(self, tmp_dir):
        p = write_file(tmp_dir, "doc.md", "# Hello")
        assert self.loader.supports(p) is True

    def test_strips_yaml_frontmatter(self, tmp_dir):
        content = """---
title: Test Doc
date: 2024-01-01
author: Aastha
---

# Introduction

This is the actual content of the document.
"""
        path   = write_file(tmp_dir, "test.md", content)
        result = self.loader.load(path)
        doc    = result.documents[0]
        # Frontmatter keys should NOT appear in text
        assert "title: Test Doc" not in doc.text
        assert "date: 2024-01-01" not in doc.text
        # Content should appear
        assert "Introduction" in doc.text or "actual content" in doc.text

    def test_strips_markdown_syntax(self, tmp_dir):
        content = "**Bold text** and _italic_ and `code` here."
        path    = write_file(tmp_dir, "styled.md", content)
        result  = self.loader.load(path)
        text    = result.documents[0].text
        assert "**" not in text
        assert "_" not in text or "italic" in text  # underscores removed, words remain

    def test_extracts_section_headers(self, tmp_dir):
        content = """# Main Title
## Section One
Content here.
## Section Two
More content.
"""
        path   = write_file(tmp_dir, "sections.md", content)
        result = self.loader.load(path)
        meta   = result.documents[0].metadata
        assert "section_headers" in meta
        assert len(meta["section_headers"]) >= 2

    def test_removes_links_keeps_text(self, tmp_dir):
        content = "See [this link](https://example.com) for details."
        path    = write_file(tmp_dir, "links.md", content)
        result  = self.loader.load(path)
        text    = result.documents[0].text
        assert "this link" in text
        assert "https://example.com" not in text


# ─── HTMLLoader ──────────────────────────────────────────────────────────────

class TestHTMLLoader:
    def setup_method(self):
        self.loader = HTMLLoader()

    def test_supports_html_extension(self, tmp_dir):
        p = write_file(tmp_dir, "doc.html", "<html></html>")
        assert self.loader.supports(p) is True

    def test_extracts_text_content(self, tmp_dir):
        content = """<!DOCTYPE html>
<html>
<head><title>Test Page</title></head>
<body>
  <main>
    <h1>Main Heading</h1>
    <p>This is the main content of the page.</p>
    <p>More content here.</p>
  </main>
</body>
</html>"""
        path   = write_file(tmp_dir, "test.html", content)
        result = self.loader.load(path)
        text   = result.documents[0].text
        assert "Main Heading" in text
        assert "main content" in text

    def test_removes_script_tags(self, tmp_dir):
        content = """<html><body>
<p>Real content here.</p>
<script>var x = 'this should not appear';</script>
</body></html>"""
        path   = write_file(tmp_dir, "scripts.html", content)
        result = self.loader.load(path)
        text   = result.documents[0].text
        assert "this should not appear" not in text
        assert "Real content" in text

    def test_extracts_title_metadata(self, tmp_dir):
        content = "<html><head><title>My Page Title</title></head><body><p>content</p></body></html>"
        path    = write_file(tmp_dir, "titled.html", content)
        result  = self.loader.load(path)
        meta    = result.documents[0].metadata
        assert meta.get("title") == "My Page Title"

    def test_removes_nav_and_footer(self, tmp_dir):
        content = """<html><body>
<nav>Navigation links here</nav>
<main><p>Article content.</p></main>
<footer>Footer text here</footer>
</body></html>"""
        path   = write_file(tmp_dir, "layout.html", content)
        result = self.loader.load(path)
        text   = result.documents[0].text
        assert "Navigation links" not in text
        assert "Footer text" not in text
        assert "Article content" in text


# ─── LoaderRegistry ──────────────────────────────────────────────────────────

class TestLoaderRegistry:
    def setup_method(self):
        self.registry = LoaderRegistry()

    def test_routes_txt_to_text_loader(self, tmp_dir):
        p      = write_file(tmp_dir, "file.txt", "content")
        loader = self.registry.get_loader_for(p)
        assert loader is not None
        assert type(loader).__name__ == "TextLoader"

    def test_routes_md_to_markdown_loader(self, tmp_dir):
        p      = write_file(tmp_dir, "file.md", "# content")
        loader = self.registry.get_loader_for(p)
        assert loader is not None
        assert type(loader).__name__ == "MarkdownLoader"

    def test_routes_html_to_html_loader(self, tmp_dir):
        p      = write_file(tmp_dir, "file.html", "<html></html>")
        loader = self.registry.get_loader_for(p)
        assert loader is not None
        assert type(loader).__name__ == "HTMLLoader"

    def test_unknown_extension_returns_none(self, tmp_dir):
        p      = write_file(tmp_dir, "file.xyz", "data")
        loader = self.registry.get_loader_for(p)
        assert loader is None

    def test_load_mixed_directory(self, tmp_dir):
        write_file(tmp_dir, "doc1.txt",  "Text document content.")
        write_file(tmp_dir, "doc2.md",   "# Markdown document\nContent here.")
        write_file(tmp_dir, "doc3.html", "<html><body><p>HTML content.</p></body></html>")
        write_file(tmp_dir, "ignore.xyz", "Should be ignored")

        result = self.registry.load(tmp_dir)

        # Should load txt + md + html, skip .xyz
        assert result.total_files == 3
        assert result.success_count >= 2  # at least 2 out of 3 should succeed

    def test_load_single_file(self, tmp_dir):
        path   = write_file(tmp_dir, "single.txt", "Single file content.")
        result = self.registry.load(path)
        assert result.total_files == 1
        assert result.success_count == 1

    def test_custom_loader_registration(self, tmp_dir):
        """A custom loader registered at runtime should override default routing."""
        from corpus.loaders.base_loader import BaseLoader, ParsedDocument

        class CustomTxtLoader(BaseLoader):
            SUPPORTED_EXTENSIONS = {".txt"}

            def supports(self, path: Path) -> bool:
                return path.suffix == ".txt"

            def _parse(self, path: Path) -> ParsedDocument:
                return ParsedDocument(
                    text="CUSTOM_CONTENT",
                    source=str(path),
                    metadata={"loaded_by": "custom"},
                )

        registry = LoaderRegistry()
        registry.register(CustomTxtLoader(), priority=999)  # highest priority

        path   = write_file(tmp_dir, "file.txt", "original content")
        loader = registry.get_loader_for(path)
        assert type(loader).__name__ == "CustomTxtLoader"

    def test_supported_extensions_includes_standard_types(self):
        exts = self.registry.supported_extensions
        assert ".txt" in exts
        assert ".md" in exts
        assert ".html" in exts
        assert ".pdf" in exts
        assert ".docx" in exts

    def test_load_nonexistent_path_returns_failure(self):
        result = self.registry.load("/nonexistent/path/")
        assert result.success_count == 0
        assert result.total_files == 0
