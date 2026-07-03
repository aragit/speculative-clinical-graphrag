
<h1 align="center">Speculative Clinical GraphRAG</h1>
<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-blue" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-009688" alt="FastAPI">
  <img src="https://img.shields.io/badge/Neo4j-008CC1" alt="Neo4j">
  <img src="https://img.shields.io/badge/LangGraph-1C3C3C" alt="LangGraph">
  <img src="https://img.shields.io/badge/Pydantic-E92063" alt="Pydantic">
  <img src="https://img.shields.io/badge/License-MIT-green" alt="License">
</p>


<p align="center">
  <b>A self-correcting clinical knowledge core that validates every diagnostic pathway against strict medical taxonomies before generation.</b>
</p>

---

## 🎯 What Problem Does This Solve?

Medical LLMs hallucinate when given open-ended generative control. Even with post-generation validation, relying on neural weights to independently map complex, multi-step clinical pathways is inherently unsafe. 

**Speculative Clinical GraphRAG** solves this by inverting the control loop. Implementing a **Type 2 Symbolic[Neuro] Architecture**, the system never allows the LLM to freewheel. Instead, a deterministic Symbolic Planner decomposes the clinical case into bounded sub-goals. The LLM is invoked strictly as a subroutine to extract specific entities or propose constrained differentials, which are instantly validated against a grounded medical knowledge graph (Neo4j) and policy engine (OPA) before proceeding to the next step.

> **The Neuro-Symbolic Invariant**: The symbolic planner drives the state machine. The LLM is treated as a highly capable *tool*, not the *orchestrator*. No diagnostic pathway advances without mathematical and rule-based verification.

---

---

## 🏗️ Technical Specification

### Architecture Paradigm

Instead of `LLM generates -> Symbolic verifies`, the system follows:
`Symbolic Planner decomposes -> Bounded LLM Extraction -> Ontology Query -> Bounded LLM Proposal -> Policy Engine Verification -> State Update`.

#### Core Components

| Component | Technology | Role in Pipeline |
|-----------|-----------|------------------|
| **Symbolic Planner** | LangGraph StateGraph | Orchestrates the deterministic workflow, maintaining a strictly typed Working Memory (`GraphState`). |
| **Bounded Reasoner** | vLLM (MedGemma-4B-IT / DeepSeek-R1) | Executes highly constrained tasks (e.g., entity extraction, bounded differential generation) via structured JSON output. |
| **Knowledge Graph** | Neo4j Community + Cypher | Provides the definitive symbolic taxonomy for medical entities and relationships. |
| **Vector Retrieval** | Qdrant | Hybrid RAG component for semantic search over embedded ontology metadata. |
| **Safety Guardrails** | Open Policy Agent (OPA) | Sidecar container executing `clinical.rego` policies to catch drug interactions and contraindications mid-reasoning. |

---
## 🚀 Applications

### Clinical Decision Support
- **Deterministic Differential Diagnosis**: Proposed symptom-disease pathways are built step-by-step and cross-referenced against institutional guidelines before presentation to clinicians.
- **Drug Interaction Safety**: Prescription recommendations are structurally verified against OPA policies and drug-interaction graphs.
- **Closed-Loop Intelligence**: Capable of integrating with larger enterprise systems requiring rigid, explainable audit trails.

  

### Core Components

| Component | Technology | Role in Pipeline |
|-----------|-----------|------------------|
| **Speculative Reasoner** | DeepSeek-R1 (via vLLM) or MockLLM | Generates structured diagnostic pathway triplets `(head, relation, tail, confidence)` from patient notes |
| **Symbolic Verification** | Neo4j Community + Cypher | Validates every proposed edge against grounded medical ontologies (SNOMED-CT, ICD-10, institutional taxonomies) |
| **Orchestration Engine** | LangGraph StateGraph | Manages the cyclic speculate-verify-correct workflow with deterministic state transitions |
| **API Gateway** | FastAPI + Pydantic V2 | Exposes typed endpoints with auto-generated OpenAPI documentation and interactive sandbox |
| **Inference Backend** | vLLM (GPU) / Ollama (CPU) / MockLLM (zero-dep) | Model-agnostic abstraction supporting production, local, and CI environments |


**Key invariant**: No diagnostic pathway reaches the patient without passing through the verification layer. The LLM is treated as a *hypothesis generator*, not a *source of truth*.

---


## 📦 Installation

### Prerequisites

- Python 3.10+
- Docker & Docker Compose (for Neo4j)
- (Optional) Ollama for local LLM inference
- (Optional) CUDA 12.1+ for GPU inference via vLLM

### Quick Start (Zero GPU, Zero API Key)

```bash
# 1. Clone repository
git clone https://github.com/aragit/speculative-clinical-graphrag.git
cd speculative-clinical-graphrag

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Start Neo4j (Docker)
docker compose up -d

# 5. Launch API with MockLLM (no GPU, no API key)
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

### With Local LLM (Ollama, CPU)

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull 2B parameter model (~1.6GB)
ollama pull gemma2:2b

# Launch with Ollama backend
RUNTIME_LLM=ollama LLM_MODEL=gemma2:2b python -m uvicorn api.main:app --reload
```

### With Production GPU (vLLM)

```bash
# Install vLLM (requires CUDA)
pip install vllm

# Launch vLLM server with DeepSeek-R1
python -m vllm.entrypoints.openai.api_server \
    --model deepseek-ai/deepseek-r1-distill-qwen-32b \
    --tensor-parallel-size 2

# Launch API pointing to vLLM
RUNTIME_LLM=ollama OLLAMA_HOST=http://localhost:8000/v1 \
    python -m uvicorn api.main:app --reload
```

### DeepSeek-R1 Backend Implementation (GPU)

