<h1 align="center">Speculative Clinical GraphRAG</h1>
<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-blue" alt="Python 3.12">
  <img src="https://img.shields.io/badge/FastAPI-0.110-009688" alt="FastAPI 0.110">
  <img src="https://img.shields.io/badge/Pydantic-2.6-E92063" alt="Pydantic 2.6">
  <img src="https://img.shields.io/badge/Neo4j-5-008CC1" alt="Neo4j 5">
  <img src="https://img.shields.io/badge/LangGraph-1.2.7-1C3C3C" alt="LangGraph 1.2.7">
  <img src="https://img.shields.io/badge/Qdrant-1.7-EB5245" alt="Qdrant 1.7">
  <img src="https://img.shields.io/badge/Redis-7-DC382D" alt="Redis 7">
  <img src="https://img.shields.io/badge/OPA-0.68-7A5CF7" alt="OPA 0.68">
  <img src="https://img.shields.io/badge/vLLM-0.6-00A86B" alt="vLLM 0.6">
  <img src="https://img.shields.io/badge/OpenTelemetry-1.22-4A154B" alt="OpenTelemetry 1.22">
  <img src="https://img.shields.io/badge/OpenAI-1.12-412991" alt="OpenAI 1.12">
  <img src="https://img.shields.io/badge/Docker-27.0-2496ED" alt="Docker 27.0">
  <img src="https://img.shields.io/badge/GitHub_Actions-2024-2088FF" alt="GitHub Actions">
  <img src="https://img.shields.io/badge/Jaeger-1.60-60D" alt="Jaeger 1.60">  
</p>

<p align="center">
  <b>Neuro-Symbolic Clinical Decision Support — every diagnostic pathway is verified against grounded medical taxonomies and policy engines before reaching a clinician.</b>
</p>

---

## Table of Contents

