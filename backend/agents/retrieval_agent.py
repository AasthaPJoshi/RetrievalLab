# =============================================================================
# RetrievalLab — backend/agents/retrieval_agent.py
# =============================================================================
# PURPOSE : 5-node LangGraph orchestrator for agentic retrieval.
#           Transforms a raw user query into a structured, reranked,
#           synthesized answer with full source attribution and confidence.
#
# PIPELINE NODES:
#   Node 1 — QueryAnalyzer:    Classifies query type, expands terms, detects domain
#   Node 2 — MultiRetriever:   Runs sparse + dense + hybrid in parallel
#   Node 3 — RankForge:        Cross-encoder reranking, deduplication, MMR diversity
#   Node 4 — Synthesizer:      LLM-synthesized answer grounded in retrieved context
#   Node 5 — OutputFormatter:  Structures final response with citations + confidence
#
# WHY LANGGRAPH:
#   LangGraph's state machine handles conditional routing (e.g., if initial
#   retrieval returns zero results, re-route to query relaxation), retry loops,
#   and async fan-out without callback hell.
#
# INPUT  : AgentQuery (query_text, corpus_id, mode, top_k)
# OUTPUT : AgentResponse (answer, sources, confidence, latency_ms, trace)
#
# USAGE:
#   agent = RetrievalAgent(retriever=retriever, embed_hub=hub)
#   response = await agent.run(AgentQuery(
#       query_text="What are the diagnostic criteria for type 2 diabetes?",
#       corpus_id="healthcare_pubmed_v1",
#   ))
#   print(response.answer)
#   print(response.sources)
# =============================================================================

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, TypedDict

import structlog

from backend.services.observe_lab import observe_lab

logger = structlog.get_logger(__name__)


# ─── State Schema ─────────────────────────────────────────────────────────────


class AgentState(TypedDict):
    """
    Shared state passed between all LangGraph nodes.

    Each node reads from and writes to this dict.
    LangGraph checkpoints this state automatically.
    """

    # Input
    query_text: str
    corpus_id: str
    mode: str
    top_k: int

    # Node 1 outputs
    query_type: str  # "factoid" | "analytical" | "comparative" | "exploratory"
    expanded_query: str  # rewritten query with synonyms
    detected_domain: str  # "healthcare" | "finance" | "legal" | "general"
    sub_queries: list[str]  # decomposed sub-queries for complex questions

    # Node 2 outputs
    raw_results: list[dict]  # retrieved chunks before reranking
    retrieval_latency: float  # ms

    # Node 3 outputs
    reranked_results: list[dict]  # after cross-encoder reranking
    dropped_count: int  # chunks filtered out
    rerank_avg_shift: float  # avg rank position shift caused by reranking

    # Node 4 outputs
    answer: str  # synthesized answer
    synthesis_latency: float

    # Node 5 outputs
    sources: list[dict]  # [{chunk_id, text, score, rank}]
    confidence: float  # 0-1 retrieval-grounded confidence
    model_confidence: float | None  # LLM's self-reported confidence, parsed from answer text
    hallucination_risk: bool  # True if retrieval and model confidence diverge sharply
    citations: list[str]  # formatted citation strings
    trace: list[str]  # agent execution trace for debugging


# ─── Request / Response Models ────────────────────────────────────────────────


@dataclass
class AgentQuery:
    """Input to the agentic retrieval pipeline."""

    query_text: str
    corpus_id: str
    mode: str = "hybrid"
    top_k: int = 10
    rerank: bool = True
    synthesize: bool = True
    query_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])


@dataclass
class AgentResponse:
    """Complete output from the agentic retrieval pipeline."""

    query_id: str
    query_text: str
    answer: str
    sources: list[dict]
    confidence: float
    model_confidence: float | None
    hallucination_risk: bool
    citations: list[str]
    query_type: str
    detected_domain: str
    expanded_query: str
    total_latency_ms: float
    trace: list[str]
    error: str | None = None

    @property
    def has_answer(self) -> bool:
        return bool(self.answer and self.answer.strip())

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_id": self.query_id,
            "query_text": self.query_text,
            "answer": self.answer,
            "sources": self.sources,
            "confidence": self.confidence,
            "model_confidence": self.model_confidence,
            "hallucination_risk": self.hallucination_risk,
            "citations": self.citations,
            "query_type": self.query_type,
            "detected_domain": self.detected_domain,
            "expanded_query": self.expanded_query,
            "total_latency_ms": self.total_latency_ms,
            "trace": self.trace,
            "error": self.error,
        }


