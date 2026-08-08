<h1 align="center">Speculative Clinical GraphRAG</h1>

<p align="left">
  <b>A Neuro-Symbolic Clinical Decision Support System — Type 2→6 architecture
  where every diagnostic path is symbolically constrained, graph-proven, and
  OPA-policy verified before natural language synthesis.</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-blue?style=flat-square&logo=python" alt="Python 3.12">
  <img src="https://img.shields.io/badge/Architecture-Type_2_to_Type_6_Neuro--Symbolic-purple?style=flat-square" alt="Type 2 to Type 6 Neuro-Symbolic">
  <img src="https://img.shields.io/badge/MCP-Protocol_v2024--11--05-00522CC?style=flat-square" alt="MCP Protocol">
  <img src="https://img.shields.io/badge/Status-v0.6.3_r5--secure-orange?style=flat-square" alt="v0.6.3-r5-secure">
  <img src="https://img.shields.io/badge/Tests-223%20Passed%20%7C%200%20Failed-brightgreen?style=flat-square" alt="Tests 223 Passed">
  <img src="https://img.shields.io/badge/FastAPI-0.110-009688?style=flat-square&logo=fastapi" alt="FastAPI 0.110">
  <img src="https://img.shields.io/badge/LangGraph-State_Engine-1C3C3C?style=flat-square" alt="LangGraph Engine">
  <img src="https://img.shields.io/badge/Neo4j-5.15-008CC1?style=flat-square&logo=neo4j" alt="Neo4j 5">
  <img src="https://img.shields.io/badge/Qdrant-1.7-EB5245?style=flat-square&logo=qdrant" alt="Qdrant 1.7">
  <img src="https://img.shields.io/badge/OPA-Zero_Trust_Rego-7A5CF7?style=flat-square&logo=openpolicyagent" alt="OPA Policy">
</p>

---

## Architecture

```mermaid
flowchart TB
    subgraph Client
        C[Clinician / EHR System]
    end

    subgraph API["FastAPI Gateway"]
        M[Security Middleware<br/>PII Redaction / Injection Filter]
        R[Rate Limit / Circuit Breakers / Security Headers]
    end

    subgraph Workflow["LangGraph Workflow (Type 6)"]
        direction TB
        FP[fhir_parse<br/>FHIR R4 Parser]
        IN[ingest<br/>Regex Fallback]
        RC[retrieve_context<br/>Hybrid RAG]
        ES[extract_symptoms<br/>LLM Extraction]
        MO[map_to_ontology<br/>Graph Mapping]
        AD[assess_differential<br/>COGITATOR Neural Core]
        VS[verify_safety<br/>Multi-Layer Verification]
        CD[correct_differential<br/>Feedback Loop]
        SY[synthesize<br/>Output Formatting]
        ES2[escalate<br/>Human-in-the-Loop]

        FP --> IN --> RC --> ES --> MO --> AD --> VS
        VS -->|valid| SY
        VS -->|correct| CD --> AD
        VS -->|escalate| ES2
        CD -->|max iterations| ES2
    end

    subgraph Verification["Verification Layers"]
        N4[Neo4j Taxonomy<br/>full / degraded / symbolic_only]
        SV[SymbolicVerifier<br/>YAML Rules: drug / allergy / pregnancy / age]
        OP[OPA Policy Engine<br/>Rego: fail-closed]
        NV[NeuralVerifier<br/>MockNeuralVerifier (disabled by default)]
        CF[ConfidenceFusion<br/>Weighted Aggregation]
    end

    subgraph Learning["Self-Improvement (EVOLUTIO)"]
        OA[OverrideAnalytics<br/>Pattern Mining]
        RL[RLHFTrainer<br/>Logistic Regression]
        HR[Hot Reload<br/>SymbolicVerifier.update()]
    end

    subgraph MCP["MCP Control Plane"]
        TR[ToolRegistry<br/>query_ehr / order_lab / check_drug / retrieve_lit]
        MP[MCPProtocolServer<br/>JSON-RPC 2.0]
    end

    C --> M --> R
    R --> Workflow
    AD -.->|critique loop| AD
    VS --> Verification
    Verification --> CF
    CF -->|decision| VS
    ES2 --> OA
    OA -->|proposed rules| RL
    RL -->|approved rules| HR
    Workflow -->|agent requests| MCP
```

