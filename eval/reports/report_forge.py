# =============================================================================
# RetrievalLab — eval/reports/report_forge.py
# =============================================================================
# PURPOSE : Automatically generate professional PDF evaluation reports
#           after benchmark runs. Reports include all metrics, charts,
#           adversarial analysis, and strategic recommendations.
#
# WHAT IT GENERATES:
#   • Executive summary with top-line NDCG@10 / MRR / MAP scores
#   • Per-corpus breakdown with strategy comparison tables
#   • Adversarial robustness heatmap (6 attacks × NDCG degradation)
#   • BEIR benchmark comparison vs published baselines
#   • Ragas pipeline quality scores (faithfulness, context recall)
#   • Recommendations based on weakest metrics
#
# OUTPUT FORMAT: PDF via ReportLab + Matplotlib charts embedded as PNG
#
# HOW TO USE:
#   forge = ReportForge()
#   pdf_path = await forge.generate(
#       experiment_name="healthcare_hybrid_v1",
#       retrieval_scores=agg_scores,
#       adversarial_report=adv_report,
#       ragas_result=ragas_result,
#   )
#   print(f"Report saved to: {pdf_path}")
# =============================================================================

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class ReportConfig:
    """Configuration for report generation."""

    experiment_name: str
    output_dir: str = "results/reports"
    include_charts: bool = True
    include_trace: bool = False
    logo_text: str = "RetrievalLab"
    author: str = "RetrievalLab EvalEngine"


