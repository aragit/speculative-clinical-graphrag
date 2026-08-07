import os
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from api.schemas import (
    SpeculateRequest, SpeculateResponse, ReasoningTraceResponse,
    HealthResponse, OverrideRequest, OverrideResponse,
)
from api.dependencies import get_llm_router, get_neo4j_verifier, get_symbolic_verifier, get_opa_client
from api.middleware import RequestIDMiddleware, APIKeyMiddleware, RateLimitMiddleware
from core.workflow import SpeculativeGraphRAG
from core.llm_backend import MockLLMBackend
from core.mas_streamer import MASStreamer
from core.evolutio import OverrideAnalytics
from core.persistence import get_trace_store, TraceStore

logger = logging.getLogger(__name__)

trace_store: TraceStore = get_trace_store()

@asynccontextmanager
async def lifespan(app: FastAPI):
    verifier = get_neo4j_verifier()
    try:
        await verifier.seed_mock_ontology_async()
        logger.info("Startup: mock ontology seeded.")
    except Exception as e:
        logger.warning(f"Startup: Neo4j seed failed (may already be seeded): {e}")
    yield
    get_neo4j_verifier().close()
    logger.info("Shutdown: Neo4j connection closed.")

app = FastAPI(
    title="Speculative Clinical GraphRAG",
    description="Type 2→6 Neuro-Symbolic Hybrid Clinical Decision Support",
    version="0.6.0",
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
llm_router = get_llm_router()
verifier = get_neo4j_verifier()
symbolic = get_symbolic_verifier()
rag = SpeculativeGraphRAG(
    router=llm_router,
    verifier=verifier,
    symbolic_verifier=symbolic,
    max_iterations=3,
)

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
        version="0.6.0",
    )

@app.post("/v1/speculate", response_model=SpeculateResponse)
async def speculate(request: SpeculateRequest, fastapi_request: Request):
    try:
        ab_variant = fastapi_request.headers.get("X-AB-Variant")
        ab_seed = fastapi_request.headers.get("X-AB-Seed", "")
        result = await rag.run(
            patient_note=request.patient_note,
            patient_context=request.patient_context,
            backend_key=request.preferred_backend,
        )
        # result is GraphState (pydantic) or dict for backward compat
        get = lambda key, default="": result.get(key, default) if isinstance(result, dict) else getattr(result, key, default)
        get_list = lambda key: result.get(key, []) if isinstance(result, dict) else getattr(result, key, [])
        get_dict = lambda key: result.get(key, {}) if isinstance(result, dict) else getattr(result, key, {})
        trace_id = os.urandom(8).hex()
        ab_metadata = {
            "variant": ab_variant,
            "seed": ab_seed,
            "backend_key": get("backend_key", ""),
            "selection_reason": "manual_header" if ab_variant else "semantic_router",
        }
        trace_record = {
            "trace_id": trace_id,
            "reasoning_trace": get("reasoning_trace", ""),
            "reasoning_history": get_list("reasoning_history"),
            "surface_output": get("final_output", ""),
            "validation_history": get_list("audit_log"),
            "escalation_reason": None if get("status") != "escalated" else get("final_output", ""),
            "status": get("status"),
            "validation_mode": get("validation_mode", "symbolic_only"),
            "backend_key": get("backend_key", ""),
            "patient_note": request.patient_note,
            "ab_variant": ab_variant,
            "ab_metadata": ab_metadata,
            "created_at": datetime.utcnow().isoformat(),
        }
        await trace_store.save(trace_id, trace_record)
        return SpeculateResponse(
            proposed_path=get_list("proposed_path"),
            validation=get_dict("validation_result"),
            iterations=get("iteration_count", 0),
            final_output=get("final_output", ""),
            status=get("status", "error"),
            reasoning_trace=get("reasoning_trace", ""),
            reasoning_history=get_list("reasoning_history"),
            retrieval_sources=[
                {"symptom": sym, "mapped_conditions": len(edges)}
                for sym, edges in get_dict("ontology_mappings").items()
            ] if get_dict("ontology_mappings") else None,
            audit_log=get_list("audit_log"),
            validation_mode=get("validation_mode", "symbolic_only"),
            ab_variant=ab_variant,
            ab_metadata=ab_metadata,
        )
    except Exception as e:
        logger.exception("speculate failed")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/v1/reasoning_trace/{trace_id}", response_model=ReasoningTraceResponse)