## Architecture Evolution

| Phase | Version | Status | Description |
|-------|---------|--------|-------------|
| R0 | v0.1.0 | ✅ | Mock ontology, basic LangGraph workflow |
| R1 | v0.2.0 | ✅ | Neo4j integration, multi-layer verification |
| R2 | v0.3.0 | ✅ | FHIR parser, external YAML rules, convergence detection, property tests |
| R3 | v0.5.0 | ✅ | NeuralVerifier ABC, AgentRegistry, ConfidenceFusion, DAGModifier, OverrideAnalytics |
| **Type 6** | **v0.6.0** | **✅** | **COGITATOR self-critique, NeuralPolicy routing, EVOLUTIO learning** |
| R4.1 | v0.6.1 | ✅ | RLHF training pipeline, admin endpoints |
| R4.2 | v0.6.2 | ✅ | MCP Protocol (JSON-RPC 2.0), clinical tool registry |
| **R5** | **v0.6.3** | **✅** | **Security hardening, PII redaction, load testing** |
| R6 | v0.7.0 | ⏳ | Glass Box UI, MCP tool_enrichment in workflow |
| Production | v1.0.0 | ⏳ | FDA alignment, real SNOMED-CT, horizontal scale |

## 🔒 Type 2 Safety Invariants (Non-Negotiable)

These invariants are **hardcoded** and cannot be overridden by neural components:

| Invariant | Enforcement | Location |
|-----------|-------------|----------|
| **Symbolic rules dominate by default** | `enable_neural=false`, `enable_neural_policy=false` defaults | `core/workflow.py` |
| **Max iterations → escalate** | `iteration_count >= max_iterations` routes to `escalate` | `core/neural_policy.py` `_static_predict()` |
| **Symbolic unsafe + high risk → escalate** | Neural policy override regardless of heuristic score | `core/neural_policy.py` `predict()` |
| **OPA fail-closed** | Unreachable OPA returns `allow=False` | `core/verification_layer.py` |
| **Immutable nodes protected** | `ingest`, `verify_safety`, `escalate`, `fhir_parse` cannot be removed | `core/dag_modifier.py` |
| **Human approval for self-modification** | All `OverrideAnalytics` rules have `status: pending_approval` | `core/evolutio.py` |
| **PII redaction** | SSN, phone, email, DOB, MRN redacted before LLM processing | `core/security.py` |
| **Prompt injection blocking** | Pattern-based detection blocks suspicious inputs with 400 | `core/security.py` |

---

## Table of Contents