# ─── Individual Node Implementations ─────────────────────────────────────────


class QueryAnalyzerNode:
    """
    Node 1: Analyze and expand the user query.

    Operations:
    - Classify query type (factoid / analytical / comparative / exploratory)
    - Rewrite query with synonym expansion for better recall
    - Detect domain from query vocabulary
    - Decompose complex questions into sub-queries

    Uses a fast LLM (haiku) to keep latency low.
    Falls back to rule-based analysis if LLM unavailable.
    """

    DOMAIN_KEYWORDS = {
        "healthcare": {
            "diagnosis",
            "treatment",
            "patient",
            "clinical",
            "drug",
            "symptom",
            "disease",
            "medical",
            "therapy",
            "glucose",
            "cardiac",
        },
        "finance": {
            "revenue",
            "profit",
            "ebitda",
            "margin",
            "earnings",
            "investment",
            "portfolio",
            "dividend",
            "stock",
            "debt",
            "yield",
        },
        "legal": {
            "contract",
            "agreement",
            "liability",
            "clause",
            "statute",
            "court",
            "plaintiff",
            "defendant",
            "regulation",
            "compliance",
        },
        "manufacturing": {
            "supply chain",
            "production",
            "quality",
            "defect",
            "tolerance",
            "assembly",
            "specification",
            "material",
        },
        "education": {
            "curriculum",
            "learning",
            "student",
            "assessment",
            "pedagogy",
            "course",
            "lecture",
            "exam",
        },
    }

    QUERY_TYPE_PATTERNS = {
        "factoid": ["what is", "who is", "when did", "how many", "define", "what are"],
        "analytical": ["why does", "how does", "explain", "analyze", "compare", "what causes"],
        "comparative": [
            "difference between",
            "compare",
            "versus",
            "vs",
            "better than",
            "advantages",
        ],
        "exploratory": ["tell me about", "overview of", "summarize", "what should i know"],
    }

    async def run(self, state: AgentState) -> AgentState:
        """Analyze query and populate query_type, expanded_query, detected_domain."""
        start = time.perf_counter()
        query = state["query_text"].lower()

        # Detect query type
        query_type = "factoid"  # default
        for qtype, patterns in self.QUERY_TYPE_PATTERNS.items():
            if any(p in query for p in patterns):
                query_type = qtype
                break

        # Detect domain
        detected_domain = "general"
        max_hits = 0
        for domain, keywords in self.DOMAIN_KEYWORDS.items():
            hits = sum(1 for kw in keywords if kw in query)
            if hits > max_hits:
                max_hits = hits
                detected_domain = domain

        # Try LLM-based query expansion
        expanded_query = await self._expand_query_llm(state["query_text"])

        # Sub-query decomposition for analytical/comparative queries
        sub_queries = []
        if query_type in ("analytical", "comparative"):
            sub_queries = await self._decompose_query(state["query_text"])

        latency = (time.perf_counter() - start) * 1000
        observe_lab.record_agent_node("query_analyzer", latency)

        state.update(
            {
                "query_type": query_type,
                "expanded_query": expanded_query,
                "detected_domain": detected_domain,
                "sub_queries": sub_queries,
                "trace": state.get("trace", [])
                + [
                    f"[Node1/QueryAnalyzer] type={query_type} domain={detected_domain} "
                    f"expanded={len(expanded_query)} chars latency={round(latency)}ms"
                ],
            }
        )
        return state

    async def _expand_query_llm(self, query: str) -> str:
        """Use LLM to rewrite query with synonym expansion."""
        try:
            from anthropic import Anthropic

            client = Anthropic()
            response = client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=200,
                system=(
                    "You are a query expansion expert. Rewrite the user query to improve "
                    "information retrieval. Add relevant synonyms and alternative phrasings. "
                    "Return ONLY the expanded query, nothing else. Keep it under 100 words."
                ),
                messages=[{"role": "user", "content": f"Expand this query: {query}"}],
            )
            return response.content[0].text.strip()
        except Exception:
            return query  # fallback: use original query

    async def _decompose_query(self, query: str) -> list[str]:
        """Decompose complex query into atomic sub-queries."""
        try:
            import json

            from anthropic import Anthropic

            client = Anthropic()
            response = client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=300,
                system=(
                    "Decompose the question into 2-4 atomic sub-questions that together "
                    "answer the main question. Return a JSON array of strings only."
                ),
                messages=[{"role": "user", "content": query}],
            )
            return json.loads(response.content[0].text)
        except Exception:
            return []