- [What Problem Does This Solve?](#-what-problem-does-this-solve)
- [Architecture](#-architecture)
- [Features](#-features)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [API Reference](#-api-reference)
- [Project Structure](#-project-structure)
- [Module Deep-Dive](#-module-deep-dive)
- [Testing](#-testing)
- [Docker & CI](#-docker--ci)
- [Roadmap](#-roadmap)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🎯 What Problem Does This Solve?

Medical LLMs hallucinate when given open-ended generative control. Even with post-generation validation, relying on neural weights to independently map complex, multi-step clinical pathways is inherently unsafe.

**Speculative Clinical GraphRAG** inverts the control loop using a **Type 2 Symbolic[Neuro] Architecture**. A deterministic Symbolic Planner decomposes each clinical case into bounded sub-goals. The LLM is invoked strictly as a subroutine to extract specific entities or propose constrained differentials, which are instantly validated against a grounded medical knowledge graph (Neo4j), vector embeddings (Qdrant), and policy engine (OPA) before proceeding.

> **Neuro-Symbolic Invariant**: The symbolic planner drives the state machine. The LLM is a *tool*, not the *orchestrator*. No diagnostic pathway advances without mathematical and rule-based verification.

---

## 🏗 Architecture

### Core Components

| Component | Technology | Role |
|-----------|-----------|------|
| **Symbolic Planner** | LangGraph StateGraph | Deterministic workflow with typed GraphState working memory |
| **LLM Backends** | MockLLM / Ollama / DeepSeek-R1 / vLLM | Interchangeable: bounded extract_symptoms() and assess_differential() |
| **Knowledge Graph** | Neo4j Community + Cypher | Definitive symbolic taxonomy; falls back to in-memory EDGES constant when unavailable |
| **Vector Store** | Qdrant | Hybrid RAG embedding storage for clinical ontology + episodic memory |
| **Safety Guardrails** | Open Policy Agent (OPA) | Rego policies for drug interactions and contraindications |
| **Working Memory** | Redis | Idempotency keys, event sourcing (CQRS), multi-tiered session state |
| **Observability** | OpenTelemetry + Jaeger | Distributed tracing, LLM-as-judge evaluation |

---

## ✨ Features

| Area | Feature | Status |
|------|---------|--------|
| **Pipeline** | Type 2 Symbolic[Neuro] linear workflow | ✅ |
| **Pipeline** | Hybrid RAG (vector + graph) retrieval context | ✅ |
| **Pipeline** | Correction loop: up to 3 automated iterations before escalation | ✅ |
| **LLM** | 4 backends: MockLLM (zero-dep), Ollama (CPU), DeepSeek-R1, vLLM (GPU) | ✅ |
| **LLM** | Bounded extract_symptoms() / assess_differential() on all backends | ✅ |
| **LLM** | SemanticRouter for automatic backend selection | ✅ |
| **Ontology** | 178 in-memory ontology triples covering 126 unique clinical concepts | ✅ |
| **Ontology** | Symbolic lookup_edges() — no LLM, no database | ✅ |
| **Safety** | Neo4j Cypher validation (falls back to in-memory) | ✅ |
| **Safety** | SymbolicVerifier: drug interactions + age contraindications | ✅ |
| **Safety** | OPA Rego policies (Aspirin+Warfarin, NSAID+Warfarin, Metformin+Renal) | ✅ |
| **Retrieval** | sentence-transformers (all-MiniLM-L6-v2, 384-d) | ✅ |
| **Retrieval** | Qdrant vector search + Neo4j graph traversal + fusion scoring | ✅ |
| **Storage** | Redis: idempotency (SETNX), event sourcing (streams), working memory | ✅ |
| **Storage** | Qdrant: clinical ontology + episodic memory collections | ✅ |
| **Orchestration** | SupervisorAgent with 4 default workers | ✅ |
| **Orchestration** | DAGCompiler with topological sort + step-through execution | ✅ |
| **Observability** | OpenTelemetry tracer (OTLP gRPC → Jaeger) | ✅ |
| **Observability** | LLM-as-judge evaluation scoring | ✅ |
| **API** | API key authentication (X-API-Key header) | ✅ |
| **API** | Rate limiting (sliding window, 100 req/min default) | ✅ |
| **API** | Request ID + process time headers | ✅ |
| **API** | `/health` probes Neo4j / Qdrant / OPA / Redis | ✅ |
| **API** | `/v1/speculate` — full Type 2 pipeline | ✅ |
| **API** | `/v1/reasoning_trace/{id}` — clinician-reviewable trace | ✅ |
| **Infra** | docker-compose with 5 default services (7 with optional profiles) | ✅ |
| **Infra** | vLLM GPU profile (profiles: ["gpu"]) | ✅ |
| **Infra** | Jaeger tracing profile (profiles: ["tracing"]) | ✅ |
| **Infra** | GitHub Actions CI with service containers | ✅ |
| **Tests** | 53 passing, 4 skipped (Docker-only), 0 failing | ✅ |

---

## 📦 Installation

### Prerequisites

- Python 3.10+
- Docker & Docker Compose (for Neo4j / Qdrant / OPA / Redis)
- (Optional) Ollama for local CPU LLM inference
- (Optional) NVIDIA CUDA 12.1+ for GPU inference via vLLM

### Quick Start (MockLLM — zero GPU, zero API key)

```bash
# 1. Clone
git clone https://github.com/aragit/speculative-clinical-graphrag.git
cd speculative-clinical-graphrag

# 2. Virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Dependencies
pip install -r requirements.txt

# 4. Start infrastructure services
docker compose up -d neo4j qdrant redis opa

# 5. Run tests
pytest tests/ -v

# 6. Launch API
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

### With Local LLM (Ollama, CPU)

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull a model
ollama pull gemma2:2b

# Launch API with Ollama backend
RUNTIME_LLM=ollama LLM_MODEL=gemma2:2b python -m uvicorn api.main:app --reload
```

### With Production GPU (vLLM)

```bash
# Install vLLM (requires CUDA)
pip install vllm

# Start vLLM server with DeepSeek-R1
python -m vllm.entrypoints.openai.api_server \
    --model deepseek-ai/deepseek-r1-distill-qwen-32b \
    --tensor-parallel-size 2

# Or use Docker GPU profile
docker compose --profile gpu up -d

# Launch API pointing to vLLM
RUNTIME_LLM=deepseek_r1 VLLM_URL=http://localhost:8000/v1 \
    python -m uvicorn api.main:app --reload
```

---

## ⚙ Configuration

All configuration is via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `RUNTIME_LLM` | `mock` | LLM backend: `mock`, `ollama`, `deepseek_r1` |
| `LLM_MODEL` | `gemma2:2b` | Ollama model name |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL |
| `VLLM_URL` | `http://localhost:8000/v1` | vLLM / OpenAI-compatible URL |
| `VLLM_MODEL` | `deepseek-ai/deepseek-r1-distill-qwen-32b` | vLLM model name |
| `NEO4J_URI` | `bolt://localhost:7687` | Neo4j Bolt URI |
| `NEO4J_USER` | `neo4j` | Neo4j username |
| `NEO4J_PASSWORD` | `speculative123` | Neo4j password |
| `QDRANT_HOST` | `http://localhost:6333` | Qdrant HTTP URL |
| `OPA_URL` | `http://localhost:8181/v1/data/clinical` | OPA data API URL |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection URL |
| `JAEGER_HOST` | `jaeger:6831` | Jaeger agent host |
| `API_KEY` | *(empty — disabled)* | If set, requires `X-API-Key` header on all non-health requests |

---

## 🔬 API Reference

### Interactive Docs

Once running: `http://localhost:8000/docs`

### Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/health` | ❌ No | Infrastructure liveness probe |
| `POST` | `/v1/speculate` | ✅ Optional | Full Type 2 pipeline |
| `GET` | `/v1/reasoning_trace/{trace_id}` | ✅ Optional | Retrieve reasoning trace |

### Example Request

```bash
curl -X POST http://localhost:8000/v1/speculate \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-key" \      # only if API_KEY is set
  -d '{"patient_note": "A 65-year-old man with dyspnea and orthopnea"}'
```

### Example Response (Valid)

```json
{
  "proposed_path": [
    {"head": "Dyspnea", "relation": "INDICATES", "tail": "Heart Failure"},
    {"head": "Orthopnea", "relation": "INDICATES", "tail": "Heart Failure"}
  ],
  "validation": {
    "is_valid": true,
    "valid_edges": [...],
    "violations": [],
    "total_checked": 2,
    "confidence_decay": 1.0
  },
  "iterations": 1,
  "final_output": "{...}",
  "status": "valid",
  "reasoning_trace": "65-year-old man → dyspnea + orthopnea → both INDICATES Heart Failure...",
  "retrieval_sources": [
    {"symptom": "Dyspnea", "mapped_conditions": 5},
    {"symptom": "Orthopnea", "mapped_conditions": 2}
  ],
  "audit_log": [...]
}
```

### Example Response (Escalated)

```json
{
  "proposed_path": [],
  "validation": {
    "is_valid": false,
    "violations": [{"reason": "Empty path: no diagnostic entities extracted"}],
    "total_checked": 0
  },
  "iterations": 1,
  "final_output": "Escalated to human review. ...",
  "status": "escalated",
  "audit_log": [...]
}
```

### Request Schema

```json
{
  "patient_note": "string (required, 1-10000 chars)",
  "patient_context": {
    "age": "integer (optional)",
    "gender": "string (optional)",
    "medications": ["string (optional)"]
  },
  "preferred_backend": "mock | ollama | deepseek_r1 (optional)"
}
```

### Middleware

| Middleware | Behavior |
|-----------|----------|
| `RequestIDMiddleware` | Adds `X-Request-ID` (UUID) and `X-Process-Time` headers to every response |
| `APIKeyMiddleware` | If `API_KEY` env var is set, requires `X-API-Key` header. Bypassed for `/health`, `/docs`, `/openapi.json`, `/redoc` |
| `RateLimitMiddleware` | Sliding window (default 100 requests / 60 seconds per IP). Bypassed for the same paths |

---

## 📁 Project Structure

```
speculative-clinical-graphrag/
├── api/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app, lifespan, routing, middleware registration
│   ├── schemas.py              # Pydantic request/response models
│   ├── dependencies.py         # Dependency injection (verifier, LLM, OPA clients)
│   └── middleware.py           # RequestIDMiddleware, APIKeyMiddleware, RateLimitMiddleware
├── core/
│   ├── __init__.py
│   ├── workflow.py             # SpeculativeGraphRAG — Type 2 LangGraph state machine (9 nodes)
│   ├── llm_backend.py          # LLMBackend ABC + MockLLM, Ollama, DeepSeekR1, VLLM, SemanticRouter
│   ├── verification_layer.py   # Neo4jVerifier, SymbolicVerifier, OPAClient, EDGES ontology
│   ├── retrieval.py            # HybridRetriever — sentence-transformers + Qdrant + Neo4j + fusion
│   ├── ontology_etl.py         # OntologyETL — RF2/ICD-10/RxNorm parsers, embed_and_index()
│   ├── supervisor.py           # SupervisorAgent — 4 default workers, capability routing
│   ├── dag_compiler.py         # DAGCompiler — topological sort, cycle check, execute_dag()
│   ├── state_machine.py        # CQRSStateManager — Redis event streams + file fallback
│   ├── memory.py               # MultiTieredMemory — working (Redis), episodic (Qdrant), semantic (Neo4j)
│   ├── idempotency.py          # IdempotencyManager — UUID5 keys + Redis SETNX dedup
│   ├── telemetry.py            # TelemetryManager — OpenTelemetry tracer, LLM-as-judge
│   ├── mcp_registry.py         # MCPRegistry — Model Context Protocol tool registry
│   └── reasoning_extractor.py  # surface_reasoning_for_clinician() — trace formatting
├── infra/
│   └── opa/
│       └── policies/
│           └── clinical.rego   # OPA Rego policies (drug interactions)
├── tests/
│   ├── __init__.py
│   ├── test_api.py             # FastAPI endpoint tests (4)
│   ├── test_workflow.py        # Type 2 pipeline tests (4)
│   ├── test_llm_backends.py    # All 4 LLM backends + router (5)
│   ├── test_verification.py    # Neo4j, SymbolicVerifier, OPA (6, 3 skip without Docker)
│   ├── test_retrieval.py       # HybridRetriever tests (4)
│   ├── test_ontology_etl.py    # OntologyETL tests (4)
│   ├── test_supervisor.py      # SupervisorAgent tests (3)
│   ├── test_dag_compiler.py    # DAGCompiler tests (5)
│   ├── test_state_machine.py   # CQRSStateManager tests (2)
│   ├── test_memory.py          # MultiTieredMemory tests (5)
│   ├── test_idempotency.py     # IdempotencyManager tests (3)
│   ├── test_telemetry.py       # TelemetryManager tests (2)
│   ├── test_middleware.py      # API middleware tests (6)
│   ├── test_hybrid_rag.py      # Integration-oriented hybrid RAG tests (2)
│   └── test_reasoning_extractor.py  # Trace formatting tests (3)
├── .github/
│   └── workflows/
│       └── ci.yml              # GitHub Actions — service containers + seed + test
├── docker-compose.yml          # 5 default services: Neo4j, Qdrant, Redis, OPA, FastAPI; +vLLM (gpu), +Jaeger (tracing)
├── requirements.txt            # Python dependencies
└── README.md
```

---

## 🧩 Module Deep-Dive

### `core/workflow.py` — Type 2 Pipeline

The LangGraph `StateGraph` has 9 nodes with a correction loop:

```
ingest → retrieve_context → extract_symptoms → map_to_ontology → assess_differential → verify_safety
                                                                                              |
                                                      ┌─────────────────────────────────────┤
                                                      ▼                                     ▼
                                              correct_differential                     [synthesize | escalate]
                                                      │
                                                      ▼
                                              assess_differential ←── (loop back)
```

`GraphState` typed working memory:
- `patient_note`, `patient_context` — input
- `retrieval_context` — hybrid RAG output fed into LLM prompt
- `extracted_symptoms` — LLM-extracted structured symptoms
- `ontology_mappings` — symbolic `lookup_all_by_symptoms()` (no LLM)
- `proposed_path` — LLM-proposed diagnostic triplets
- `safety_result` — 3-way verification outcome
- `validation_result`, `reasoning_trace`, `final_output`, `status`, `audit_log` — output

### `core/llm_backend.py` — LLM Abstraction

| Backend | Dependencies | Use Case |
|---------|-------------|----------|
| `MockLLMBackend` | None | Development / CI / testing |
| `OllamaBackend` | `httpx` | Local CPU inference (gemma2:2b, etc.) |
| `DeepSeekR1Backend` | `openai` | Production GPU via vLLM, extracts `<think>` reasoning |
| `VLLMBackend` | `openai` | Any OpenAI-compatible server |

All backends implement:
- `generate_path(note)` — legacy, for compatibility
- `extract_symptoms(note, ctx)` — returns `{"symptoms": [{"term": ..., "confidence": ...}]}`
- `assess_differential(symptoms, mappings, ctx)` — returns `{"triplets": [...], "reasoning": "..."}`

### `core/verification_layer.py` — Safety Stack

Three independent verification layers:

1. **Neo4jVerifier**: Cypher `MATCH` queries against Neo4j graph. Falls back to in-memory EDGES constant when Neo4j is unavailable.
2. **SymbolicVerifier**: Hardcoded drug interaction rules + age-based contraindications. No external dependencies.
3. **OPAClient**: HTTP calls to OPA sidecar evaluating `clinical.rego` policies. Defaults to `allow=True` when OPA is unreachable.

### `core/retrieval.py` — Hybrid RAG

Two retrieval paths fused together:

- **Vector search**: `sentence-transformers(all-MiniLM-L6-v2)` → Qdrant `clinical_ontology` collection
- **Graph search**: In-memory `EDGES` lookup first, falls back to Neo4j fulltext CONTAINS query
- **Fusion score**: `α * vector_score + (1-α) * graph_score` (default α=0.7)

### `core/supervisor.py` — Worker Delegation

Routes tasks by capability string to 4 built-in workers:
- `extract_symptoms` → `llm.extract_symptoms()`
- `map_to_ontology` → `lookup_all_by_symptoms()`
- `assess_differential` → `llm.assess_differential()`
- `verify_safety` → `symbolic.validate()`

### `core/dag_compiler.py` — DAG Execution

- `compile_plan(llm_plan)` — parses `{steps: [{id, action, parameters, depends_on}]}` into `{nodes, edges, topological_order}`
- `validate_dag(dag)` — Kahn's algorithm cycle detection
- `execute_dag(dag, context, node_executor)` — walks topological order, calls optional executor callback per node, stores results in context

### `core/state_machine.py` — CQRS Event Sourcing

- `commit_event(trace_id, event)` — pushes to Redis stream `events:{trace_id}` via `XADD`, expires after 24h. Falls back to `events.db` file append
- `get_state(trace_id)` — replays events from Redis via `XRANGE`, falls back to file scan

### `core/memory.py` — Multi-Tiered Memory

| Tier | Backend | Namespace | Methods |
|------|---------|-----------|---------|
| Working | Redis | `wm:{session}:{key}` | `working_get`, `working_set` |
| Episodic | Qdrant | `episodic_memory` collection | `episodic_search`, `episodic_store` |
| Semantic | Neo4j | — | `semantic_query(cypher)` |

### `core/idempotency.py` — Deduplication

- `generate_key(trace_id, tool_name, payload)` — UUID5 over canonical JSON
- `check_and_store(key, ttl)` — Redis `SETNX` + `EXPIRE`. Returns `True` (first call — proceed) or `False` (duplicate — skip). Falls back to `True` when Redis is unreachable.

### `core/telemetry.py` — Observability

- `get_tracer(name)` — OpenTelemetry `TracerProvider` with OTLP gRPC exporter to Jaeger. Falls back to `logging.Logger` when OTel packages are unavailable.
- `llm_as_judge(execution_graph, llm_backend)` — sends final_output to LLM with structured scoring prompt, parses `{factual_accuracy, tone, logic}` JSON response.

---

## 🧪 Testing

### Quick Run (no Docker)

```bash
pytest tests/ -v
# 53 passed, 4 skipped (Docker-only), 0 failed
```

### Full Run (with Docker)

```bash
docker compose up -d neo4j qdrant redis opa
pytest tests/ -v
# 56 passed, 1 skipped (Ollama), 0 failed
```

### Test Coverage

| File | Tests | What it covers |
|------|-------|----------------|
| `test_api.py` | 4 | Health probes, speculate endpoint, escalation, reasoning trace |
| `test_workflow.py` | 4 | Valid path, invalid→escalate, nonsensical input, reasoning trace |
| `test_llm_backends.py` | 6 | All 4 backends, semantic router, think tag parsing (1 skip: Ollama) |
| `test_verification.py` | 4 | Neo4j valid/invalid (2 skip), SymbolicVerifier, OPA (1 skip) |
| `test_retrieval.py` | 4 | HybridRetriever structure, in-memory graph, fusion scores |
| `test_ontology_etl.py` | 4 | All 4 parser not-found paths |
| `test_supervisor.py` | 3 | Delegation, unknown task, safety verification |
| `test_dag_compiler.py` | 5 | Compile, validate, execute, executor callback |
| `test_state_machine.py` | 2 | Commit + get state with Redis fallback |
| `test_memory.py` | 5 | All 3 tiers with fallbacks |
| `test_idempotency.py` | 3 | Key generation, determinism, Redis fallback |
| `test_telemetry.py` | 2 | Tracer fallback, LLM-as-judge stub |
| `test_middleware.py` | 6 | API key, rate limit, request ID |
| `test_hybrid_rag.py` | 2 | Vector search structure, graph traversal |
| `test_reasoning_extractor.py` | 3 | Trace extraction, coherence, clinician formatting |

---

## 🐳 Docker & CI

### docker-compose.yml

| Service | Image | Ports | Healthcheck | Profile |
|---------|-------|-------|-------------|---------|
| `neo4j` | `neo4j:5-community` | 7687, 7474 | Cypher `RETURN 1` | default |
| `qdrant` | `qdrant/qdrant` | 6333 | `/health` | default |
| `redis` | `redis:7-alpine` | 6379 | `PING` | default |
| `opa` | `openpolicyagent/opa` | 8181 | `/health` | default |
| `fastapi` | (builds from Dockerfile) | 8000 | `/health` | default |
| `vllm` | `vllm/vllm-openai` | 8000 | `/health` | `gpu` |
| `jaeger` | `jaegertracing/all-in-one` | 4317, 16686 | — | `tracing` |

### GitHub Actions (`.github/workflows/ci.yml`)

- Service containers: Neo4j, Qdrant, Redis. OPA started via `docker run` after checkout with policy volume mount.
- Steps: checkout → pip install → seed ontology → run tests → post-results
- Healthcheck options for all service containers

---

## 🛣 Roadmap

| Phase | Deliverable | Status |
|-------|-------------|--------|
| **Phase 1** | Knowledge Foundation — in-memory EDGES ontology, Neo4j schema | ✅ Complete |
| **Phase 2** | Type 2 Pipeline — LangGraph state machine with 9 nodes + correction loop | ✅ Complete |
| **Phase 3** | Safety Stack — Neo4j + SymbolicVerifier + OPA | ✅ Complete |
| **Phase 4** | Hybrid RAG — Qdrant vector search + Neo4j graph | ✅ Complete |
| **Phase 5** | Production API — auth, rate limiting, SSE streaming | ⬜ In progress |
| **Phase 6** | Multi-Hospital Federation — federated taxonomy sync | 🔬 Research |
| **Phase 7** | Type 6 (Neuro[Symbolic]) — end-to-end differentiable neuro-symbolic | 🔬 Research |

---

## 🔒 Safety & Compliance

- **Zero PHI persistence**: All processing is ephemeral; no patient data is stored
- **Deterministic escalation**: Unvalidated paths always route to human review — never to patient-facing output
- **Audit trail**: Every speculation, validation, and correction is logged with full reasoning trace
- **Model-agnostic safety**: Verification logic is independent of the LLM backend; swapping models does not bypass guardrails
- **3-layer verification**: Neo4j ontology + symbolic rules + OPA policies — any single layer can block a path

---

## 🤝 Contributing

This is an active research blueprint. Contributions welcome in:

- Additional medical ontologies (LOINC, ATC, MedDRA)
- Structured output formats (FHIR R4, JSON-LD, RDF)
- Evaluation benchmarks (MedQA, PubMedQA, custom clinical datasets)
- Edge deployment (NVIDIA Jetson, Apple Silicon)
- Multi-LLM routing and fallback strategies

---

## 📄 License

MIT License — Clinical AI Research & Engineering

---

<p align="center">
  <sub>Built with LangGraph, Neo4j, Qdrant, OPA, FastAPI, vLLM, and a deep respect for clinical safety.</sub>
</p>