async def reasoning_trace(trace_id: str):
    t = await trace_store.get(trace_id)
    if t is None:
        raise HTTPException(status_code=404, detail="Trace ID not found")
    return ReasoningTraceResponse(
        trace_id=t["trace_id"],
        reasoning_trace=t["reasoning_trace"],
        surface_output=t["surface_output"],
        validation_history=t["validation_history"],
        escalation_reason=t.get("escalation_reason"),
        ab_variant=t.get("ab_variant"),
        ab_metadata=t.get("ab_metadata"),
    )


@app.post("/v1/override", response_model=OverrideResponse)
async def override_trace(request: OverrideRequest):
    """
    Human-in-the-Loop override endpoint.
    Allows a clinician to approve, reject, or modify an escalated trace.
    """
    trace = await trace_store.get(request.trace_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="Trace ID not found")

    if trace.get("escalation_reason") is None and trace.get("status") != "escalated":
        raise HTTPException(
            status_code=400,
            detail=f"Trace {request.trace_id} is not in an escalated state (current status: {trace.get('status', 'unknown')}). Only escalated traces can be overridden.",
        )

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

    success = await trace_store.update(request.trace_id, trace)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to persist override")

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


@app.get("/v1/metrics/backends")
async def backend_metrics():
    return {
        "backends": rag.router_backend.get_metrics(),
        "default_backend": rag.router_backend.default,
    }


@app.get("/v1/agents/health")
async def agent_health():
    return {
        "agents": {
            agent.name: {
                "health": agent.health,
                "executions": agent.execution_count,
                "avg_latency_ms": round(agent.avg_latency_ms, 2),
                "error_count": agent.error_count,
                "last_executed": agent.last_executed.isoformat() if agent.last_executed else None,
            }
            for agent in rag.agent_registry.list_all()
        }
    }


@app.get("/v1/analytics/overrides")
async def override_analytics(hours: int = 24):
    analytics = OverrideAnalytics(trace_store)
    return await analytics.analyze_recent(hours=hours)


@app.post("/v1/analytics/rules/{rule_id}/approve")
async def approve_rule_endpoint(rule_id: int):
    analytics = OverrideAnalytics(trace_store)
    await analytics.analyze_recent()
    success = await analytics.approve_rule(rule_id)
    if not success:
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"status": "approved", "rule": analytics.proposed_rules[rule_id]}


@app.post("/v1/analytics/rules/{rule_id}/reject")
async def reject_rule_endpoint(rule_id: int):
    analytics = OverrideAnalytics(trace_store)
    await analytics.analyze_recent()
    success = await analytics.reject_rule(rule_id)
    if not success:
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"status": "rejected"}


@app.get("/v1/policy/stats")
async def policy_stats():
    if not rag.enable_neural_policy:
        return {"enabled": False}
    return {
        "enabled": True,
        "accuracy": rag.neural_policy.get_accuracy(),
        "history_size": len(rag.neural_policy.history),
        "learning_enabled": rag.neural_policy.enable_learning,
    }


@app.post("/v1/analytics/rules/apply")
async def apply_rules():
    analytics = OverrideAnalytics(trace_store)
    result = await analytics.apply_approved_rules()

    if result["applied"] > 0:
        new_count = get_symbolic_verifier().hot_reload()
        result["symbolic_rules_loaded"] = new_count

    return result


@app.post("/v1/admin/policy/train")
async def train_policy(admin_key: str):
    expected = os.getenv("ADMIN_API_KEY", "")
    if not expected or admin_key != expected:
        raise HTTPException(status_code=403, detail="Invalid admin key")

    if not rag.enable_neural_policy:
        raise HTTPException(status_code=400, detail="Neural policy not enabled")

    from core.rlhf_trainer import RLHFTrainer
    trainer = RLHFTrainer(rag.neural_policy)

    exported = trainer.export_dataset()
    result = trainer.train(epochs=100)

    if result["status"] == "trained":
        trainer.load_model()
        rag.neural_policy.load_trained_weights(trainer.weights, trainer.bias)

    return {
        "exported_examples": exported,
        "training_result": result,
    }


@app.get("/v1/admin/policy/evaluate")
async def evaluate_policy(admin_key: str):
    expected = os.getenv("ADMIN_API_KEY", "")
    if not expected or admin_key != expected:
        raise HTTPException(status_code=403, detail="Invalid admin key")

    from core.rlhf_trainer import RLHFTrainer
    trainer = RLHFTrainer(rag.neural_policy)

    test_cases = [
        {"features": r["features"], "expected_action": r["actual"]}
        for r in rag.neural_policy.history
    ]

    result = trainer.evaluate_vs_static(test_cases)
    return result