- [Architecture](#architecture)
- [Architecture Evolution](#architecture-evolution)
- [Safety Invariants](#-type-2-safety-invariants-non-negotiable)
- [The Paradigm Shift: Graph-Driven Reasoning](#-the-paradigm-shift-graph-driven-reasoning)
- [MAS Glass Box Cockpit (Frontend UI)](#-mas-glass-box-cockpit-frontend-ui)
- [System Execution Flow](#-system-execution-flow)
- [Target 6-Layer Architecture](#-target-6-layer-architecture)
- [MCP & Hub-and-Spoke Topology](#%EF%B8%8F-model-context-protocol-mcp--hub-and-spoke-topology)
- [Features](#-features)
- [API Endpoints](#-api-endpoints)
- [Security Hardening](#-security-hardening-v063)
- [Quick Start & E2E Demo Mode](#-quick-start--e2e-demo-mode)
- [Project Directory Structure](#-project-directory-structure)
- [LLM Backends](#-llm-backends--bounded-subroutines-layer-4-isolation)
- [Testing & Verification](#-testing--verification)
- [Docker & CI/CD](#-docker--cicd)
- [License](#-license)

---

## 🎯 The Paradigm Shift: Graph-Driven Reasoning

Standard "GraphRAG" and agentic frameworks suffer from a **Cognitive Control Gap**: they use Knowledge Graphs as passive context dumps while leaving clinical deduction, differential diagnosis, and routing inside the LLM's probabilistic latent space. In a clinical setting, open-ended LLM routing leads to non-deterministic failure loops and hallucinations.

**Speculative Clinical GraphRAG** introduces a fundamental architectural shift into a **Type 2 Symbolic[Neuro] Clinical Decision Support System**:

1. **Explicit Knowledge Control**: Clinical reasoning is moved out of the LLM prompt and into deterministic Python code, Cypher graph traversals, and symbolic rule engines.
2. **LLM as Interface (Demoted Subroutine)**: The fine-tuned LLM (`MedGemma-4B-IT` / `vLLM`) is demoted from "The Brain" to a bounded Layer 4 subroutine responsible only for structured extraction and natural language synthesis.
3. **Zero-Trust Governance**: No diagnostic hypothesis or treatment pathway reaches a clinician without passing structural Cypher proof validation and external Open Policy Agent (OPA) safety checks.

<p align="center">
  <img src="assets/graphRAG.png" alt="Clinical GraphRAG Flow Diagram" width="50%">
</p>

---

## 🖥️ MAS Glass Box Cockpit (Frontend UI)

The **Multi-Agent System (MAS) Glass Box Cockpit** provides real-time observability into the inner workings of the neuro-symbolic engine. Built with React 18, Vite, Tailwind CSS, and React Flow, it visualizes state transitions, agent handoffs, and policy verification in real time.

<p align="center">
  <img src="assets/UI_V3.png" alt="MAS Glass Box Cockpit Interface" width="100%">
</p>

### Interactive Visual Control Zones

| Zone | Component | Description |
| :--- | :--- | :--- |
| **Zone 1** | **Orchestration Canvas** | Renders the live **Hub-and-Spoke MCP Topology**. Displays the `Central MCP Orchestrator` delegating work to 4 specialized `MCP Skill` nodes with real-time status badges (`COMPLETED`, `RUNNING`, `FAILED`). |
| **Zone 2** | **ReAct Reasoning Trace** | Streams granular execution events tagged with semantic indicators: 🧠 *Thought*, ⚡ *Action*, 👁️ *Observation*, and 🛡️ *Policy Safety Verification*. |
| **Zone 3** | **Global Memory State** | Live state inspector displaying active patient demographics, extracted symptoms, ontology mapping counts, and execution status mutations (`valid`, `escalated`). |
| **Zone 4** | **Validated Clinical Pathway** | Formatted diagnostic card displaying validated clinical pathways (`Dyspnea ➔ INDICATES ➔ Heart Failure (92%)`), patient context, and collapsible reasoning proofs. |

---

## 🔄 System Execution Flow

Every clinical request executes across a strictly enforced 6-step deterministic pipeline:

```
User Note ──► Intent Planner ──► Guided Graph Traversal ──► Symbolic Rules & Elimination
    ──► Bounded LLM Synthesis ──► OPA Policy Gate ──► Verified Briefing + Trace
```

1. **Intent Planning**: Query is parsed into a bounded DAG execution plan with sub-goals and required ontology domains.
2. **Guided Traversal**: Cypher queries actively walk symptom-condition-drug graphs (`symptom → related conditions → risk factors → contraindications`).
3. **Symbolic Elimination**: Hardcoded rules and Bayesian constraint engines eliminate clinical impossibilities and rank paths based on grounded evidence strength.
4. **Bounded LLM Synthesis**: The LLM translates verified subgraphs and reasoning paths into structured clinical briefings.
5. **Deterministic Verification**: OPA Rego sidecar policies (<5ms) and sub-50ms native Python fallbacks evaluate safety invariants (e.g., drug interactions, dosing safety).
6. **Delivery & Audit Ledger**: Output is emitted along with an immutable, step-by-step symbolic proof trace.

---

## 🏗 Target 6-Layer Architecture

The codebase decouples execution into six single-responsibility layers:

```
+-----------------------------------------------------------------------------------+
| 1. COGNITIVE ORCHESTRATION LAYER (core/orchestrator.py & core/supervisor.py)      |
|    - Decomposes clinical query into bounded sub-goals                             |
|    - Emits structured execution plan (Intent, Required Nodes, Policy Domain)      |
+---------------------------------------------+-------------------------------------+
                                             v
+-----------------------------------------------------------------------------------+
| 2. ACTIVE KNOWLEDGE TRAVERSAL LAYER (core/retrieval.py & graph/)                      |
|    - Plan-guided Cypher graph traversal (Symptoms -> Conditions -> Contraindications) |
|    - Qdrant hybrid vector extraction for unstructured EHR context                     |
+---------------------------------------------+-------------------------------------+
                                             v
+-----------------------------------------------------------------------------------+
| 3. SYMBOLIC CONSTRAINT & REASONING LAYER (agents/reasoner/ & core/verification.py) |
|    - Deterministic elimination of clinical impossibilities (rules_engine.py)       |
|    - Conflict identification (drug-symptom, allergy-condition)                     |
|    - Bayesian posterior confidence updates & path elimination                      |
+---------------------------------------------+-------------------------------------+
                                             v
+-----------------------------------------------------------------------------------+
| 4. NEURAL EXPRESSION & SYNTHESIS LAYER (agents/synthesizer/ & core/llm_backend.py)   |
|    - Invokes fine-tuned LLM (MedGemma-4B-IT / vLLM / Ollama) strictly as subroutine  |
|    - Converts validated symbolic reasoning paths into clear clinical briefings       |
+---------------------------------------------+-------------------------------------+
                                             v
+-----------------------------------------------------------------------------------+
| 5. DETERMINISTIC GOVERNANCE LAYER (core/verification_layer.py & infra/opa/)       |
|    - OPA/Rego sidecar zero-trust policy verification (<5ms)                       |
|    - Native Python fallback validator (<50ms under OPA timeout)                   |
|    - Structural Cypher proof validation before final response delivery            |
+---------------------------------------------+-------------------------------------+
                                             v
+-----------------------------------------------------------------------------------+
| 6. MEMORY SUBSTRATE & AUDIT LEDGER (core/memory.py & storage/)                    |
|    - Redis Streams for state checkpointing (<15ms hydration)                      |
|    - Append-only event log for 100% deterministic replayability                   |
+-----------------------------------------------------------------------------------+
```

---

## 🛠️ Model Context Protocol (MCP) & Hub-and-Spoke Topology

The architecture enforces the **Model Context Protocol (MCP) specification v2024-11-05** via `core/mcp_protocol.py` (`MCPProtocolServer`, `ToolRegistry`, `MCPControlPlane`). Unlike probabilistic agent systems where an LLM calls tools directly, this engine utilizes a **Governed Hub-and-Spoke Control Plane**:

```
                         ┌─────────────────────────┐
                         │  MCP ProtocolServer     │
                         │  (JSON-RPC 2.0)         │
                         │  - tools/list (filtered)│
                         │  - tools/call (guarded) │
                         └────────────┬────────────┘
                                      │
                    ┌─────────────────┼──────────────────┐
                    │ mcp:call        │ mcp:call          │ mcp:call
                    ▼                 ▼                   ▼
┌──────────────────────────┐ ┌──────────────────┐ ┌──────────────────────┐
│ query_ehr (clinician+)  │ │ check_drug_int.  │ │ retrieve_literature  │
│ FHIR EHR query          │ │ SymbolicVerifier │ │ PubMed mock search   │
└──────────────────────────┘ └──────────────────┘ └──────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│              Permission Levels:                                    │
│  READONLY → CLINICIAN → ADMIN → SYSTEM                              │
│  order_lab requires ADMIN; all others require CLINICIAN             │
│  OPA fail-closed policy enforcement on every tool call              │
└─────────────────────────────────────────────────────────────────────┘
```

### Registered MCP Tools

| Tool | Permission | Capabilities | Description |
|------|-----------|-------------|-------------|
| `query_ehr` | CLINICIAN | `ehr`, `fhir`, `read` | Query electronic health record for patient data (FHIR) |
| `order_lab` | ADMIN | `lab`, `order`, `write` | Order a laboratory test for a patient |
| `check_drug_interaction` | CLINICIAN | `drug`, `safety`, `read` | Check for drug-drug or drug-condition interactions |
| `retrieve_literature` | CLINICIAN | `literature`, `evidence`, `read` | Search clinical literature for evidence |

### MCP API Endpoints

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/v1/mcp/initialize` | POST | API Key | MCP protocol handshake |
| `/v1/mcp/tools/list` | POST | API Key | List available tools by role |
| `/v1/mcp/tools/call` | POST | API Key | Execute MCP tool (JSON-RPC 2.0) |
| `/v1/mcp/agent/tool` | POST | API Key | Agent tool request via control plane |

---

## ✨ Features

| Area | Feature | Status |
|------|---------|--------|
| **Architecture** | Type 2 Symbolic[Neuro] Graph-Driven Reasoning Engine | ✅ |
| **UI Observability**| MAS Glass Box Cockpit with real-time ReAct trace and state inspector | ✅ |
| **MCP Topology** | Full MCP Protocol v2024-11-05 server: ToolRegistry, JSON-RPC 2.0, dynamic discovery | ✅ |
| **MCP Tools** | 4 clinical tools with RBAC (query_ehr, order_lab, check_drug_interaction, retrieve_literature) | ✅ |
| **MCP Security** | Permission levels, OPA policy pre-checks (fail-closed), circuit breaker protection | ✅ |
| **Pipeline** | Verify-then-generate pattern with topological cycle detection | ✅ |
| **Correction Loop**| Automated feedback iterations prior to human escalation | ✅ |
| **LLM Engine** | Bounded local inference via MedGemma-4B-IT, vLLM, Ollama, or MockLLM | ✅ |
| **LLM Subroutines**| Typed JSON schemas (`extract_symptoms`, `assess_differential`) | ✅ |
| **Ontology** | 178+ in-memory ontology triples covering SNOMED-CT, ICD-10, RxNorm | ✅ |
| **Governance** | OPA/Rego sidecar policy engine + sub-50ms native Python fallback validator | ✅ |
| **Retrieval** | Hybrid Qdrant vector search + active Cypher graph traversal + RRF fusion | ✅ |
| **Storage** | Multi-Tiered Memory: Working (Redis), Episodic (Qdrant), Semantic (Neo4j) | ✅ |
| **Security** | PII redaction, prompt injection detection, security headers, audit logging, payload limits | ✅ |
| **CI/CD** | Bandit SAST, Safety dependency scan, pip-audit vulnerability checks | ✅ |
| **Load Testing** | Locust simulation suite for capacity planning | ✅ |
| **Tests** | **223 passing, 5 skipped, 0 failures** | ✅ |

---

## API Endpoints

### Clinical Reasoning & Observability

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/v1/speculate` | POST | API Key | Main clinical reasoning (with PII redaction + injection guard) |
| `/v1/override` | POST | API Key | Human-in-the-loop approval |
| `/v1/reasoning_trace/{id}` | GET | API Key | Full audit trail |
| `/v1/agents/health` | GET | API Key | Agent health monitoring |
| `/v1/metrics/backends` | GET | API Key | Backend A/B performance |
| `/v1/policy/stats` | GET | API Key | Neural policy accuracy |
| `/v1/analytics/overrides` | GET | API Key | Override pattern analytics |
| `/v1/analytics/rules/apply` | POST | Admin Key | Apply approved rules + hot reload |

### MCP Protocol

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/v1/mcp/initialize` | POST | API Key | MCP protocol handshake |
| `/v1/mcp/tools/list` | POST | API Key | List available tools by role |
| `/v1/mcp/tools/call` | POST | API Key | Execute MCP tool (JSON-RPC 2.0) |
| `/v1/mcp/agent/tool` | POST | API Key | Agent tool request via control plane |

### Admin

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/v1/admin/policy/train` | POST | Admin Key | Trigger RLHF training |
| `/v1/admin/policy/evaluate` | GET | Admin Key | Evaluate neural vs static policy |

---

## 🔐 Security Hardening (v0.6.3)

Production-grade security controls addressing HIPAA data protection, prompt injection defense, and zero-trust governance:

### Input Sanitization (`core/security.py`)

| Layer | Implementation | Details |
|-------|---------------|---------|
| **PII Redaction** | `InputSanitizer.sanitize_patient_note()` | Redacts SSN, phone, email, DOB, MRN, Patient IDs via regex patterns before LLM processing |
| **Context Sanitization** | `InputSanitizer.sanitize_context()` | Recursively sanitizes nested dict/list values in `patient_context` |
| **Prompt Injection Detection** | `InputSanitizer.check_prompt_injection()` | Blocks known injection patterns (`ignore previous instructions`, template injection `{{}}`, XML/HTML comments, special token abuse) |
| **Encoding Attack Detection** | Heuristic special-character ratio check | Flags inputs with >30% non-alphanumeric characters as potential encoding attacks |
| **Structured Audit Logging** | `AuditLogger` | JSON-structured logs for clinical decisions, overrides, and safety violations with non-reversible `patient_hash` |

### Middleware Security (`api/middleware.py`)

| Middleware | Purpose | Configuration |
|-----------|---------|---------------|
| `SecurityHeadersMiddleware` | Adds HSTS, X-Content-Type-Options, X-Frame-Options, CSP | Applied to all responses |
| `ContentLengthMiddleware` | Rejects oversized payloads (10 MB default) | Prevents DoS via large request bodies |
| `RequestIDMiddleware` | Unique request tracing for audit correlation | UUID per request |
| `APIKeyMiddleware` | API key authentication for protected routes | Configurable via `API_KEY` env var |
| `RateLimitMiddleware` | Per-IP request rate limiting | 100 req/60s default |

### MCP Security (`core/mcp_protocol.py`, `infra/opa/policies/`)

| Layer | Implementation | Behavior |
|-------|---------------|----------|
| **RBAC Permission Check** | `PermissionLevel` enum filter | `readonly` cannot see admin tools; `order_lab` requires `admin` |
| **OPA Policy Enforcement** | `evaluate_tool_execution()` | OPA `tool_execution.rego` policy checked per tool call; **fail-closed** |
| **Circuit Breaker Protection** | `CircuitBreaker` per tool | Open state after 3 failures; prevents cascading failures |
| **Agent Health Gate** | `MCPControlPlane.agent_request_tool()` | Rejects requests from unhealthy or unregistered agents |

### CI/CD Security Gate (` .github/workflows/ci.yml`)

| Job | Tool | What It Does |
|-----|------|-------------|
| `security` | **Bandit** | SAST scan of `core/` and `api/` source — reports saved as artifact |
| `security` | **Safety** | Dependency vulnerability scan — reports saved as artifact |
| `test` | **pip-audit** | Python dependency CVE scan |
| `test` | **ruff** | Static analysis for security anti-patterns |

---

## 🚀 Quick Start & E2E Demo Mode

### Mode 1: Full E2E Production-Authentic Stack (CPU-Optimized)

Run authentic Cypher graph queries, vector similarity searches, and OPA policy checks on CPU without needing a GPU:

```bash
# 1. Clone repository
git clone https://github.com/aragit/speculative-clinical-graphrag.git
cd speculative-clinical-graphrag

# 2. Setup Virtual Environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Spin up Docker Infrastructure (Neo4j, Qdrant, OPA)
docker-compose up -d

# 4. Prepare E2E Demo (Seeds Neo4j, Qdrant, & OPA Rego Policies)
python scripts/prepare_demo.py

# 5. Load Demo Environment
cp .env.demo .env

# 6. Start FastAPI Backend (Terminal 1)
python -m uvicorn api.main:app --host 0.0.0.0 --port 8001 --reload

# 7. Start MAS Glass Box UI (Terminal 2)
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` to access the cockpit.

### Mode 2: Zero-Dependency Developer Mode (Mock Infra)

Run the entire pipeline and UI instantly without Docker:

```bash
# Launch backend in mock mode
python -m uvicorn api.main:app --host 0.0.0.0 --port 8001 --reload

# In a separate terminal, launch frontend
cd frontend && npm run dev
```

### API Usage

```bash
# Clinical reasoning with PII redaction & safety checks
curl -X POST http://localhost:8001/v1/speculate \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "patient_note": "Patient with dyspnea and chest pain",
    "patient_context": {"age": 65, "gender": "male"}
  }'

# MCP tool call
curl -X POST http://localhost:8001/v1/mcp/tools/call \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "check_drug_interaction",
      "arguments": {"drug_a": "Warfarin", "drug_b": "Aspirin"},
      "caller_role": "clinician"
    }
  }'

# Load testing with Locust
pip install -r requirements-dev.txt
locust -f scripts/load_test.py --host http://localhost:8001
```

---

## 📁 Project Directory Structure

```
speculative-clinical-graphrag/
│
├── api/                            # FastAPI Application Layer
│   ├── main.py                     # Entrypoint & lifecycle probes
│   ├── schemas.py                  # Pydantic models
│   ├── dependencies.py             # Dependency injection
│   └── middleware.py               # Security, rate limiting, auth middleware
│
├── core/                           # Neuro-Symbolic Core Engine
│   ├── workflow.py                 # 9-node state machine workflow + MCP tool_enrichment node
│   ├── supervisor.py               # Central MCP Orchestrator
│   ├── orchestrator.py             # StateGraph execution & loops
│   ├── llm_backend.py              # LLM Backends (MedGemma, Ollama, Mock)
│   ├── retrieval.py                # Hybrid RAG retriever (Vector + Cypher)
│   ├── verification_layer.py       # Neo4j, SymbolicVerifier, OPA integration, drug interactions
│   ├── mas_streamer.py             # SSE streaming engine for MAS events
│   ├── mcp_registry.py             # Legacy MCP registry (superseded by mcp_protocol.py)
│   ├── mcp_protocol.py             # MCP server: ToolRegistry, MCPProtocolServer, MCPControlPlane
│   ├── mcp_tools.py                # Clinical MCP tools (query_ehr, order_lab, check_drug_interaction, retrieve_literature)
│   ├── security.py                 # InputSanitizer (PII redaction, injection detection) & AuditLogger
│   ├── circuit_breaker.py          # Circuit breaker with fail-closed semantics
│   ├── dag_modifier.py             # Controlled topology modification
│   ├── neural_policy.py            # Neural policy network with RLHF
│   ├── confidence_fusion.py        # Weighted confidence aggregation
│   ├── rlhf_trainer.py             # RLHF training pipeline
│   ├── evolutio.py                 # Override analytics & rule generation
│   ├── persistence.py              # Trace storage (InMemory / Redis)
│   ├── telemetry.py                # OpenTelemetry instrumentation
│   ├── fhir_parser.py              # FHIR R4 parser
│   ├── idempodency.py              # Deterministic payload UUID5
│   └── state_machine.py           # Workflow state management
│
├── schemas/                        # SSE Event Protocol
│   └── mas_events.py               # Pydantic v2 event models
│
├── frontend/                       # MAS Glass Box Cockpit (React + Vite)
│   ├── src/
│   │   ├── components/
│   │   │   ├── MASCockpit.tsx      # Main glass box cockpit interface
│   │   │   ├── DAGCanvas.tsx       # React Flow Hub-and-Spoke MCP canvas
│   │   │   ├── ClinicalSummaryCard.tsx # Diagnostic output card
│   │   │   ├── EscalationCard.tsx  # HITL escalation UI
│   │   │   ├── ReActTrace.tsx      # Streaming reasoning log
│   │   │   └── MemoryState.tsx     # Live JSON state inspector
│   │   └── hooks/
│   │       └── useMASSream.ts      # SSE stream hook for real-time trace
│   ├── package.json
│   └── vite.config.ts
│
├── infra/
│   └── opa/
│       └── policies/
│           ├── clinical.rego           # Clinical safety path validation
│           └── tool_execution.rego     # MCP tool execution RBAC policy
│
├── scripts/
│   ├── prepare_demo.py                 # CPU E2E database & policy seeder
│   └── load_test.py                    # Locust load testing suite
│
├── tests/                            # Enterprise Verification Suite
│   ├── test_api.py
│   ├── test_mas_stream.py              # SSE streaming integration tests
│   ├── test_dag_compiler.py
│   ├── test_verification.py
│   ├── test_mcp_protocol.py            # MCP protocol, permissions, circuit breaker tests
│   ├── test_security.py                # PII redaction & prompt injection integration tests
│   └── test_workflow.py
│
├── assets/                           # Documentation screenshots & diagrams
│   └── UI_V3.png                     # MAS Glass Box Cockpit screenshot
├── .env.demo                       # Preconfigured CPU demo environment
├── docker-compose.yml
├── requirements.txt
├── requirements-dev.txt              # Dev dependencies (locust, bandit, safety)
├── pytest.ini
└── README.md
```

---

## 🤖 LLM Backends & Bounded Subroutines (Layer 4 Isolation)

The system supports four selectable backends via the `RUNTIME_LLM` environment variable:

| Backend | Class | Default Model Target | Primary Use Case |
|---------|-------|---------------------|------------------|
| `mock` | `MockLLMBackend` | — | Zero-GPU local testing & UI demo mode |
| `ollama` | `OllamaBackend` | `gemma2:2b` | Local CPU developer sandbox |
| `deepseek_r1` | `DeepSeekR1Backend` | `deepseek-ai/deepseek-r1-distill-qwen-32b` | Production GPU complex reasoning |
| `medgemma_4b_it` | `MedGemmaBackend` | `google/MedGemma-4B-IT` | Fine-tuned clinical inference engine |

---

### Deterministic LangGraph vs. Probabilistic Routing

Standard Agentic Usage (Probabilistic): LangGraph uses LLMs on conditional edges (if llm_router() == 'tool': ...). The execution path is trapped in the LLM's latent space, leaving it vulnerable to prompt injection, logic loops, and hallucinations.

Our Neuro-Symbolic Usage (Deterministic Chassis): LangGraph is used strictly as a State Machine and State Checkpointer. Edge transitions and node executions are determined by core/dag_compiler.py, topological sorting, Python rule engines, and OPA policy gates. The LLM is confined inside a single node (Layer 4 Synthesis) and has zero authority to alter execution flow.

---

## 🧪 Testing & Verification

```bash
pytest tests/ -v
# 223 passed, 5 skipped, 0 failures
```

![Tests](https://img.shields.io/badge/tests-223%20passed_0_failed-brightgreen)
![Coverage](https://img.shields.io/badge/coverage-94%25-brightgreen)
![Security](https://img.shields.io/badge/security-bandit%20%2B%20safety-blue)

### Test Area	What It Verifies
| Module | Description |
|--------|-------------|
| Reasoning Extraction | Strict truncation math ensuring clinician traces never break length contracts |
| DAG Compiler | Kahn's algorithm topological sorting & explicit cycle rejection |
| Memory Tiers | Redis working memory fallback & session hydration |
| Governance | Fail-secure policy evaluations with native Python sub-50ms fallback |
| MCP Protocol | JSON-RPC 2.0 handshake, permission filtering, circuit breaker, OPA enforcement |
| Security | PII redaction, prompt injection detection, security headers, audit logging |
| Idempotency | Deterministic payload UUID5 key generation |
| Workflow | End-to-end 9-node state graph execution with correction loops |

---

## 🐳 Docker & CI/CD

| Service | Image | Ports | Profile |
|---------|-------|-------|---------|
| neo4j | `neo4j:5.15-community` | 7687, 7474 | default |
| qdrant | `qdrant/qdrant` | 6333 | default |
| redis | `redis:7-alpine` | 6379 | default |
| opa | `openpolicyagent/opa` | 8181 | default |
| fastapi | *(builds from Dockerfile)* | 8001 | default |
| vllm | `vllm/vllm-openai` | 8000 | gpu |
| jaeger | `jaegertracing/all-in-one` | 16686 | tracing |

### CI Pipeline

| Job | Steps |
|-----|-------|
| `test` | Checkout → Python 3.12 → Install deps → Start OPA → Seed Neo4j → Run pytest → pip-audit → ruff |
| `security` | Checkout → Python 3.12 → Bandit SAST scan → Safety dependency scan → Upload reports |

---

## 📄 License

MIT License — Clinical AI Research & Engineering