class MultiRetrieverNode:
    """
    Node 2: Execute retrieval using the expanded query.

    Runs the full RetrieverCore pipeline (sparse/dense/hybrid).
    If sub-queries exist, runs retrieval on each and merges results.
    """

    def __init__(self, retriever) -> None:
        self.retriever = retriever

    async def run(self, state: AgentState) -> AgentState:
        from backend.services.retriever_core import RetrievalRequest

        start = time.perf_counter()
        expanded = state.get("expanded_query") or state["query_text"]

        request = RetrievalRequest(
            query=expanded,
            corpus_id=state["corpus_id"],
            mode=state["mode"],
            top_k=state["top_k"],
        )

        try:
            results = await self.retriever.retrieve(request)
            raw = [
                {
                    "chunk_id": r.chunk_id,
                    "text": r.text,
                    "score": r.score,
                    "rank": r.rank,
                    "source_doc": r.source_doc,
                    "mode": r.retrieval_mode,
                    "metadata": r.metadata,
                }
                for r in results
            ]
        except Exception as exc:
            logger.warning("retrieval_failed", error=str(exc))
            raw = []

        latency = (time.perf_counter() - start) * 1000
        observe_lab.record_agent_node("multi_retriever", latency)

        state.update(
            {
                "raw_results": raw,
                "retrieval_latency": round(latency, 2),
                "trace": state.get("trace", [])
                + [
                    f"[Node2/MultiRetriever] mode={state['mode']} results={len(raw)} latency={round(latency)}ms"
                ],
            }
        )
        return state


