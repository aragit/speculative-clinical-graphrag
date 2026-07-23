<h1 align="center">Speculative Clinical GraphRAG</h1>
<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-blue" alt="Python 3.12">
  <img src="https://img.shields.io/badge/Architecture-Type_2_Symbolic[Neuro]-purple" alt="Type 2 Symbolic Neuro">
  <img src="https://img.shields.io/badge/Tests-125_Passed_|_0_Failed-success" alt="Tests 125 Passed">
  <img src="https://img.shields.io/badge/FastAPI-0.110-009688" alt="FastAPI 0.110">
  <img src="https://img.shields.io/badge/LangGraph-State_Engine-1C3C3C" alt="LangGraph Engine">
  <img src="https://img.shields.io/badge/Neo4j-5-008CC1" alt="Neo4j 5">
  <img src="https://img.shields.io/badge/Qdrant-1.7-EB5245" alt="Qdrant 1.7">
  <img src="https://img.shields.io/badge/Redis-Streams-DC382D" alt="Redis Streams">
  <img src="https://img.shields.io/badge/OPA-Zero_Trust_Rego-7A5CF7" alt="OPA Policy">
  <img src="https://img.shields.io/badge/vLLM-MedGemma_4B-00A86B" alt="vLLM MedGemma">
</p>

<p align="center">
  <b>A Graph-Driven Reasoning Engine with LLM as Interface — Every diagnostic path is deterministically planned, symbolically constrained, and policy-verified before natural language synthesis.</b>
</p>

---

## Table of Contents

