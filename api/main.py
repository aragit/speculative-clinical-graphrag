import os
import json
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from api.schemas import (
    SpeculateRequest, SpeculateResponse, ReasoningTraceResponse,
    HealthResponse, OverrideRequest, OverrideResponse,
)
from api.dependencies import get_neo4j_verifier, get_symbolic_verifier, get_opa_client, get_llm_backend
from api.middleware import RequestIDMiddleware, APIKeyMiddleware, RateLimitMiddleware
from core.workflow import SpeculativeGraphRAG
from core.llm_backend import MockLLMBackend
from core.mas_streamer import MASStreamer

logger = logging.getLogger(__name__)

_trace_store: dict = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    verifier = get_neo4j_verifier()
    try:
        verifier.seed_mock_ontology()
        logger.info("Startup: mock ontology seeded.")
    except Exception as e:
        logger.warning(f"Startup: Neo4j seed failed (may already be seeded): {e}")
    yield
    get_neo4j_verifier().close()
    logger.info("Shutdown: Neo4j connection closed.")

app = FastAPI(
    title="Speculative Clinical GraphRAG",
    description="Type 2→6 Neuro-Symbolic Hybrid Clinical Decision Support",
    version="0.3.0",
    lifespan=lifespan,
)

app.add_middleware(RequestIDMiddleware)
app.add_middleware(APIKeyMiddleware)
app.add_middleware(RateLimitMiddleware)
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
    redis_ok = False
    try:
        from neo4j import GraphDatabase
        d = GraphDatabase.driver(
            os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "speculative123")),
        )
        d.verify_connectivity()
        d.close()
        neo_ok = True
    except Exception:
        pass
    try:
        import httpx
        r = httpx.get(
            os.getenv("QDRANT_HOST", "http://localhost:6333").rstrip("/") + "/", timeout=2.0
        )
        qdrant_ok = r.status_code < 500
    except Exception:
        pass
    try:
        import httpx
        r = httpx.get(
            os.getenv("OPA_URL", "http://localhost:8181").rstrip("/") + "/health", timeout=2.0
        )
        opa_ok = r.status_code < 500
    except Exception:
        pass
    try:
        import redis.asyncio as redis
        r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
        await r.ping()
        await r.aclose()
        redis_ok = True
    except Exception:
        pass
    return HealthResponse(
        status="ok",
        llm_mode=llm_mode,
        neo4j_connected=neo_ok,
        qdrant_connected=qdrant_ok,
        opa_connected=opa_ok,
        version="0.3.0",
    )

@app.post("/v1/speculate", response_model=SpeculateResponse)
async def speculate(request: SpeculateRequest):
    try:
        result = await rag.run(
            patient_note=request.patient_note,
            patient_context=request.patient_context,
            backend_key=request.preferred_backend,
        )
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


@app.post("/v1/override", response_model=OverrideResponse)
async def override_trace(request: OverrideRequest):
    """
    Human-in-the-Loop override endpoint.
    Allows a clinician to approve, reject, or modify an escalated trace.
    """
    if request.trace_id not in _trace_store:
        raise HTTPException(status_code=404, detail="Trace ID not found")

    trace = _trace_store[request.trace_id]

    # Verify trace is in an escalated state
    if trace.get("escalation_reason") is None and trace.get("status") != "escalated":
        raise HTTPException(
            status_code=400,
            detail=f"Trace {request.trace_id} is not in an escalated state (current status: {trace.get('status', 'unknown')}). Only escalated traces can be overridden.",
        )

    # Apply override action
    if request.override_action == "approve":
        trace["status"] = "clinician_approved"
        trace["escalation_reason"] = None
        trace["clinician_notes"] = request.clinician_notes
        trace["override_action"] = "approve"
        surface_output = trace.get("surface_output", "")
        logger.info(f"Trace {request.trace_id} approved by clinician")

    elif request.override_action == "reject":
        trace["status"] = "clinician_rejected"
        trace["clinician_notes"] = request.clinician_notes
        trace["override_action"] = "reject"
        surface_output = f"Clinician rejected the proposed pathway. Notes: {request.clinician_notes}"
        trace["surface_output"] = surface_output
        logger.info(f"Trace {request.trace_id} rejected by clinician")

    elif request.override_action == "modify":
        if not request.modified_path:
            raise HTTPException(
                status_code=400,
                detail="'modified_path' is required when override_action is 'modify'",
            )
        trace["status"] = "clinician_modified"
        trace["escalation_reason"] = None
        trace["modified_path"] = request.modified_path
        trace["clinician_notes"] = request.clinician_notes
        trace["override_action"] = "modify"
        surface_output = json.dumps({
            "modified_path": request.modified_path,
            "clinician_notes": request.clinician_notes,
            "original_trace_id": request.trace_id,
        }, indent=2)
        trace["surface_output"] = surface_output
        logger.info(f"Trace {request.trace_id} modified by clinician")

    else:
        raise HTTPException(status_code=400, detail=f"Invalid override_action: {request.override_action}")

    return OverrideResponse(
        trace_id=request.trace_id,
        status=trace["status"],
        override_action=request.override_action,
        clinician_notes=request.clinician_notes,
        surface_output=trace.get("surface_output"),
        modified_path=trace.get("modified_path"),
    )


@app.post("/v1/chat/stream")
async def stream_clinical_reasoning(request: SpeculateRequest):
    """SSE streaming endpoint that emits MAS events as the multi-agent workflow executes."""
    streamer = MASStreamer(workflow=rag)

    async def event_generator():
        try:
            async for event in streamer.stream(
                patient_note=request.patient_note,
                patient_context=request.patient_context,
            ):
                yield f"data: {event.model_dump_json()}\n\n"
        except Exception as e:
            logger.exception("SSE stream failed")
            error_event = json.dumps({
                "event_type": "ERROR",
                "detail": str(e),
            })
            yield f"data: {error_event}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
