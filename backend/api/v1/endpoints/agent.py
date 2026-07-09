# =============================================================================
# RetrievalLab — backend/api/v1/endpoints/agent.py
# =============================================================================
# PURPOSE : FastAPI router exposing the 5-node agentic retrieval pipeline.
#
# ENDPOINTS:
#   POST /api/v1/agent/query        → full agentic pipeline (analyze→retrieve→rerank→synthesize)
#   POST /api/v1/agent/query/stream → streaming token output (SSE)
#   GET  /api/v1/agent/status       → pipeline health check
#
# INPUT  : AgentQuerySchema with query_text, corpus_id, mode, top_k
# OUTPUT : Full AgentResponse with answer, sources, confidence, trace
# =============================================================================

from __future__ import annotations

import time
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.base import get_db
from backend.agents.retrieval_agent import RetrievalAgent, AgentQuery

logger = structlog.get_logger(__name__)
router = APIRouter()

# Module-level agent singleton
_agent: RetrievalAgent | None = None


def _get_agent() -> RetrievalAgent:
    """Lazy-initialize agent with retriever stack."""
    global _agent
    if _agent is None:
        from backend.api.v1.endpoints.retrieve import _get_retriever
        retriever = _get_retriever()
        _agent = RetrievalAgent(retriever=retriever)
    return _agent


# ─── Schemas ──────────────────────────────────────────────────────────────────

class AgentQuerySchema(BaseModel):
    query_text:  str  = Field(..., min_length=3, max_length=2048, description="Natural language query")
    corpus_id:   str  = Field(..., description="Target corpus identifier")
    mode:        str  = Field(default="hybrid", description="Retrieval mode: sparse|dense|hybrid")
    top_k:       int  = Field(default=10, ge=1, le=50)
    rerank:      bool = Field(default=True, description="Apply cross-encoder reranking")
    synthesize:  bool = Field(default=True, description="Generate LLM answer synthesis")


class AgentResponseSchema(BaseModel):
    query_id:         str
    query_text:       str
    answer:           str
    sources:          list[dict]
    confidence:       float
    model_confidence:   float | None = None
    hallucination_risk: bool = False
    citations:        list[str]
    query_type:       str
    detected_domain:  str
    expanded_query:   str
    total_latency_ms: float
    trace:            list[str]
    error:            str | None = None


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post(
    "/query",
    response_model=AgentResponseSchema,
    summary="Agentic retrieval query",
    description=(
        "Execute the full 5-node agentic pipeline: "
        "Query Analysis → Multi-Retrieval → RankForge Reranking → LLM Synthesis → Output Formatting. "
        "Returns a synthesized answer with source citations and confidence score."
    ),
)
async def agent_query(
    body: AgentQuerySchema,
    db:   AsyncSession = Depends(get_db),
) -> AgentResponseSchema:
    """Run the complete agentic retrieval pipeline."""
    agent = _get_agent()

    # Ensure index is built
    from backend.api.v1.endpoints.retrieve import _ensure_index_built
    await _ensure_index_built(body.corpus_id, body.mode, agent.nodes[1].retriever, db)

    query = AgentQuery(
        query_text = body.query_text,
        corpus_id  = body.corpus_id,
        mode       = body.mode,
        top_k      = body.top_k,
        rerank     = body.rerank,
        synthesize = body.synthesize,
    )

    response = await agent.run(query)

    if response.error and not response.answer:
        raise HTTPException(status_code=500, detail=f"Agent pipeline failed: {response.error}")

    return AgentResponseSchema(**response.to_dict())


@router.get(
    "/status",
    summary="Agent pipeline status",
)
async def agent_status() -> dict[str, Any]:
    """Return the status of all agent nodes."""
    return {
        "pipeline": "5-node LangGraph retrieval agent",
        "nodes": [
            {"name": "QueryAnalyzer",    "status": "ready", "description": "Query expansion + type classification"},
            {"name": "MultiRetriever",   "status": "ready", "description": "Sparse + dense + hybrid retrieval"},
            {"name": "RankForge",        "status": "ready", "description": "Cross-encoder reranking + MMR diversity"},
            {"name": "Synthesizer",      "status": "ready", "description": "LLM answer synthesis with grounding"},
            {"name": "OutputFormatter",  "status": "ready", "description": "Citation formatting + confidence scoring"},
        ],
        "reranker_model": "cross-encoder/ms-marco-MiniLM-L-12-v2",
        "synthesizer_model": "claude-3-5-haiku-20241022",
    }