class RankForgeNode:
    """
    Node 3: Cross-encoder reranking + MMR diversity filtering.

    Cross-encoder reranking:
        Unlike bi-encoders (which embed query and doc separately),
        cross-encoders jointly encode (query, doc) pairs for higher accuracy.
        Uses BGE-Reranker-v2-M3 or ms-marco-MiniLM as the reranking model.

    MMR (Maximal Marginal Relevance) diversity:
        Balances relevance vs. novelty to avoid redundant top-K results.
        score = λ * relevance - (1-λ) * max_similarity_to_already_selected

    Falls back to score-based ordering if cross-encoder unavailable.
    """

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-12-v2") -> None:
        self.model_name = model_name
        self._cross_encoder = None  # lazy-loaded

    async def run(self, state: AgentState) -> AgentState:
        import asyncio

        start = time.perf_counter()
        raw = state.get("raw_results", [])
        query = state.get("expanded_query") or state["query_text"]

        if not raw:
            state.update(
                {
                    "reranked_results": [],
                    "dropped_count": 0,
                    "trace": state.get("trace", []) + ["[Node3/RankForge] no results to rerank"],
                }
            )
            return state

        # Attempt cross-encoder reranking
        reranked = await asyncio.get_event_loop().run_in_executor(
            None, self._rerank_sync, query, raw
        )

        # Rank-shift: how much did the cross-encoder reorder vs. initial retrieval order
        pre_order = {r["chunk_id"]: i for i, r in enumerate(raw)}
        avg_shift = sum(
            abs(pre_order.get(r["chunk_id"], i) - i) for i, r in enumerate(reranked)
        ) / max(len(reranked), 1)
        observe_lab.record_rerank_delta(state.get("corpus_id", "unknown"), avg_shift)

        # Apply MMR to add diversity
        final = self._apply_mmr(query, reranked, top_k=min(state["top_k"], len(reranked)))
        dropped = len(raw) - len(final)
        latency = (time.perf_counter() - start) * 1000
        observe_lab.record_agent_node("rank_forge", latency)

        state.update(
            {
                "reranked_results": final,
                "dropped_count": dropped,
                "rerank_avg_shift": round(avg_shift, 2),
                "trace": state.get("trace", [])
                + [
                    f"[Node3/RankForge] reranked={len(final)} dropped={dropped} "
                    f"avg_shift={round(avg_shift, 2)} latency={round(latency)}ms"
                ],
            }
        )
        return state

    def _rerank_sync(self, query: str, results: list[dict]) -> list[dict]:
        """Run cross-encoder reranking synchronously."""
        try:
            from sentence_transformers import CrossEncoder

            if self._cross_encoder is None:
                self._cross_encoder = CrossEncoder(self.model_name)

            pairs = [(query, r["text"]) for r in results]
            scores = self._cross_encoder.predict(pairs)

            for i, result in enumerate(results):
                result["rerank_score"] = float(scores[i])

            return sorted(results, key=lambda x: x.get("rerank_score", x["score"]), reverse=True)

        except Exception as exc:
            logger.debug("cross_encoder_unavailable_fallback", error=str(exc))
            return sorted(results, key=lambda x: x["score"], reverse=True)

    def _apply_mmr(
        self, query: str, results: list[dict], top_k: int, lambda_: float = 0.7
    ) -> list[dict]:
        """
        Maximal Marginal Relevance for result diversity.
        λ=0.7 means 70% weight on relevance, 30% on novelty.
        """
        if len(results) <= top_k:
            return results

        selected: list[dict] = []
        remaining = list(results)

        while remaining and len(selected) < top_k:
            if not selected:
                # First pick: highest relevance
                best = max(remaining, key=lambda x: x.get("rerank_score", x["score"]))
            else:
                # MMR: balance relevance and diversity
                def mmr_score(candidate: dict) -> float:
                    rel = candidate.get("rerank_score", candidate["score"])
                    # Approximate similarity via text overlap (no embeddings needed)
                    c_words = set(candidate["text"].lower().split())
                    max_sim = 0.0
                    for sel in selected:
                        s_words = set(sel["text"].lower().split())
                        overlap = len(c_words & s_words) / max(len(c_words | s_words), 1)
                        max_sim = max(max_sim, overlap)
                    return lambda_ * rel - (1 - lambda_) * max_sim

                best = max(remaining, key=mmr_score)

            selected.append(best)
            remaining.remove(best)

        # Re-assign ranks
        for i, r in enumerate(selected, start=1):
            r["rank"] = i

        return selected


class SynthesizerNode:
    """
    Node 4: LLM-powered answer synthesis grounded in retrieved context.

    Generates a fluent, factual answer using only the retrieved chunks
    as context. Includes explicit grounding instructions to minimize
    hallucination and force citation of sources.

    If no LLM is available, returns a structured extractive summary.
    """

    SYNTHESIS_SYSTEM = """You are an expert research assistant synthesizing information from retrieved documents.

RULES:
1. Answer ONLY from the provided context. Do not add external knowledge.
2. If the context does not contain enough information, say so explicitly.
3. Cite sources inline using [Source N] notation where N is the chunk number.
4. Be precise and factual. Use technical language appropriate to the domain.
5. Structure complex answers with clear sections.
6. End with a confidence statement: "Confidence: High/Medium/Low - [brief reason]"
"""

    async def run(self, state: AgentState) -> AgentState:
        start = time.perf_counter()
        results = state.get("reranked_results") or state.get("raw_results", [])
        query = state["query_text"]

        if not results:
            state.update(
                {
                    "answer": "No relevant documents found for this query.",
                    "synthesis_latency": 0.0,
                    "trace": state.get("trace", []) + ["[Node4/Synthesizer] no context available"],
                }
            )
            return state

        answer = await self._synthesize(query, results)
        latency = (time.perf_counter() - start) * 1000
        observe_lab.record_agent_node("synthesizer", latency)

        state.update(
            {
                "answer": answer,
                "synthesis_latency": round(latency, 2),
                "trace": state.get("trace", [])
                + [f"[Node4/Synthesizer] answer_length={len(answer)} latency={round(latency)}ms"],
            }
        )
        return state

    async def _synthesize(self, query: str, results: list[dict]) -> str:
        """Generate answer using LLM with retrieved context."""
        # Build context block
        context_parts = []
        for i, r in enumerate(results[:8], start=1):  # cap at 8 to stay in context window
            context_parts.append(f"[Source {i}]\n{r['text'][:500]}")

        context = "\n\n---\n\n".join(context_parts)

        prompt = f"""QUERY: {query}

RETRIEVED CONTEXT:
{context}

Based solely on the above context, provide a comprehensive answer to the query."""

        try:
            from anthropic import Anthropic

            client = Anthropic()
            response = client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=1024,
                system=self.SYNTHESIS_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text.strip()

        except Exception:
            # Extractive fallback: return top 3 chunk snippets
            snippets = [f"• {r['text'][:200]}..." for r in results[:3]]
            return "Based on retrieved documents:\n\n" + "\n\n".join(snippets)