```bash
# core/llm_backend.py — DeepSeekR1Backend
class DeepSeekR1Backend(LLMBackend):
    """
    Production backend using DeepSeek-R1-Distill-Qwen-32B via vLLM.
    Extracts reasoning traces from <think>...</think> tags for validation.
    """
    def __init__(self, base_url: str = "http://localhost:8000/v1", model: str = "deepseek-ai/deepseek-r1-distill-qwen-32b"):
        self.client = openai.AsyncOpenAI(base_url=base_url, api_key="dummy")
        self.model = model

    async def generate_path(self, patient_note: str) -> List[Dict]:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": self._build_prompt(patient_note)}],
            temperature=0.1,
        )
        raw = response.choices[0].message.content
        reasoning, triplets = self._extract_reasoning(raw)
        return {"triplets": triplets, "reasoning": reasoning}

    def _extract_reasoning(self, raw: str) -> Tuple[str, List[Dict]]:
        """Extract <think>...</think> reasoning trace and JSON triplets."""
        think_match = re.search(r'<think>(.*?)</think>', raw, re.DOTALL)
        reasoning = think_match.group(1).strip() if think_match else ""
        # Parse JSON triplets from remaining text
        ...
        return reasoning, triplets
```
**Key invariant**: No diagnostic pathway reaches the patient without passing through the verification layer. The LLM is treated as a *hypothesis generator*, not a *source of truth*.

---

## 🔬 API Reference

### Interactive Documentation

Once running, visit: `http://localhost:8000/docs`

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Infrastructure liveness probe |
| `POST` | `/v1/speculate` | Principal speculative-validate-correct pipeline |

### Example Request

```bash
curl -X POST http://localhost:8000/v1/speculate \
  -H "Content-Type: application/json" \
  -d '{"patient_note": "Patient presents with dyspnea and orthopnea"}'
```

### Example Response (Valid Path)

```json
{
  "proposed_path": [
    {"head": "Dyspnea", "relation": "INDICATES", "tail": "Heart Failure", "confidence": 0.92},
    {"head": "Orthopnea", "relation": "INDICATES", "tail": "Heart Failure", "confidence": 0.95}
  ],
  "validation": {
    "is_valid": true,
    "valid_edges": [...],
    "violations": [],
    "total_checked": 2
  },
  "iterations": 1,
  "final_output": "Validated path: [...]",
  "status": "valid"
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
  "iterations": 3,
  "final_output": "Escalated to human review after 3 attempts.",
  "status": "escalated"
}
```

---

## 🧪 Testing

```bash
# Run full test suite
pytest tests/ -v

# Expected output:
# tests/test_workflow.py::test_valid_path PASSED
# tests/test_workflow.py::test_invalid_then_corrected PASSED
# tests/test_workflow.py::test_escalation_after_max_iterations PASSED
```

---

## 📁 Project Structure

```
speculative-clinical-graphrag/
├── api/
│   ├── __init__.py
│   └── main.py                 # FastAPI application, routing, lifecycle
├── core/
│   ├── __init__.py
│   ├── llm_backend.py          # LLMBackend protocol + MockLLM + Ollama implementations
│   ├── verification_layer.py  # Neo4j taxonomy validation engine
│   └── workflow.py             # LangGraph speculative-validate-correct state machine
├── graph/
│   └── schema.cypher           # Neo4j DDL (constraints, indexes, node/rel definitions)
├── tests/
│   ├── __init__.py
│   └── test_workflow.py        # Pytest suite for validation, correction, escalation
├── docker-compose.yml          # Neo4j Community Edition
├── requirements.txt            # Production dependencies
└── README.md                   # This file
```

---

## 🧬 Supported Taxonomies

| Source | Version | Status | Coverage |
|--------|---------|--------|----------|
| SNOMED-CT | US Edition 2024 | Planned | Clinical findings, disorders, procedures |
| ICD-10-CM | 2024 | Planned | Diagnosis classification, billing codes |
| RxNorm | Current | Planned | Drug names, ingredients, dose forms |
| UMLS Metathesaurus | 2024AB | Planned | Cross-vocabulary concept mapping |
| Custom Hospital Ontology | — | Configurable | Institutional pathways, formularies |

---

## 🔒 Safety & Compliance

- **Zero patient data persistence**: All processing is ephemeral; no PHI leaves the verification layer
- **Deterministic escalation**: Unvalidated paths always route to human review — never to patient-facing output
- **Audit trail**: Every speculation, validation, and correction is logged with full reasoning trace
- **Model-agnostic safety**: Verification logic is independent of the LLM backend; swapping models does not bypass guardrails

---

## 🛣️ Roadmap

| Phase | Deliverable | Status |
|-------|-------------|--------|
| **Phase 1** | Knowledge Foundation — Neo4j schema + SNOMED-CT ingestion | ✅ Complete |
| **Phase 2** | Speculative Parsing Engine — Structured triplet extraction | ✅ Complete |
| **Phase 3** | Verification Layer — Symbolic guardrail with corrective feedback | ✅ Complete |
| **Phase 4** | Production Deployment — vLLM containerization, streaming SSE | Planned |
| **Phase 5** | Multi-Hospital Federation — Federated taxonomy sync via TigerGraph | Research |

---

## 🤝 Contributing

This is an active research blueprint. Contributions welcome in:

- Additional medical ontologies (LOINC, ATC, MedDRA)
- Structured output formats (FHIR R4, JSON-LD, RDF)
- Evaluation benchmarks (MedQA, PubMedQA, custom clinical datasets)
- Edge deployment (NVIDIA Jetson, Apple Silicon)

---

## 📄 License

MIT License — Clinical AI Research & Engineering

---

<p align="center">
  <sub>Built with LangGraph, Neo4j, FastAPI, and a deep respect for clinical safety.</sub>
</p>