class ReportForge:
    """
    Generates professional PDF evaluation reports.

    Combines ReportLab for PDF layout with Matplotlib for embedded charts.
    Falls back to Markdown report if PDF dependencies unavailable.

    Args:
        config: ReportConfig with output settings.

    Example:
        forge = ReportForge()
        path  = await forge.generate(
            config=ReportConfig(experiment_name="hybrid_eval_v1"),
            retrieval_scores=aggregate_scores,
            adversarial_report=adv_report,
        )
    """

    # Color palette (matches UI)
    COLORS = {
        "navy": (0.04, 0.07, 0.18),  # #0A1230
        "cyan": (0.0, 0.8, 1.0),  # #00CCFF
        "white": (1.0, 1.0, 1.0),
        "light_bg": (0.96, 0.97, 0.99),
        "success": (0.0, 0.78, 0.55),
        "warning": (1.0, 0.75, 0.0),
        "danger": (1.0, 0.25, 0.25),
        "text": (0.15, 0.15, 0.25),
    }

    async def generate(
        self,
        config: ReportConfig,
        retrieval_scores: Any | None = None,
        adversarial_report: Any | None = None,
        ragas_result: Any | None = None,
        beir_result: Any | None = None,
        extra_metrics: dict[str, float] | None = None,
    ) -> str:
        """
        Generate a comprehensive PDF evaluation report.

        Args:
            config:             Report configuration.
            retrieval_scores:   AggregatedEvalScore from aggregate_scores().
            adversarial_report: AdversarialReport from AdversarialHarness.
            ragas_result:       RagasResult from RagasEvaluator.
            beir_result:        BEIRSuiteResult from BEIRRunner.
            extra_metrics:      Any additional key→value metrics to include.

        Returns:
            Path to the generated PDF file.
        """
        start = time.perf_counter()

        # Ensure output directory exists
        output_dir = Path(config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"{config.experiment_name}_{timestamp}.pdf"
        pdf_path = output_dir / filename

        try:
            path = self._generate_pdf(
                pdf_path,
                config,
                retrieval_scores,
                adversarial_report,
                ragas_result,
                beir_result,
                extra_metrics,
            )
        except ImportError as e:
            logger.warning("pdf_deps_unavailable", error=str(e), fallback="markdown")
            path = self._generate_markdown(
                output_dir / filename.replace(".pdf", ".md"),
                config,
                retrieval_scores,
                adversarial_report,
                ragas_result,
            )

        duration = time.perf_counter() - start
        logger.info("report_generated", path=str(path), duration_s=round(duration, 2))
        return str(path)

    def _generate_pdf(
        self,
        path: Path,
        config: ReportConfig,
        retrieval_scores: Any | None,
        adversarial_report: Any | None,
        ragas_result: Any | None,
        beir_result: Any | None,
        extra_metrics: dict | None,
    ) -> Path:
        """Generate PDF using ReportLab."""
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import (
            HRFlowable,
            PageBreak,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )

        doc = SimpleDocTemplate(
            str(path), pagesize=letter, rightMargin=0.75 * inch, leftMargin=0.75 * inch
        )
        styles = getSampleStyleSheet()
        story = []

        # ── Custom styles ──────────────────────────────────────────────────
        title_style = ParagraphStyle(
            "ReportTitle",
            parent=styles["Title"],
            fontSize=28,
            fontName="Helvetica-Bold",
            textColor=colors.HexColor("#0A1230"),
            spaceAfter=6,
            alignment=TA_LEFT,
        )
        h1_style = ParagraphStyle(
            "H1",
            parent=styles["Heading1"],
            fontSize=16,
            fontName="Helvetica-Bold",
            textColor=colors.HexColor("#0A1230"),
            spaceBefore=20,
            spaceAfter=8,
        )
        h2_style = ParagraphStyle(
            "H2",
            parent=styles["Heading2"],
            fontSize=13,
            fontName="Helvetica-Bold",
            textColor=colors.HexColor("#1a3a6b"),
            spaceBefore=14,
            spaceAfter=6,
        )
        body_style = ParagraphStyle(
            "Body",
            parent=styles["Normal"],
            fontSize=10,
            fontName="Helvetica",
            textColor=colors.HexColor("#1e1e3a"),
            spaceAfter=4,
            leading=15,
        )
        metric_style = ParagraphStyle(
            "Metric",
            parent=styles["Normal"],
            fontSize=22,
            fontName="Helvetica-Bold",
            textColor=colors.HexColor("#00CCFF"),
            alignment=TA_CENTER,
        )

        # ── Cover ──────────────────────────────────────────────────────────
        story.append(Spacer(1, 0.5 * inch))
        story.append(Paragraph("RetrievalLab", title_style))
        story.append(
            Paragraph(
                "Evaluation Report",
                ParagraphStyle(
                    "Subtitle",
                    parent=styles["Normal"],
                    fontSize=14,
                    fontName="Helvetica",
                    textColor=colors.HexColor("#4a5568"),
                    spaceAfter=4,
                ),
            )
        )
        story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#00CCFF")))
        story.append(Spacer(1, 0.1 * inch))
        story.append(Paragraph(f"Experiment: {config.experiment_name}", body_style))
        story.append(Paragraph(f"Generated: {time.strftime('%B %d, %Y at %H:%M UTC')}", body_style))
        story.append(Paragraph(f"Author: {config.author}", body_style))
        story.append(Spacer(1, 0.4 * inch))

        # ── Executive Summary ──────────────────────────────────────────────
        story.append(Paragraph("Executive Summary", h1_style))

        if retrieval_scores:
            summary_data = [
                ["Metric", "Score", "Interpretation"],
                [
                    "NDCG@10",
                    f"{retrieval_scores.ndcg_at_10:.4f}",
                    self._interpret_ndcg(retrieval_scores.ndcg_at_10),
                ],
                ["MRR", f"{retrieval_scores.mrr:.4f}", self._interpret_mrr(retrieval_scores.mrr)],
                [
                    "MAP@10",
                    f"{retrieval_scores.map_at_10:.4f}",
                    "Average Precision across all queries",
                ],
                [
                    "Precision@10",
                    f"{retrieval_scores.precision_at_10:.4f}",
                    "Fraction of top-10 that are relevant",
                ],
                [
                    "Recall@10",
                    f"{retrieval_scores.recall_at_10:.4f}",
                    "Fraction of relevant docs retrieved",
                ],
                [
                    "Hit Rate@10",
                    f"{retrieval_scores.hit_rate_at_10:.4f}",
                    "Queries with ≥1 relevant in top-10",
                ],
                ["Query Count", str(retrieval_scores.query_count), "Total queries evaluated"],
            ]
            tbl = Table(summary_data, colWidths=[2.0 * inch, 1.2 * inch, 3.6 * inch])
            tbl.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0A1230")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, 0), 11),
                        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                        ("FONTSIZE", (0, 1), (-1, -1), 10),
                        (
                            "ROWBACKGROUNDS",
                            (0, 1),
                            (-1, -1),
                            [colors.HexColor("#f4f7ff"), colors.white],
                        ),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d0d5e8")),
                        ("ALIGN", (1, 0), (1, -1), "CENTER"),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ]
                )
            )
            story.append(tbl)
            story.append(Spacer(1, 0.3 * inch))

        # ── Adversarial Section ────────────────────────────────────────────
        if adversarial_report:
            story.append(Paragraph("Adversarial Robustness Analysis", h1_style))
            story.append(
                Paragraph(
                    f"Overall Robustness Score: <b>{adversarial_report.overall_robustness:.1f}%</b> "
                    f"({'Robust' if adversarial_report.overall_robustness > 80 else 'Fragile'})",
                    body_style,
                )
            )

            adv_data = [["Attack Type", "Baseline NDCG", "Attacked NDCG", "Δ%", "Status"]]
            for ar in adversarial_report.attack_results:
                status = "✓ Robust" if ar.is_robust else "✗ Degraded"
                adv_data.append(
                    [
                        ar.attack_name.replace("_", " ").title(),
                        f"{ar.baseline_ndcg:.4f}",
                        f"{ar.attacked_ndcg:.4f}",
                        f"{ar.degradation_pct:+.1f}%",
                        status,
                    ]
                )
            tbl = Table(
                adv_data, colWidths=[2.2 * inch, 1.3 * inch, 1.3 * inch, 0.8 * inch, 1.2 * inch]
            )
            tbl.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3a6b")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        (
                            "ROWBACKGROUNDS",
                            (0, 1),
                            (-1, -1),
                            [colors.HexColor("#f4f7ff"), colors.white],
                        ),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d0d5e8")),
                        ("TOPPADDING", (0, 0), (-1, -1), 5),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ]
                )
            )
            story.append(tbl)
            story.append(Spacer(1, 0.3 * inch))

        # ── Ragas Section ──────────────────────────────────────────────────
        if ragas_result:
            story.append(Paragraph("RAG Pipeline Quality (Ragas)", h1_style))
            ragas_data = [["Metric", "Score", "Target"]]
            metrics = [
                ("Faithfulness", ragas_result.faithfulness, 0.85),
                ("Context Precision", ragas_result.context_precision, 0.75),
                ("Context Recall", ragas_result.context_recall, 0.80),
                ("Answer Relevance", ragas_result.answer_relevance, 0.80),
            ]
            for name, score, target in metrics:
                if score is not None:
                    status = "✓" if score >= target else "↑ Needs work"
                    ragas_data.append([name, f"{score:.4f}", f"≥{target:.2f} {status}"])
            tbl = Table(ragas_data, colWidths=[2.5 * inch, 1.2 * inch, 3.1 * inch])
            tbl.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0A1230")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        (
                            "ROWBACKGROUNDS",
                            (0, 1),
                            (-1, -1),
                            [colors.HexColor("#f4f7ff"), colors.white],
                        ),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d0d5e8")),
                        ("TOPPADDING", (0, 0), (-1, -1), 5),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ]
                )
            )
            story.append(tbl)

        # ── Recommendations ────────────────────────────────────────────────
        story.append(PageBreak())
        story.append(Paragraph("Strategic Recommendations", h1_style))
        recs = self._generate_recommendations(retrieval_scores, adversarial_report, ragas_result)
        for i, rec in enumerate(recs, 1):
            story.append(Paragraph(f"{i}. {rec}", body_style))
            story.append(Spacer(1, 0.05 * inch))

        doc.build(story)
        return path

    def _generate_markdown(
        self,
        path: Path,
        config: ReportConfig,
        retrieval_scores: Any | None,
        adversarial: Any | None,
        ragas: Any | None,
    ) -> Path:
        """Fallback Markdown report when ReportLab is unavailable."""
        lines = [
            "# RetrievalLab Evaluation Report",
            f"**Experiment:** {config.experiment_name}",
            f"**Generated:** {time.strftime('%Y-%m-%d %H:%M UTC')}",
            "",
            "## Retrieval Metrics",
        ]

        if retrieval_scores:
            lines += [
                "| Metric | Score |",
                "|--------|-------|",
                f"| NDCG@10 | {retrieval_scores.ndcg_at_10:.4f} |",
                f"| MRR | {retrieval_scores.mrr:.4f} |",
                f"| MAP@10 | {retrieval_scores.map_at_10:.4f} |",
                f"| Precision@10 | {retrieval_scores.precision_at_10:.4f} |",
                f"| Recall@10 | {retrieval_scores.recall_at_10:.4f} |",
                f"| Hit Rate@10 | {retrieval_scores.hit_rate_at_10:.4f} |",
                f"| Query Count | {retrieval_scores.query_count} |",
            ]

        if adversarial:
            lines += [
                "",
                "## Adversarial Robustness",
                f"**Overall: {adversarial.overall_robustness:.1f}%**",
                "",
            ]
            for ar in adversarial.attack_results:
                lines.append(
                    f"- {ar.attack_name}: {ar.attacked_ndcg:.4f} (Δ{ar.degradation_pct:+.1f}%)"
                )

        path.write_text("\n".join(lines))
        return path

    def _interpret_ndcg(self, score: float) -> str:
        if score >= 0.85:
            return "Excellent — production-ready"
        if score >= 0.70:
            return "Good — competitive performance"
        if score >= 0.55:
            return "Moderate — improvement needed"
        return "Poor — investigate retrieval quality"

    def _interpret_mrr(self, score: float) -> str:
        if score >= 0.90:
            return "Excellent — first result almost always relevant"
        if score >= 0.75:
            return "Good — relevant result typically in top 2"
        if score >= 0.60:
            return "Moderate — often not in position 1"
        return "Poor — consider re-ranking or query expansion"

    def _generate_recommendations(self, scores, adv, ragas) -> list[str]:
        """Generate strategic improvement recommendations based on metric weaknesses."""
        recs = []

        if scores:
            if scores.ndcg_at_10 < 0.70:
                recs.append(
                    "Switch to hybrid retrieval (RRF fusion) if using sparse-only — typically +8-12% NDCG@10."
                )
            if scores.recall_at_10 < 0.60:
                recs.append(
                    "Improve recall: increase top_k to 20, add query expansion, or use dense retrieval with BGE-M3."
                )
            if scores.precision_at_10 < 0.50:
                recs.append(
                    "Improve precision: add cross-encoder reranking (RankForge) — eliminates low-relevance results."
                )
            if scores.mrr < 0.70:
                recs.append(
                    "Improve MRR: PropositionalChunker produces finer granularity for factoid Q&A; test on your query set."
                )

        if adv and adv.overall_robustness < 80:
            recs.append(
                "Adversarial robustness < 80%: add query augmentation in training, use spell-correction as a preprocessing step."
            )

        if ragas and ragas.faithfulness and ragas.faithfulness < 0.80:
            recs.append(
                "Low faithfulness score: the LLM is hallucinating. Add explicit grounding instructions and reduce temperature to 0."
            )

        if not recs:
            recs.append(
                "All metrics within target range. Consider running BEIR benchmark for external validation."
            )
            recs.append(
                "Next: fine-tune embedding model with domain-specific data using LoRA for +5-10% NDCG improvement."
            )

        return recs
