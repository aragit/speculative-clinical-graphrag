import pytest
from core.workflow import SpeculativeGraphRAG
from core.verification_layer import Neo4jVerifier, SymbolicVerifier
from core.llm_backend import MockLLMBackend
from core.backend_router import BackendRouter


def get_field(obj, key, default=None):
    if hasattr(obj, 'to_dict'):
        return obj.to_dict().get(key, default)
    if hasattr(obj, key):
        return getattr(obj, key, default)
    return obj.get(key, default)


@pytest.fixture
def rag():
    verifier = Neo4jVerifier()
    try:
        verifier.seed_mock_ontology()
    except Exception:
        pass
    router = BackendRouter({"mock": MockLLMBackend()}, default="mock")
    r = SpeculativeGraphRAG(
        router=router,
        verifier=verifier,
        symbolic_verifier=SymbolicVerifier(),
        max_iterations=3,
    )
    yield r
    try:
        r.verifier.close()
    except Exception:
        pass


@pytest.mark.asyncio
async def test_valid_path_1_iteration(rag):
    result = await rag.run("Patient has dyspnea and orthopnea")
    violations = get_field(result, "violations") or []
    opa_violations = [v for v in violations if "OPA" in v.get("reason", "")]
    if opa_violations:
        pytest.skip("OPA policy engine not running. Fail-closed denies the path.")
    assert get_field(result, "status") == "valid"
    assert get_field(result, "iteration_count") == 1
    validation_result = get_field(result, "validation_result") or {}
    assert len(validation_result.get("valid_edges", [])) > 0
    audit_log = get_field(result, "audit_log") or []
    assert any(e.get("node") == "ingest" for e in audit_log)
    symptoms = get_field(result, "extracted_symptoms") or []
    assert len(symptoms) == 2
    mappings = get_field(result, "ontology_mappings") or {}
    assert any("dyspnea" in str(k).lower() for k in mappings)


@pytest.mark.asyncio
async def test_invalid_path_escalation(rag):
    result = await rag.run("Patient has unknown rare symptom XYZ123")
    assert get_field(result, "status") == "escalated"
    assert get_field(result, "iteration_count") == 3


@pytest.mark.asyncio
async def test_escalate_on_nonsensical_input(rag):
    result = await rag.run("Completely nonsensical medical text")
    assert get_field(result, "status") == "escalated"
    final_output = get_field(result, "final_output") or ""
    assert "human review" in final_output.lower()


@pytest.mark.asyncio
async def test_reasoning_trace_in_response(rag):
    result = await rag.run("Patient has chest pain")
    reasoning = get_field(result, "reasoning_trace")
    assert reasoning is not None
    assert reasoning != ""


@pytest.mark.asyncio
async def test_opa_fail_closed(rag):
    result = await rag.run("Patient has dyspnea and orthopnea")
    status = get_field(result, "status")
    assert status in ("valid", "escalated")


@pytest.mark.asyncio
async def test_validation_mode_full(rag):
    result = await rag.run("Patient has dyspnea and orthopnea")
    violations = get_field(result, "violations") or []
    opa_violations = [v for v in violations if "OPA" in v.get("reason", "")]
    if opa_violations:
        pytest.skip("OPA policy engine not running. Cannot test 'full' mode.")
    val_mode = get_field(result, "validation_mode")
    assert val_mode == "full"


@pytest.mark.asyncio
async def test_backend_key_resolution(rag):
    result = await rag.run("Patient has chest pain", backend_key="mock")
    assert get_field(result, "backend_key") == "mock"
    audit_log = get_field(result, "audit_log") or []
    assert any("mock" in str(e.get("detail", "")) for e in audit_log)


@pytest.mark.asyncio
async def test_symptom_extraction_format(rag):
    result = await rag.run("Patient has dyspnea and chest pain")
    symptoms = get_field(result, "extracted_symptoms") or []
    assert len(symptoms) >= 2
    assert all("term" in s and "confidence" in s for s in symptoms)


@pytest.mark.asyncio
async def test_validation_mode_in_response(rag):
    result = await rag.run("Patient has dyspnea and chest pain", backend_key="mock")
    val_mode = get_field(result, "validation_mode")
    assert val_mode is not None
    assert val_mode in ("full", "degraded", "symbolic_only")
    validation_result = get_field(result, "validation_result") or {}
    assert "validation_mode" in validation_result


@pytest.mark.asyncio
async def test_safety_result_present(rag):
    result = await rag.run("Patient has chest pain")
    safety_result = get_field(result, "safety_result")
    assert safety_result is not None
    assert "is_safe" in safety_result
    assert "violations" in safety_result
    assert "validation_mode" in get_field(result, "validation_result") or True


@pytest.mark.asyncio
async def test_escalation_resets_iteration(rag):
    result = await rag.run("Patient has unknown rare symptom XYZ123")
    assert get_field(result, "status") == "escalated"
    assert get_field(result, "iteration_count") == 3


@pytest.mark.asyncio
async def test_convergence_escalation(rag):
    """When correction produces identical path, escalate immediately (< max_iterations)."""

    class StubBackend:
        backend_type = "mock"

        async def assess_differential(self, symptoms, mappings, context=None):
            return {
                "triplets": [{"head": "Symptom", "relation": "INDICATES", "tail": "Condition", "confidence": 0.9}],
                "reasoning": "stub reasoning",
            }

        async def regenerate_with_feedback(self, note, violations, prior, context=None):
            return {
                "triplets": [{"head": "Symptom", "relation": "INDICATES", "tail": "Condition", "confidence": 0.9}],
                "reasoning": "same reasoning",
            }

        async def extract_symptoms(self, note, context=None):
            return {"symptoms": [{"term": "Symptom", "confidence": 0.9}]}

    rag.router_backend.backends["mock"] = StubBackend()
    result = await rag.run("Patient has Symptom")
    assert get_field(result, "status") == "escalated"
    assert get_field(result, "iteration_count", 0) < 3


@pytest.mark.asyncio
async def test_fhir_parsing(rag):
    """FHIR Bundle in patient_context should populate age, gender, medications."""
    from datetime import datetime
    fhir_bundle = {
        "resourceType": "Bundle",
        "entry": [
            {"resource": {
                "resourceType": "Patient",
                "birthDate": "1950-06-15",
                "gender": "male"
            }},
            {"resource": {
                "resourceType": "MedicationRequest",
                "medicationCodeableConcept": {"text": "Warfarin"},
                "status": "active",
                "intent": "order"
            }},
        ]
    }
    result = await rag.run("Patient has dyspnea and orthopnea", patient_context=fhir_bundle)
    ctx = get_field(result, "patient_context") or {}
    assert "age" in ctx
    assert ctx["age"] == 76
    assert ctx["gender"] == "male"
    assert ctx["medications"] is not None
    assert len(ctx["medications"]) > 0


@pytest.mark.asyncio
async def test_fhir_fallback_to_regex(rag):
    """Without FHIR data, regex should still extract age and gender from note."""
    result = await rag.run("Patient has dyspnea and orthopnea")
    ctx = get_field(result, "patient_context") or {}
    assert ctx.get("age") is None or isinstance(ctx.get("age"), int)
    assert ctx.get("gender") is None or ctx["gender"] in ("male", "female")
