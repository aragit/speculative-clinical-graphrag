<h1 align="center">Speculative Clinical GraphRAG</h1>

<p align="center">
  <b>A Type 6 Neuro-Symbolic Architecture Reference Implementation.</b><br>
  Symbolic guardrails constrain neural reasoning. Every diagnostic path is
  graph-verified, policy-checked, and human-escalatable.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-blue?style=flat-square&logo=python" alt="Python 3.12">
  <img src="https://img.shields.io/badge/Architecture-Type_6_Neuro--Symbolic-purple?style=flat-square" alt="Type 6 Neuro-Symbolic">
  <img src="https://img.shields.io/badge/MCP-Protocol_v2024--11--05-0052CC?style=flat-square" alt="MCP Protocol">
  <img src="https://img.shields.io/badge/Status-v0.6.4--adversarial--hardened-orange?style=flat-square" alt="v0.6.4-adversarial-hardened">
  <img src="https://img.shields.io/badge/Tests-227%2B%20Passed%20%7C%200%20Failed-brightgreen?style=flat-square" alt="Tests 227+ Passed">
  <img src="https://img.shields.io/badge/Adversarial%20Tests-35%20Red--Team-brightgreen?style=flat-square" alt="35 Adversarial Tests">
  <img src="https://img.shields.io/badge/FastAPI-0.110-009688?style=flat-square&logo=fastapi" alt="FastAPI 0.110">
  <img src="https://img.shields.io/badge/LangGraph-State_Engine-1C3C3C?style=flat-square" alt="LangGraph Engine">
  <img src="https://img.shields.io/badge/Neo4j-5.15-008CC1?style=flat-square&logo=neo4j" alt="Neo4j 5">
  <img src="https://img.shields.io/badge/OPA-Fail--Closed-7A5CF7?style=flat-square&logo=openpolicyagent" alt="OPA Policy">
</p>

---

## ⚠️ What This Is (And Isn't)

| This Is | This Isn't |
|---------|-----------|
| A **reference implementation** of Type 6 Neuro[Symbolic] architecture | A production clinical device (no FDA 510(k), no HIPAA BAA) |
| A **safety-first scaffold** designed to accept real ontologies, EHRs, and models | A deployed system connected to real patient records |
| An **adversarially red-teamed** multi-agent workflow with 227+ tests | A finished product with validated clinical efficacy |
| A **portfolio piece** demonstrating architectural depth, not marketing claims | A startup pitch deck |

---

## Architecture

```mermaid
flowchart TB
    subgraph Client
        C[API Client / EHR Webhook]
    end

    subgraph Gateway["FastAPI Gateway"]
        M[Security Middleware<br/>PII Redaction / Injection Filter]
        R[Rate Limit / Circuit Breakers / Security Headers]
    end

    subgraph Workflow["LangGraph Workflow (Type 6)"]
        direction TB
        FP[fhir_parse<br/>FHIR R4 Parser]
        IN[ingest<br/>Regex Fallback + Context Fusion]
        RC[retrieve_context<br/>Hybrid RAG: Qdrant + Neo4j]
        ES[extract_symptoms<br/>LLM Extraction]
        MO[map_to_ontology<br/>Graph Edge Mapping]
        AD[assess_differential<br/>COGITATOR Neural Core]
        VS[verify_safety<br/>Multi-Layer Verification]
        CD[correct_differential<br/>Feedback Loop + Convergence Check]
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
        NV[NeuralVerifier ABC<br/>MockNeuralVerifier (disabled by default)]
        CF[ConfidenceFusion<br/>Weighted Aggregation]
    end

    subgraph Learning["Self-Improvement (EVOLUTIO)"]
        OA[OverrideAnalytics<br/>Pattern Mining from Trace Store]
        RL[RLHFTrainer<br/>Logistic Regression on Outcomes]
        HR[Hot Reload<br/>SymbolicVerifier.load_rules()]
    end

    subgraph MCP["MCP Control Plane"]
        TR[ToolRegistry<br/>RBAC: query_ehr / order_lab / check_drug / retrieve_lit]
        MP[MCPProtocolServer<br/>JSON-RPC 2.0]
    end

    C --> M --> R
    R --> Workflow
    AD -.->|self-critique loop| AD
    VS --> Verification
    Verification --> CF
    CF -->|decision| VS
    ES2 --> OA
    OA -->|proposed rules| RL
    RL -->|approved rules| HR
    Workflow -->|agent requests| MCP
```