- [The Paradigm Shift: Graph-Driven Reasoning](#-the-paradigm-shift-graph-driven-reasoning)
- [System Execution Flow](#-system-execution-flow)
- [Target 6-Layer Architecture](#-target-6-layer-architecture)
- [Features](#-features)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [API Reference](#-api-reference)
- [Project Directory Structure](#-project-directory-structure)
- [Module & Layer Deep-Dive](#-module--layer-deep-dive)
- [Deterministic LangGraph vs. Probabilistic Routing](#-deterministic-langgraph-vs-probabilistic-routing)
- [Testing & Verification](#-testing--verification)
- [Docker & CI/CD](#-docker--cicd)
- [License](#-license)

---

## 🎯 The Paradigm Shift: Graph-Driven Reasoning

Standard "GraphRAG" and agentic frameworks (LangChain, basic LangGraph) suffer from a **Cognitive Control Gap**: they use Knowledge Graphs as passive context dumps while leaving clinical deduction, differential diagnosis, and routing inside the LLM's probabilistic latent space. In a clinical setting, open-ended LLM routing leads to non-deterministic failure loops and hallucinations.

**Speculative Clinical GraphRAG** introduces a fundamental architectural shift into a **Type 2 Symbolic[Neuro] Clinical Decision Support System**:

1. **Explicit Knowledge Control**: Clinical reasoning is moved out of the LLM prompt and into deterministic Python code, Cypher traversals, and symbolic rules.
2. **LLM as Interface (Demoted Subroutine)**: The fine-tuned LLM (`MedGemma-4B-IT` / `vLLM`) is demoted from "The Brain" to a bounded Layer 4 subroutine responsible only for structured extraction and natural language synthesis.
3. **Zero-Trust Governance**: No diagnostic hypothesis or treatment pathway reaches a clinician without passing structural Cypher proof validation and external Open Policy Agent (OPA) safety checks.

```
              STANDARD AGENTIC RAG (Probabilistic Latent Reasoning)
User Query ──► LLM Router (Latent Space) ──► Tool / Graph Dump ──► LLM Output (Unconstrained)

              SPECULATIVE CLINICAL GRAPHRAG (Graph-Driven Neuro-Symbolic)
User Query ──► Intent Planner ──► Guided Graph Traversal ──► Symbolic Rules & Constraints
                                                                │
Clinician ◄── Verification Gate ◄── LLM Synthesis (Translator) ◄─────────┘
```

---

## 🔄 System Execution Flow

Every request executes across a strictly enforced 6-step deterministic pipeline:

```
User ──► Intent/Planner ──► Guided Graph Traversal ──► Constraint Reasoning ──► LLM Synthesis ──► Verification ──► Answer + Trace
```

1. **Intent Planning**: Query is parsed into a bounded DAG execution plan with sub-goals and required ontology domains.
2. **Guided Traversal**: Cypher queries actively walk symptom-condition-drug graphs (`symptom → related conditions → risk factors → contraindications`).
3. **Symbolic Elimination**: Hardcoded rules and Bayesian constraint engines eliminate clinical impossibilities and rank paths based on grounded evidence strength.
4. **Bounded LLM Synthesis**: The LLM translates the verified subgraphs and reasoning paths into structured clinical briefings.
5. **Deterministic Verification**: OPA Rego sidecar policies (<5ms) and sub-50ms native Python fallbacks evaluate final safety invariants (e.g., drug interaction, dosing safety).
6. **Delivery & Audit Ledger**: Output is emitted along with an immutable, step-by-step symbolic proof trace.

---

## 🏗 Target 6-Layer Architecture

The codebase decouples execution into six single-responsibility layers:

```
+-----------------------------------------------------------------------------------+
| 1. COGNITIVE ORCHESTRATION LAYER (core/orchestrator.py & agents/planner/)         |
|    - Decomposes clinical query into bounded sub-goals                             |
|    - Emits structured execution plan (Intent, Required Nodes, Policy Domain)      |
+---------------------------------------------+-------------------------------------+
                                              |
                                              v
+-----------------------------------------------------------------------------------+
| 2. ACTIVE KNOWLEDGE TRAVERSAL LAYER (agents/retriever/ & knowledge/graph/)        |
|    - Plan-guided Cypher graph traversal (Symptoms -> Conditions -> Contraindications) |
|    - Qdrant hybrid vector extraction for unstructured EHR context                  |
+---------------------------------------------+-------------------------------------+
                                              |
                                              v
+-----------------------------------------------------------------------------------+
| 3. SYMBOLIC CONSTRAINT & REASONING LAYER (agents/reasoner/)                      |
|    - Deterministic elimination of clinical impossibilities (rules_engine.py)       |
|    - Conflict identification (drug-symptom, allergy-condition)                     |
|    - Bayesian posterior confidence updates & path elimination                     |
+---------------------------------------------+-------------------------------------+
                                              |
                                              v
+-----------------------------------------------------------------------------------+
| 4. NEURAL EXPRESSION & SYNTHESIS LAYER (agents/synthesizer/)                       |
|    - Invokes local fine-tuned LLM (MedGemma-4B-IT / vLLM) strictly as a subroutine |
|    - Converts validated symbolic reasoning paths into clear clinical briefings    |
+---------------------------------------------+-------------------------------------+
                                              |
                                              v
+-----------------------------------------------------------------------------------+
| 5. DETERMINISTIC GOVERNANCE LAYER (agents/verifier/ & governance/opa/)            |
|    - OPA/Rego sidecar zero-trust policy verification (<5ms)                       |
|    - Native Python fallback validator (<50ms under OPA timeout)                   |
|    - Structural Cypher proof validation before final response delivery             |
+---------------------------------------------+-------------------------------------+
                                              |
                                              v
+-----------------------------------------------------------------------------------+
| 6. MEMORY SUBSTRATE & AUDIT LEDGER (core/state.py & storage/)                     |
|    - Redis Streams for state checkpointing (<15ms hydration)                      |
|    - Append-only event log for 100% deterministic replayability                  |
+-----------------------------------------------------------------------------------+
```

---

## ✨ Features

| Area | Feature | Status |
|------|---------|--------|
| **Architecture** | Type 2 Symbolic[Neuro] Graph-Driven Reasoning Pipeline | ✅ |
| **Pipeline** | Verify-then-generate pattern with topological cycle detection | ✅ |
| **Pipeline** | Correction loop: Automated feedback iterations before human escalation | ✅ |
| **LLM Engine** | Bounded local inference via MedGemma-4B-IT, vLLM, DeepSeek-R1, or MockLLM | ✅ |
| **LLM Engine** | Bounded JSON subroutines (`extract_symptoms`, `assess_differential`) | ✅ |
| **Ontology** | 178+ in-memory ontology triples covering SNOMED-CT, ICD-10, RxNorm | ✅ |
| **Governance** | OPA/Rego sidecar policy engine + sub-50ms native Python fallback validator | ✅ |
| **Governance** | Fail-secure OPA policy blocks for contraindications (Aspirin/Warfarin, etc.) | ✅ |
| **Retrieval** | Hybrid Qdrant vector search + active Cypher graph traversal + RRF fusion | ✅ |
| **Storage** | Multi-Tiered Memory: Working (Redis), Episodic (Qdrant), Semantic (Neo4j) | ✅ |
| **Storage** | CQRS event sourcing with Redis Streams (<15ms hydration) | ✅ |
| **Orchestration** | SupervisorAgent with capability routing & DAGCompiler (topological sort) | ✅ |
| **Observability** | OpenTelemetry gRPC tracing to Jaeger + LLM-as-Judge evaluation | ✅ |
| **API** | FastAPI 0.110 with API key auth, sliding-window rate limit, `/health` probes | ✅ |
| **Tests** | **125 passing, 4 skipped (Docker-only), 0 failing** (~10s runtime) | ✅ |

---

## 📦 Installation

### Quick Start (MockLLM — Zero GPU, Zero External Dependencies)

```bash
# 1. Clone
git clone https://github.com/aragit/speculative-clinical-graphrag.git
cd speculative-clinical-graphrag

# 2. Setup Virtual Environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install Dependencies
pip install -r requirements.txt

# 4. Spin up Infrastructure (Neo4j, Qdrant, Redis, OPA)
docker compose up -d neo4j qdrant redis opa

# 5. Run Verification Test Suite
python -m pytest tests/ -vv

# 6. Launch API Server
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 📁 Project Directory Structure

```
speculative-clinical-graphrag/
│
├── api/                            # Application Layer
│   ├── main.py                     # FastAPI application entrypoint & lifespan hooks
│   ├── schemas.py                  # Pydantic request/response models
│   ├── dependencies.py             # Dependency injection (verifier, LLM, OPA)
│   └── middleware.py               # Request ID, API Key, Rate Limiter
│
├── core/                           # Core Orchestration Engine
│   ├── orchestrator.py             # StateGraph execution & deterministic loops
│   ├── workflow.py                 # SpeculativeGraphRAG 9-node state machine
│   ├── dag_compiler.py             # Topological sorting & cycle-detection execution
│   ├── llm_backend.py              # LLM Backend implementations (MedGemma, vLLM, Mock)
│   ├── retrieval.py                # Hybrid RAG retriever (Vector + Cypher + Fusion)
│   ├── verification_layer.py       # Neo4j, SymbolicVerifier, and OPA policy integration
│   ├── memory.py                   # Multi-Tiered Memory (Working, Episodic, Semantic)
│   ├── idempotency.py              # UUID5 key generation & Redis SETNX deduplication
│   └── telemetry.py                # OpenTelemetry tracing & LLM-as-judge scoring
│
├── agents/                         # Bounded Single-Responsibility Subroutines
│   └── reasoner/
│       └── graph_reasoner.py       # Speculative path generation & LangGraph interface
│
├── infra/
│   └── opa/
│       └── policies/
│           └── clinical.rego       # OPA Rego policies (drug interactions)
│
├── graph/
│   └── schema.cypher               # Neo4j ontology schema definitions
│
├── tests/                          # Enterprise Verification Suite
│   ├── test_api.py                 # Endpoint integration tests
│   ├── test_dag_compiler.py        # Cycle detection & topological sorting tests
│   ├── test_idempotency.py         # Deterministic key generation tests
│   ├── test_memory.py              # Working memory tier tests
│   ├── test_reasoning_extractor.py # Clinician truncation & trace formatting tests
│   ├── test_verification.py        # Symbolic rules & OPA policy tests
│   ├── test_verify_all.py          # Master 125-test verification suite
│   └── test_workflow.py            # End-to-end state graph execution tests
│
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── README.md
```

---

## 🧩 Module & Layer Deep-Dive

### `core/orchestrator.py` — Neuro-Symbolic State Machine

The `ClinicalOrchestrator` wraps a LangGraph `StateGraph` with five deterministic nodes:
1. `retrieve` — Fetches graph context via in-memory EDGES lookup + Neo4j fallback
2. `speculative_reasoning` — Invokes `GraphReasonerAgent` to propose candidate clinical paths
3. `symbolic_verification` — Validates paths against `SymbolicVerifier` drug interaction rules + age contraindications
4. `synthesize` — Generates clinician-facing response using verified paths
5. `escalate` — Flags state for human-in-the-loop review on validation failure

### `core/workflow.py` — Type 2 Pipeline (9 Nodes)

The `SpeculativeGraphRAG` LangGraph `StateGraph` executes: **ingest → retrieve_context → extract_symptoms → map_to_ontology → assess_differential → verify_safety → [correct_differential ↔ assess_differential] → synthesize | escalate**

### `agents/reasoner/graph_reasoner.py` — Speculative Path Generator

`GraphReasonerAgent` constructs candidate diagnostic or multi-drug interaction paths using the LLM backend prior to symbolic graph validation. Exposes `SpeculativePath` Pydantic model with `path_id`, `nodes`, `relations`, `rationale`, and `confidence_score`.

### `core/llm_backend.py` — LLM Abstraction Layer

| Backend | Use Case |
|---------|----------|
| `MockLLMBackend` | Development / CI / zero-dependency testing |
| `OllamaBackend` | Local CPU inference |
| `DeepSeekR1Backend` | Production GPU via vLLM |
| `MedGemmaBackend` | Medical fine-tuned model via vLLM |

### `core/verification_layer.py` — Safety Stack

Three independent verification layers:
1. **Neo4jVerifier**: Cypher `MATCH` queries (falls back to in-memory EDGES when unreachable)
2. **SymbolicVerifier**: Hardcoded drug interaction rules + age-based contraindications
3. **OPAClient**: HTTP calls to OPA sidecar evaluating `clinical.rego` policies

---

## 🧠 Deterministic LangGraph vs. Probabilistic Routing

**Standard Agentic Usage (Probabilistic):** LangGraph uses LLMs on conditional edges (`if llm_router() == 'tool': ...`). The execution path is trapped in the LLM's latent space, leaving it vulnerable to prompt injection, logic loops, and hallucinations.

**Our Neuro-Symbolic Usage (Deterministic Chassis):** LangGraph is used strictly as a State Machine and State Checkpointer. Edge transitions and node executions are determined by `core/dag_compiler.py`, topological sorting, Python rule engines, and OPA policy gates. The LLM is confined inside a single node (Layer 4 Synthesis) and has zero authority to alter execution flow.

---

## 🧪 Testing & Verification

The suite features complete unit, integration, and property-based verification tests:

```bash
python -m pytest tests/ -vv
```

**Verification Suite Results:**
```
================ 125 passed, 4 skipped, 17 warnings in 10.86s ================
```

| Test Area | What It Verifies |
|-----------|-----------------|
| Reasoning Extraction | Strict truncation math ensuring clinician traces never break length contracts |
| DAG Compiler | Kahn's algorithm topological sorting & explicit cycle rejection |
| Memory Tiers | Redis working memory fallback & session hydration |
| Governance | Fail-secure policy evaluations with native Python sub-50ms fallback |
| Idempotency | Deterministic payload UUID5 key generation |
| Workflow | End-to-end 9-node state graph execution with correction loops |

---

## 🐳 Docker & CI/CD

### docker-compose.yml

| Service | Image | Ports | Profile |
|---------|-------|-------|---------|
| `neo4j` | `neo4j:5.15-community` | 7687, 7474 | default |
| `qdrant` | `qdrant/qdrant` | 6333 | default |
| `redis` | `redis:7-alpine` | 6379 | default |
| `opa` | `openpolicyagent/opa` | 8181 | default |
| `fastapi` | (builds from Dockerfile) | 8000 | default |
| `vllm` | `vllm/vllm-openai` | 8000 | `gpu` |
| `jaeger` | `jaegertracing/all-in-one` | 16686 | `tracing` |

### GitHub Actions

Service containers: Neo4j, Qdrant, Redis. OPA started via `docker run` after checkout with policy volume mount.

---

## 📄 License

MIT License — Clinical AI Research & Engineering
