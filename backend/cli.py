# =============================================================================
# RetrievalLab — backend/cli.py
# =============================================================================
# PURPOSE : Typer-powered CLI for developers and DevOps workflows.
#           Provides `retrievallab` command with sub-commands for corpus
#           management, evaluation runs, and index operations.
#
# ENTRY POINT: defined in pyproject.toml as:
#   [project.scripts]
#   retrievallab = "backend.cli:app"
#
# USAGE (after `pip install -e .`):
#   retrievallab --help
#   retrievallab corpus ingest --source data/ --corpus-id mydata_v1 --domain legal
#   retrievallab corpus list
#   retrievallab corpus status mydata_v1
#
# DESIGN:
#   CLI is a thin wrapper over the same services used by the FastAPI layer.
#   This means CLI and API behavior are always in sync — no duplicated logic.
#
# INPUT  : CLI arguments and flags
# OUTPUT : Rich-formatted terminal output (progress bars, tables, colored text)
# =============================================================================

from __future__ import annotations

import asyncio

import typer
from rich import print as rprint
from rich.console import Console
from rich.table import Table

console = Console()

# ─── Root App ─────────────────────────────────────────────────────────────────
app = typer.Typer(
    name="retrievallab",
    help="[bold blue]RetrievalLab[/bold blue] — Cross-industry retrieval research platform",
    rich_markup_mode="rich",
    no_args_is_help=True,
)

# ─── Sub-app: corpus ──────────────────────────────────────────────────────────
corpus_app = typer.Typer(
    name="corpus",
    help="Manage corpora: ingest, list, inspect, delete",
    no_args_is_help=True,
)
app.add_typer(corpus_app, name="corpus")


# ─── corpus ingest ────────────────────────────────────────────────────────────

@corpus_app.command("ingest")
def ingest_corpus(
    source:          str            = typer.Option(...,     "--source",     "-s", help="Path to documents directory or single file"),
    corpus_id:       str            = typer.Option(...,     "--corpus-id",  "-c", help="Unique corpus identifier (snake_case)"),
    domain:          str            = typer.Option("general", "--domain",   "-d", help="Industry domain: healthcare, finance, legal, ..."),
    strategy:        str            = typer.Option("recursive", "--strategy", "-S", help="Chunking strategy name"),
    chunk_size:      int            = typer.Option(512,     "--chunk-size",       help="Target chunk size in tokens"),
    chunk_overlap:   int            = typer.Option(64,      "--overlap",          help="Overlap between chunks in tokens"),
    embed_model:     str            = typer.Option("text-embedding-3-small", "--embed-model", help="Embedding model"),
    force:           bool           = typer.Option(False,   "--force",      "-f", help="Re-ingest even if fingerprint unchanged"),
    name:            str | None  = typer.Option(None,    "--name",       "-n", help="Human-readable corpus name"),
) -> None:
    """
    Ingest documents from a local path into a named corpus.

    Examples:

        # Ingest all PDFs from a directory
        retrievallab corpus ingest --source data/legal/ --corpus-id legal_contracts_v1 --domain legal

        # Ingest a single PDF
        retrievallab corpus ingest --source report.pdf --corpus-id annual_report_2024

        # Use semantic chunking
        retrievallab corpus ingest --source data/ --corpus-id mydata --strategy semantic
    """
    from backend.services.corpus_forge import IngestRequest

    request = IngestRequest(
        corpus_id       = corpus_id,
        source          = source,
        name            = name or "",
        domain          = domain,
        strategy        = strategy,
        chunk_size      = chunk_size,
        chunk_overlap   = chunk_overlap,
        embedding_model = embed_model,
        force_reingest  = force,
    )

    rprint("\n[bold blue]RetrievalLab[/bold blue] — Corpus Ingestion")
    rprint(f"  Corpus ID : [cyan]{corpus_id}[/cyan]")
    rprint(f"  Source    : [yellow]{source}[/yellow]")
    rprint(f"  Domain    : {domain}")
    rprint(f"  Strategy  : [green]{strategy}[/green]")
    rprint(f"  Chunk size: {chunk_size} tokens  (overlap: {chunk_overlap})\n")

    # Run async ingest in the CLI event loop
    result = asyncio.run(_run_ingest(request))

    if result.skipped:
        rprint("[yellow]⟳ Skipped[/yellow] — same fingerprint; use --force to re-ingest")
        return

    if result.success:
        rprint("\n[bold green]✓ Ingestion Complete[/bold green]")
        t = Table(show_header=True, header_style="bold blue")
        t.add_column("Metric")
        t.add_column("Value", justify="right")
        t.add_row("Documents loaded",  str(result.doc_count))
        t.add_row("Chunks created",    str(result.chunk_count))
        t.add_row("Total tokens",      f"{result.total_tokens:,}")
        t.add_row("Duration",          f"{result.duration_s:.1f}s")
        t.add_row("Failures",          str(len(result.failures)))
        console.print(t)

        if result.failures:
            rprint("\n[yellow]⚠ Failed files:[/yellow]")
            for src, err in result.failures[:5]:
                rprint(f"  [red]✗[/red] {src}: {err}")
            if len(result.failures) > 5:
                rprint(f"  ... and {len(result.failures) - 5} more")
    else:
        rprint("\n[bold red]✗ Ingestion Failed[/bold red]")
        for src, err in result.failures:
            rprint(f"  [red]{src}[/red]: {err}")
        raise typer.Exit(code=1)