### Architecture Evolution

| Phase | Version | Status | Description |
|-------|---------|--------|-------------|
| R0 | v0.1.0 | ✅ | Mock ontology, basic LangGraph workflow |
| R1 | v0.2.0 | ✅ | Neo4j integration, multi-layer verification |
| R2 | v0.3.0 | ✅ | FHIR parser, external YAML rules, convergence detection, property tests |
| R3 | v0.5.0 | ✅ | NeuralVerifier ABC, AgentRegistry, ConfidenceFusion, DAGModifier, OverrideAnalytics |
| Type 6 | v0.6.0 | ✅ | COGITATOR self-critique, NeuralPolicy routing, EVOLUTIO learning |
| R4.1 | v0.6.1 | ✅ | RLHF training pipeline, admin endpoints |
| R4.2 | v0.6.2 | ✅ | MCP Protocol (JSON-RPC 2.0), clinical tool registry |
| **R5** | **v0.6.4** | **✅** | **Security hardening, PII redaction, adversarial red-teaming, load testing** |
| R6 | v0.7.0 | ⏳ | Glass Box UI, MCP tool_enrichment in workflow |
| Production | v1.0.0 | ⏳ | FDA alignment, real SNOMED-CT/UMLS, horizontal scale, SOC 2 |

### Type 2 Safety Invariants (Non-Negotiable)

These invariants are hardcoded and cannot be overridden by neural components:

| Invariant | Enforcement | Evidence |
|-----------|-------------|----------|
| Symbolic rules dominate by default | `enable_neural=false`, `enable_neural_policy=false` defaults | `core/workflow.py` |
| Max iterations → escalate | `iteration_count >= max_iterations` routes to escalate | `core/neural_policy.py` |
| Symbolic unsafe + high risk → escalate | Neural policy override regardless of heuristic score | `core/neural_policy.py` `predict()` |
| OPA fail-closed | Unreachable OPA returns `allow=False` | `core/verification_layer.py` |
| Immutable nodes protected | `ingest`, `verify_safety`, `escalate`, `fhir_parse` cannot be removed | `core/dag_modifier.py` |
| Human approval for self-modification | All generated rules have `status: pending_approval` | `core/evolutio.py` |
| PII redaction | SSN, phone, email, DOB, MRN redacted before LLM processing | `core/security.py` |
| Prompt injection blocking | Pattern-based detection blocks suspicious inputs with HTTP 400 | `core/security.py` |

### Confidence Fusion: From Boolean AND to Weighted Aggregation

Traditional clinical AI uses boolean logic: `neo4j_valid AND symbolic_valid AND opa_allowed`. This is brittle — one false positive blocks a valid path. This system uses probabilistic confidence fusion:

```mermaid
flowchart LR
    subgraph Inputs
        N[Neo4j<br/>confidence: 0.85]
        S[Symbolic<br/>confidence: 0.90]
        O[OPA<br/>confidence: 1.0]
        NV[Neural<br/>confidence: 0.70]
    end

    F[ConfidenceFusion<br/>weights: 0.30 / 0.35 / 0.20 / 0.15]
    D{Decision}

    N --> F
    S --> F
    O --> F
    NV --> F
    F -->|fused_score| D
    D -->|>= 0.7| V[valid]
    D -->|0.3–0.7| C[correct]
    D -->|< 0.3| E[escalate]
```

### Adversarial Safety Architecture

The system was red-teamed with 35 adversarial tests across 10 attack classes:

```mermaid
flowchart LR
    A1[Prompt Injection] --> D[InputSanitizer]
    A2[PII Extraction] --> D
    A3[Ontology Bypass] --> V[Neo4jVerifier]
    A4[Symbolic Evasion] --> S[SymbolicVerifier]
    A5[Backend Manipulation] --> B[BackendRouter]
    A6[Convergence Exhaustion] --> W[Workflow]
    A7[DAG Bypass] --> DM[DAGModifier]
    A8[OPA Downgrade] --> O[OPAClient]

    D -->|block| R[HTTP 400 / Sanitized]
    V -->|reject| E[Escalate]
    S -->|violate| E
    B -->|fallback| M[MockLLM]
    W -->|max_iter| E
    DM -->|reject| L[Log Only]
    O -->|fail-closed| E
```

### The Paradigm Shift: Neuro-Symbolic Control

Standard agentic frameworks leave routing and safety inside the LLM's latent space. In clinical settings, this causes hallucination loops and non-deterministic failures. This architecture inverts that:

**Symbolic Chassis** — LangGraph enforces deterministic state transitions. The LLM cannot alter workflow topology or skip verification.
**Neural Subroutine** — The LLM (MedGemma/DeepSeek via vLLM/Ollama) is bounded to extraction, assessment, and synthesis nodes only.
**Self-Critique** — COGITATOR wraps the LLM in a generate→critique→refine loop with uncertainty calibration.
**Learning Without Forgetting** — RLHF improves routing decisions, but symbolic drug-interaction rules are immutable.

### System Execution Flow

```plain
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  Raw Input  │────▶│  Perception  │────▶│   FHIR Parse    │
│  (note/EHR) │     │  Sanitize    │     │  Regex Fallback │
└─────────────┘     └──────────────┘     └─────────────────┘
                                                  │
┌─────────────────┐     ┌─────────────────┐      │
│  Confidence     │◀────│  Verification   │◀─────┘
│  Fusion         │     │  (Neo4j + Sym   │
│  (weighted)     │     │   + OPA + Neural)│
└────────┬────────┘     └─────────────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌───────┐  ┌──────────┐
│ Valid │  │ Escalate │
│ Synth │  │ Human    │
└───────┘  └──────────┘
```

### MCP Control Plane

The architecture implements MCP Protocol v2024-11-05 via `core/mcp_protocol.py`. Unlike direct LLM tool calling, this uses a governed hub-and-spoke control plane:

| Tool | Permission | Description |
|------|-----------|-------------|
| `query_ehr` | CLINICIAN | Query patient data via FHIR (mock EHR) |
| `order_lab` | ADMIN | Order laboratory tests |
| `check_drug_interaction` | CLINICIAN | Check drug-drug interactions against loaded rule set |
| `retrieve_literature` | CLINICIAN | Search clinical literature (mock PubMed) |

Security model: Role-based access control + OPA policy pre-check + circuit breaker per tool. `order_lab` is admin-only; all tools are fail-closed on OPA outage.

### Features

| Area | Feature | Status |
|------|---------|--------|
| Architecture | Type 6 Neuro[Symbolic] with Type 2 safety invariants | ✅ |
| Neural Core | COGITATOR self-critique loop (generate→critique→refine) | ✅ |
| Routing | NeuralPolicy with RLHF recording + heuristic fallback | ✅ |
| Verification | 4-layer fusion: Neo4j + Symbolic YAML + OPA + Neural stub | ✅ |
| Safety Rules | External YAML: drug interactions, allergies, pregnancy, age | ✅ |
| Self-Improvement | OverrideAnalytics → proposed rules → human approval → hot reload | ✅ |
| MCP | JSON-RPC 2.0 server, RBAC tool registry, circuit breakers | ✅ |
| LLM Backends | Mock / Ollama / DeepSeek-R1 / MedGemma-4B-IT / COGITATOR wrapper | ✅ |
| Retrieval | Hybrid Qdrant vector + Neo4j graph with fusion scoring | ✅ |
| Persistence | Redis-backed trace store with TTL; InMemory fallback | ✅ |
| Security | PII redaction, prompt injection detection, security headers, audit logging | ✅ |
| Testing | 227+ tests: unit, integration, property-based (Hypothesis), adversarial | ✅ |
| Load Testing | Locust simulation suite | ✅ |
| CI/CD | Bandit SAST, Safety dependency scan, pip-audit, ruff | ✅ |
| Frontend UI | Not implemented (R6 roadmap) | ⏳ |

