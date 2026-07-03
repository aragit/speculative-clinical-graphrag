import os
import json
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from api.schemas import SpeculateRequest, SpeculateResponse, ReasoningTraceResponse, HealthResponse
from api.dependencies import get_neo4j_verifier, get_symbolic_verifier, get_opa_client, get_llm_backend
from api.middleware import RequestIDMiddleware
from core.workflow import SpeculativeGraphRAG
from core.llm_backend import MockLLMBackend

logger = logging.getLogger(__name__)

# In-memory trace store for reasoning traces (ephemeral, no PHI persistence)
_trace_store: dict = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    verifier = get_neo4j_verifier()
    try:
        verifier.seed_mock_ontology()
        logger.info("Startup: mock ontology seeded.")
    except Exception as e:
        logger.warning(f"Startup: Neo4j seed failed (may already be seeded): {e}")
    yield
    # Shutdown
    get_neo4j_verifier().close()
    logger.info("Shutdown: Neo4j connection closed.")

app = FastAPI(
    title="Speculative Clinical GraphRAG",
    description="Type 2→6 Neuro-Symbolic Hybrid Clinical Decision Support",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

llm_mode = os.getenv("RUNTIME_LLM", "mock")
llm = get_llm_backend(llm_mode)
verifier = get_neo4j_verifier()
symbolic = get_symbolic_verifier()
rag = SpeculativeGraphRAG(llm=llm, verifier=verifier, symbolic_verifier=symbolic, max_iterations=3)

@app.get("/health", response_model=HealthResponse)
async def health():
    neo_ok = False
    qdrant_ok = False
    opa_ok = False
    try:
        from neo4j import GraphDatabase
        d = GraphDatabase.driver(os.getenv("NEO4J_URI", "bolt://localhost:7687"), auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "speculative123")))
        d.verify_connectivity()
        d.close()
        neo_ok = True
    except Exception:
        pass
    try:
        import httpx
        r = httpx.get(os.getenv("QDRANT_HOST", "http://localhost:6333").rstrip("/") + "/", timeout=2.0)
        qdrant_ok = r.status_code < 500
    except Exception:
        pass
    try:
        import httpx
        r = httpx.get(os.getenv("OPA_URL", "http://localhost:8181").rstrip("/") + "/health", timeout=2.0)
        opa_ok = r.status_code < 500
    except Exception:
        pass
    return HealthResponse(
        status="ok",
        llm_mode=llm_mode,
        neo4j_connected=neo_ok,
        qdrant_connected=qdrant_ok,
        opa_connected=opa_ok,
    )

@app.post("/v1/speculate", response_model=SpeculateResponse)
async def speculate(request: SpeculateRequest):
    try:
        result = rag.run(
            patient_note=request.patient_note,
            patient_context=request.patient_context,
            backend_key=request.preferred_backend,
        )
        # Store trace for /v1/reasoning_trace retrieval
        trace_id = os.urandom(8).hex()
        _trace_store[trace_id] = {
            "trace_id": trace_id,
            "reasoning_trace": result.get("reasoning_trace", ""),
            "surface_output": result.get("final_output", ""),
            "validation_history": result.get("audit_log", []),
            "escalation_reason": None if result["status"] != "escalated" else result.get("final_output", ""),
        }
        return SpeculateResponse(
            proposed_path=result["proposed_path"],
            validation=result["validation_result"],
            iterations=result["iteration_count"],
            final_output=result["final_output"],
            status=result["status"],
            reasoning_trace=result.get("reasoning_trace"),
            retrieval_sources=[
                {"symptom": sym, "mapped_conditions": len(edges)}
                for sym, edges in result.get("ontology_mappings", {}).items()
            ] if result.get("ontology_mappings") else None,
            audit_log=result.get("audit_log"),
        )
    except Exception as e:
        logger.exception("speculate failed")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/v1/reasoning_trace/{trace_id}", response_model=ReasoningTraceResponse)
async def reasoning_trace(trace_id: str):
    if trace_id not in _trace_store:
        raise HTTPException(status_code=404, detail="Trace ID not found")
    t = _trace_store[trace_id]
    return ReasoningTraceResponse(
        trace_id=t["trace_id"],
        reasoning_trace=t["reasoning_trace"],
        surface_output=t["surface_output"],
        validation_history=t["validation_history"],
        escalation_reason=t["escalation_reason"],
    )