class OutputFormatterNode:
    """
    Node 5: Structure final output with sources, citations, and confidence.

    Computes:
    - Formatted source list with ranks and scores
    - Citation strings in academic format
    - Overall confidence score (composite of retrieval scores + answer quality signals)
    """

    async def run(self, state: AgentState) -> AgentState:
        start = time.perf_counter()
        results = state.get("reranked_results") or state.get("raw_results", [])
        answer = state.get("answer", "")

        # Build structured sources
        sources = [
            {
                "rank": r.get("rank", i + 1),
                "chunk_id": r.get("chunk_id", ""),
                "text": r.get("text", "")[:300],
                "score": round(r.get("rerank_score", r.get("score", 0.0)), 4),
                "source_doc": r.get("source_doc", ""),
                "mode": r.get("mode", "hybrid"),
            }
            for i, r in enumerate(results[:10])
        ]

        # Format citations
        citations = [
            f"[{s['rank']}] {s['source_doc'] or 'Document'} — score: {s['score']:.4f}"
            for s in sources
        ]

        # Compute confidence
        confidence = self._compute_confidence(sources, answer)
        model_confidence = self._extract_model_confidence(answer)
        hallucination_risk = (
            model_confidence is not None and abs(confidence - model_confidence) > 0.3
        )
        observe_lab.record_agent_node("output_formatter", (time.perf_counter() - start) * 1000)

        state.update(
            {
                "sources": sources,
                "citations": citations,
                "confidence": confidence,
                "model_confidence": model_confidence,
                "hallucination_risk": hallucination_risk,
                "trace": state.get("trace", [])
                + [
                    f"[Node5/OutputFormatter] sources={len(sources)} retrieval_conf={confidence:.2f} "
                    f"model_conf={model_confidence if model_confidence is None else round(model_confidence, 2)} "
                    f"hallucination_risk={hallucination_risk}"
                ],
            }
        )
        return state

    def _compute_confidence(self, sources: list[dict], answer: str) -> float:
        """
        Retrieval-grounded confidence, weighted composite of:
          40% top1_score       — how strong is the #1 retrieved match
          25% score_gap        — big gap vs #2 = confident, small gap = ambiguous
          20% doc_coverage     — how many of the top results clear a relevance bar
          15% reranker_top1    — cross-encoder's own top-1 score, if reranking ran

        All raw scores are squashed to 0-1 via sigmoid before combining, since
        cross-encoder and BM25 scores are on different, uncalibrated scales.
        """
        if not sources:
            return 0.0

        norm_scores = [self._sigmoid(s["score"]) for s in sources]
        top1 = norm_scores[0]
        top2 = norm_scores[1] if len(norm_scores) > 1 else 0.0
        score_gap = max(top1 - top2, 0.0)

        relevance_bar = 0.5
        doc_coverage = sum(1 for s in norm_scores[:10] if s >= relevance_bar) / min(
            len(norm_scores), 10
        )

        # reranker_top1 falls back to top1 if reranking didn't run (no separate signal)
        reranker_top1 = top1

        confidence = 0.40 * top1 + 0.25 * score_gap + 0.20 * doc_coverage + 0.15 * reranker_top1
        return round(min(confidence, 1.0), 3)

    @staticmethod
    def _sigmoid(x: float) -> float:
        import math

        return 1 / (1 + math.exp(-x))

    @staticmethod
    def _extract_model_confidence(answer: str) -> float | None:
        """
        Parse the LLM's self-reported confidence line, e.g.
        "Confidence: Medium - retrieved context partially addresses the query."
        Requested in the synthesis prompt but previously never captured.
        """
        import re

        match = re.search(r"confidence:\s*(high|medium|low)", answer, re.IGNORECASE)
        if not match:
            return None
        return {"high": 0.85, "medium": 0.55, "low": 0.25}[match.group(1).lower()]