### API Endpoints

#### Clinical Reasoning

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/v1/speculate` | POST | API Key | Main reasoning (PII redacted, injection-guarded) |
| `/v1/override` | POST | API Key | Human-in-the-loop approval |
| `/v1/reasoning_trace/{id}` | GET | API Key | Full audit trail with reasoning history |
| `/v1/agents/health` | GET | API Key | Agent registry health report |
| `/v1/metrics/backends` | GET | API Key | Backend A/B performance metrics |
| `/v1/policy/stats` | GET | API Key | Neural policy accuracy & history |

#### MCP Protocol

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/v1/mcp/initialize` | POST | API Key | MCP protocol handshake |
| `/v1/mcp/tools/list` | POST | API Key | List tools filtered by caller role |
| `/v1/mcp/tools/call` | POST | API Key | Execute MCP tool (JSON-RPC 2.0) |
| `/v1/mcp/agent/tool` | POST | API Key | Agent-mediated tool request |

#### Admin

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/v1/admin/policy/train` | POST | Admin Key | Trigger RLHF training from recorded outcomes |
| `/v1/admin/policy/evaluate` | GET | Admin Key | Neural vs static policy accuracy report |
| `/v1/analytics/overrides` | GET | API Key | Override pattern analytics |
| `/v1/analytics/rules/apply` | POST | Admin Key | Apply approved rules + hot reload |

---

## 🔐 Security Hardening (v0.6.4)

Production-grade security controls addressing HIPAA data protection, prompt injection defense, and zero-trust governance.

### Input Sanitization (`core/security.py`)

| Control | Implementation |
|---------|---------------|
| PII Redaction | Regex-based: SSN, phone, email, DOB, MRN, patient IDs stripped before LLM |
| Prompt Injection | Pattern + heuristic detection; blocked at API gateway with HTTP 400 |
| Context Recursion | `sanitize_context()` recursively cleans nested dicts/lists |
| Audit Logging | Structured JSON logs with SHA-256 patient hashes (not reversible) |

### Middleware Security (`api/middleware.py`)

| Middleware | Purpose |
|-----------|---------|
| `SecurityHeadersMiddleware` | HSTS, CSP, X-Frame-Options, nosniff |
| `ContentLengthMiddleware` | 10MB payload limit |
| `RequestIDMiddleware` | UUID trace correlation |
| `RateLimitMiddleware` | Per-IP throttling (100 req/60s) |

### CI Security Gate

| Job | Tool |
|-----|------|
| SAST | Bandit |
| Dependency CVE | Safety + pip-audit |
| Lint | ruff |

---

## 🚀 Quick Start & E2E Demo Mode

### Mode 1: Zero-Dependency (Mock Everything)

```bash
git clone https://github.com/aragit/speculative-clinical-graphrag.git
cd speculative-clinical-graphrag
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn api.main:app --host 0.0.0.0 --port 8001 --reload
```

### Mode 2: With Infrastructure (Neo4j, Qdrant, OPA, Redis)

```bash
docker-compose up -d
python -m uvicorn api.main:app --host 0.0.0.0 --port 8001 --reload
```

### Mode 3: GPU-Accelerated (vLLM + DeepSeek-R1 or MedGemma)

```bash
docker-compose --profile gpu up -d
# Set RUNTIME_LLM=deepseek_r1 in .env
```

### Tests

```bash
pytest tests/ -v
# 227+ passed, 5 skipped (external services), 0 failures
```

### Load Test

```bash
pip install -r requirements-dev.txt
locust -f scripts/load_test.py --host http://localhost:8001
```

---

## 📁 Project Directory Structure

```plain
speculative-clinical-graphrag/
├── api/
│   ├── main.py                 # FastAPI entrypoint, lifecycle, all endpoints
│   ├── schemas.py              # Pydantic request/response models
│   ├── dependencies.py         # DI: LLM router, verifiers, trace store
│   └── middleware.py           # Security, rate limit, auth, request ID
├── core/
│   ├── workflow.py             # 9-node LangGraph workflow + topology registry
│   ├── llm_backend.py          # Mock / Ollama / OpenAI-compat / vLLM / COGITATOR
│   ├── retrieval.py            # Hybrid Qdrant + Neo4j retriever
│   ├── verification_layer.py   # Neo4jVerifier, SymbolicVerifier, OPAClient
│   ├── verification_orchestrator.py  # Single verification entry point
│   ├── confidence_fusion.py    # Weighted multi-verifier aggregation
│   ├── neural_verifier.py      # NeuralVerifier ABC + MockNeuralVerifier
│   ├── neural_policy.py        # Heuristic routing + RLHF outcome recording
│   ├── cogitator.py            # Self-critique wrapper (generate→critique→refine)
│   ├── rlhf_trainer.py         # Logistic regression training from history
│   ├── evolutio.py             # Override analytics + rule generation
│   ├── dag_modifier.py         # Safety-gated topology changes
│   ├── topology.py             # Declarative workflow node registry
│   ├── agents.py               # AgentRegistry with health tracking
│   ├── backend_router.py       # Multi-backend resolution + metrics
│   ├── circuit_breaker.py      # OPEN/HALF_OPEN/CLOSED failure isolation
│   ├── persistence.py          # TraceStore ABC: Redis + InMemory
│   ├── security.py             # InputSanitizer + AuditLogger
│   ├── fhir_parser.py          # FHIR R4 Bundle/Resource parser
│   ├── mas_streamer.py         # SSE streaming for reasoning traces
│   └── reasoning_extractor.py  # Reasoning trace parsing + clinician surfacing
├── core/mcp_protocol.py        # MCP server: ToolRegistry, JSON-RPC 2.0
├── core/mcp_tools.py           # Clinical tool implementations
├── infra/opa/policies/
│   ├── clinical.rego           # Path validation policy
│   └── tool_execution.rego     # MCP tool RBAC policy
├── config/safety_rules/
│   ├── drug_interactions.yaml
│   ├── allergy_contraindications.yaml
│   ├── age_contraindications.yaml
│   └── pregnancy_contraindications.yaml
├── scripts/
│   └── load_test.py            # Locust load testing suite
├── tests/
│   ├── test_workflow.py
│   ├── test_verification.py
│   ├── test_verify_all.py
│   ├── test_api.py
│   ├── test_mcp_protocol.py
│   ├── test_property_invariants.py   # Hypothesis property tests
│   ├── test_adversarial_safety.py    # 35 red-team tests
│   └── test_security.py
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── requirements-dev.txt
├── pytest.ini
└── README.md
```

### LLM Backends

| Backend | Env Var | Description |
|---------|---------|-------------|
| mock | `RUNTIME_LLM=mock` | Deterministic responses for CI/tests |
| ollama | `RUNTIME_LLM=ollama` | Local CPU inference (gemma2:2b) |
| deepseek_r1 | `RUNTIME_LLM=deepseek_r1` | Complex reasoning via vLLM |
| medgemma_4b_it | `RUNTIME_LLM=medgemma_4b_it` | Clinical fine-tuned model via vLLM |
| cogitator | — | Wraps any above; adds self-critique + uncertainty calibration |

### Testing & Verification

```bash
pytest tests/ -v
```

| Suite | Count | What It Proves |
|-------|-------|----------------|
| Unit/Integration | ~180 | Workflow, verification, API correctness |
| Property-Based | 14 | Edge cases via Hypothesis (empty input, 10KB notes, random symptoms) |
| Adversarial | 35 | Safety invariants hold under attack (injection, bypass, exhaustion) |
| **Total** | **227+** | **0 failures** |

### 🐳 Docker & CI/CD

| Service | Image | Ports |
|---------|-------|-------|
| neo4j | `neo4j:5.15-community` | 7687, 7474 |
| qdrant | `qdrant/qdrant` | 6333 |
| redis | `redis:7-alpine` | 6379 |
| opa | `openpolicyagent/opa` | 8181 |
| fastapi | (build) | 8001 |
| vllm | `vllm/vllm-openai` | 8000 (gpu profile) |

### 📄 License

MIT License — Architecture Research & Engineering
