import os
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Dict

from core.llm_backend import MockLLMBackend, OllamaBackend
from core.verification_layer import Neo4jVerifier
from core.workflow import SpeculativeGraphRAG


app = FastAPI(
    title="Speculative Graph RAG",
    description="Self-correcting clinical knowledge core",
    version="0.1.0",
)

llm_mode = os.getenv("RUNTIME_LLM", "mock")
if llm_mode == "ollama":
    llm = OllamaBackend(
        model=os.getenv("LLM_MODEL", "gemma2:2b"),
        host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
    )
else:
    llm = MockLLMBackend()

verifier = Neo4jVerifier()
rag = SpeculativeGraphRAG(llm=llm, verifier=verifier, max_iterations=3)


class SpeculateRequest(BaseModel):
    patient_note: str


class SpeculateResponse(BaseModel):
    proposed_path: List[Dict]
    validation: Dict
    iterations: int
    final_output: str
    status: str


@app.on_event("startup")
async def startup():
    verifier.seed_mock_taxonomy()


@app.on_event("shutdown")
async def shutdown():
    verifier.close()


@app.get("/health")
async def health():
    return {"status": "ok", "llm_mode": llm_mode}


@app.post("/v1/speculate", response_model=SpeculateResponse)
async def speculate(request: SpeculateRequest):
    result = rag.run(request.patient_note)
    return SpeculateResponse(
        proposed_path=result["proposed_path"],
        validation=result["validation_result"],
        iterations=result["iteration_count"],
        final_output=result["final_output"],
        status=result["status"],
    )