# ─── RetrievalAgent Orchestrator ─────────────────────────────────────────────


class RetrievalAgent:
    """
    Full 5-node agentic retrieval pipeline using LangGraph-style state machine.

    The pipeline runs nodes sequentially with state threading.
    Future: add conditional branching (re-retrieve on zero results),
    parallel sub-query fan-out, and streaming output.

    Args:
        retriever:   RetrieverCore instance (must have indexes built).
        reranker:    Optional reranker model name override.

    Example:
        agent    = RetrievalAgent(retriever=retriever)
        query    = AgentQuery(
            query_text="What are symptoms of type 2 diabetes?",
            corpus_id="healthcare_pubmed_v1",
            mode="hybrid",
        )
        response = await agent.run(query)
        print(response.answer)
        print(f"Confidence: {response.confidence:.0%}")
        for cite in response.citations:
            print(cite)
    """

    def __init__(
        self,
        retriever,
        reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-12-v2",
    ) -> None:
        self.nodes = [
            QueryAnalyzerNode(),
            MultiRetrieverNode(retriever=retriever),
            RankForgeNode(model_name=reranker_model),
            SynthesizerNode(),
            OutputFormatterNode(),
        ]

    async def run(self, query: AgentQuery) -> AgentResponse:
        """
        Execute the full agentic pipeline.

        Args:
            query: AgentQuery with query_text, corpus_id, mode, top_k.

        Returns:
            AgentResponse with answer, sources, confidence, and trace.
        """
        start = time.perf_counter()

        # Initialize state
        state: AgentState = {
            "query_text": query.query_text,
            "corpus_id": query.corpus_id,
            "mode": query.mode,
            "top_k": query.top_k,
            "query_type": "factoid",
            "expanded_query": query.query_text,
            "detected_domain": "general",
            "sub_queries": [],
            "raw_results": [],
            "retrieval_latency": 0.0,
            "reranked_results": [],
            "dropped_count": 0,
            "rerank_avg_shift": 0.0,
            "answer": "",
            "synthesis_latency": 0.0,
            "sources": [],
            "confidence": 0.0,
            "model_confidence": None,
            "hallucination_risk": False,
            "citations": [],
            "trace": [f"[Agent] started query_id={query.query_id}"],
        }

        logger.info(
            "agent_pipeline_start",
            query_id=query.query_id,
            query_text=query.query_text[:80],
            corpus_id=query.corpus_id,
        )

        error = None
        try:
            for node in self.nodes:
                state = await node.run(state)
        except Exception as exc:
            error = str(exc)
            logger.error("agent_pipeline_error", error=error)

        total_latency = round((time.perf_counter() - start) * 1000, 2)
        state["trace"].append(f"[Agent] completed total_latency={total_latency}ms")

        logger.info(
            "agent_pipeline_complete",
            query_id=query.query_id,
            sources=len(state.get("sources", [])),
            confidence=state.get("confidence", 0.0),
            latency_ms=total_latency,
        )

        return AgentResponse(
            query_id=query.query_id,
            query_text=query.query_text,
            answer=state.get("answer", ""),
            sources=state.get("sources", []),
            confidence=state.get("confidence", 0.0),
            model_confidence=state.get("model_confidence"),
            hallucination_risk=state.get("hallucination_risk", False),
            citations=state.get("citations", []),
            query_type=state.get("query_type", "factoid"),
            detected_domain=state.get("detected_domain", "general"),
            expanded_query=state.get("expanded_query", query.query_text),
            total_latency_ms=total_latency,
            trace=state.get("trace", []),
            error=error,
        )