async def _run_ingest(request) -> IngestResult:
    """Run ingestion in async context with DB session."""
    from backend.db.base import AsyncSessionLocal
    from backend.services.corpus_forge import CorpusForge

    async with AsyncSessionLocal() as db:
        forge = CorpusForge(db=db)
        return await forge.ingest(request)


# ─── corpus list ─────────────────────────────────────────────────────────────

@corpus_app.command("list")
def list_corpora(
    domain: str | None = typer.Option(None, "--domain", "-d", help="Filter by domain"),
    status: str | None = typer.Option(None, "--status",       help="Filter by status"),
) -> None:
    """List all corpora in the database."""

    corpora = asyncio.run(_list_corpora_async(domain=domain, status=status))

    if not corpora:
        rprint("[yellow]No corpora found.[/yellow]")
        return

    t = Table(show_header=True, header_style="bold blue", title="RetrievalLab Corpora")
    t.add_column("Corpus ID",   style="cyan", no_wrap=True)
    t.add_column("Domain",      style="magenta")
    t.add_column("Status",      style="green")
    t.add_column("Docs",        justify="right")
    t.add_column("Chunks",      justify="right")
    t.add_column("Strategy")

    for c in corpora:
        status_color = {"READY": "green", "FAILED": "red", "INGESTING": "yellow"}.get(c["status"], "white")
        t.add_row(
            c["corpus_id"],
            c["domain"],
            f"[{status_color}]{c['status']}[/{status_color}]",
            str(c["doc_count"]),
            str(c["chunk_count"]),
            c["chunk_strategy"],
        )

    console.print(t)


async def _list_corpora_async(domain=None, status=None) -> list[dict]:
    from sqlalchemy import select

    from backend.db.base import AsyncSessionLocal
    from backend.models.corpus import Corpus, CorpusDomain, CorpusStatus

    async with AsyncSessionLocal() as db:
        q = select(Corpus).order_by(Corpus.created_at.desc())
        if domain:
            q = q.where(Corpus.domain == CorpusDomain(domain))
        if status:
            q = q.where(Corpus.status == CorpusStatus(status.upper()))
        result = await db.execute(q)
        corpora = result.scalars().all()
        return [
            {
                "corpus_id":     c.corpus_id,
                "domain":        c.domain.value,
                "status":        c.status.value,
                "doc_count":     c.doc_count,
                "chunk_count":   c.chunk_count,
                "chunk_strategy": c.chunk_strategy.value,
            }
            for c in corpora
        ]


# ─── corpus status ────────────────────────────────────────────────────────────

@corpus_app.command("status")
def corpus_status(
    corpus_id: str = typer.Argument(..., help="Corpus ID to check"),
) -> None:
    """Show detailed status and statistics for a corpus."""

    data = asyncio.run(_get_corpus_async(corpus_id))
    if data is None:
        rprint(f"[red]Corpus '{corpus_id}' not found[/red]")
        raise typer.Exit(code=1)

    rprint(f"\n[bold]Corpus:[/bold] [cyan]{data['corpus_id']}[/cyan]")
    rprint(f"[bold]Name:[/bold]     {data['name']}")
    rprint(f"[bold]Domain:[/bold]   {data['domain']}")
    rprint(f"[bold]Status:[/bold]   [green]{data['status']}[/green]")
    rprint(f"[bold]Docs:[/bold]     {data['doc_count']}")
    rprint(f"[bold]Chunks:[/bold]   {data['chunk_count']}")
    rprint(f"[bold]Tokens:[/bold]   {data['total_tokens']:,}")
    rprint(f"[bold]Strategy:[/bold] {data['chunk_strategy']}")
    if data.get("error_message"):
        rprint(f"[bold red]Error:[/bold red] {data['error_message']}")


async def _get_corpus_async(corpus_id: str) -> dict | None:
    from sqlalchemy import select

    from backend.db.base import AsyncSessionLocal
    from backend.models.corpus import Corpus

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Corpus).where(Corpus.corpus_id == corpus_id))
        c = result.scalar_one_or_none()
        if c is None:
            return None
        return {
            "corpus_id":     c.corpus_id,
            "name":          c.name,
            "domain":        c.domain.value,
            "status":        c.status.value,
            "doc_count":     c.doc_count,
            "chunk_count":   c.chunk_count,
            "total_tokens":  c.total_tokens,
            "chunk_strategy": c.chunk_strategy.value,
            "error_message": c.error_message,
        }


# ─── Entry point ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app()
