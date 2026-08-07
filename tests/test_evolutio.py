import pytest
from core.evolutio import OverrideAnalytics
from core.persistence import InMemoryTraceStore


@pytest.fixture
def mock_traces():
    store = InMemoryTraceStore()
    store._store = {
        "trace1": {
            "trace_id": "trace1",
            "status": "clinician_approved",
            "override_action": "approve",
            "proposed_path": [{"head": "Warfarin", "relation": "CONTRAINDICATES", "tail": "Aspirin", "confidence": 0.95}],
            "patient_context": {"age": 65, "gender": "male"},
            "override": True,
            "_stored_at": "2026-08-08T10:00:00",
        },
        "trace2": {
            "trace_id": "trace2",
            "status": "clinician_approved",
            "override_action": "modify",
            "proposed_path": [{"head": "Warfarin", "relation": "CONTRAINDICATES", "tail": "Aspirin", "confidence": 0.9}],
            "patient_context": {"age": 70, "gender": "male"},
            "override": True,
            "_stored_at": "2026-08-08T11:00:00",
        },
        "trace3": {
            "trace_id": "trace3",
            "status": "clinician_rejected",
            "override_action": "reject",
            "proposed_path": [{"head": "Warfarin", "relation": "CONTRAINDICATES", "tail": "Heparin", "confidence": 0.85}],
            "patient_context": {"age": 75, "gender": "female"},
            "override": True,
            "_stored_at": "2026-08-08T12:00:00",
        },
    }
    return store


@pytest.mark.asyncio
async def test_override_analytics_generates_rules(mock_traces):
    analytics = OverrideAnalytics(mock_traces)
    result = await analytics.analyze_recent(hours=48)

    assert result["total_overrides"] == 3
    assert len(result["proposed_rules"]) > 0

    # Warfarin+Aspirin appeared in 2 overrides -> should generate a drug_interaction rule
    di_rules = [r for r in result["proposed_rules"] if r["type"] == "drug_interaction"]
    assert len(di_rules) >= 1
    assert any(r["status"] == "pending_approval" for r in di_rules)

    # Pattern should show Warfarin+Aspirin
    drug_patterns = result["patterns"]["drug_interactions"]
    assert "Warfarin+Aspirin" in drug_patterns
    assert drug_patterns["Warfarin+Aspirin"] == 2


@pytest.mark.asyncio
async def test_override_analytics_no_overrides():
    store = InMemoryTraceStore()
    store._store = {
        "trace1": {
            "trace_id": "trace1",
            "status": "valid",
            "override": False,
            "_stored_at": "2026-08-08T10:00:00",
        },
    }
    analytics = OverrideAnalytics(store)
    result = await analytics.analyze_recent()
    assert result["total_overrides"] == 0
    assert len(result["proposed_rules"]) == 0


@pytest.mark.asyncio
async def test_approve_rule():
    store = InMemoryTraceStore()
    analytics = OverrideAnalytics(store)
    analytics.proposed_rules = [{
        "type": "drug_interaction",
        "drugs": ["Warfarin", "Aspirin"],
        "frequency": 2,
        "confidence": 0.7,
        "status": "pending_approval",
        "reason": "test",
    }]

    success = await analytics.approve_rule(0)
    assert success is True
    assert analytics.proposed_rules[0]["status"] == "approved"
    assert "approved_at" in analytics.proposed_rules[0]

    # Invalid index
    success = await analytics.approve_rule(99)
    assert success is False


@pytest.mark.asyncio
async def test_reject_rule():
    store = InMemoryTraceStore()
    analytics = OverrideAnalytics(store)
    analytics.proposed_rules = [{
        "type": "drug_interaction",
        "drugs": ["Warfarin", "Aspirin"],
        "frequency": 2,
        "confidence": 0.7,
        "status": "pending_approval",
        "reason": "test",
    }]

    success = await analytics.reject_rule(0)
    assert success is True
    assert analytics.proposed_rules[0]["status"] == "rejected"
