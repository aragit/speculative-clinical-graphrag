import pytest
from unittest.mock import AsyncMock, MagicMock
from core.cogitator import COGITATORBackend
from core.llm_backend import MockLLMBackend


@pytest.fixture
def mock_cogitator():
    base = MockLLMBackend()
    base._chat = AsyncMock(return_value='{"is_sound": false, "issues": ["Overconfident edge"], "suggested_removals": [], "suggested_additions": []}')
    return COGITATORBackend(base_backend=base)


@pytest.mark.asyncio
async def test_cogitator_self_critique():
    """Mock backend returns overconfident triplet, assert COGITATOR reduces confidence or removes it."""
    base = MockLLMBackend()
    base._chat = AsyncMock(return_value='{"is_sound": false, "issues": ["Overconfident edge"], "suggested_removals": ["Aspirin"], "suggested_additions": []}')
    cogitator = COGITATORBackend(base_backend=base)

    patient_note = "Patient on warfarin and aspirin"
    result = await cogitator.generate_path(patient_note)

    triplets = result.get("triplets", [])
    assert len(triplets) > 0
    assert result["critique_iterations"] >= 1

    for t in triplets:
        assert "uncertainty" in t
        assert 0.0 <= t["uncertainty"] <= 1.0
        assert t["uncertainty"] + t.get("confidence", 0.5) <= 1.0

    assert "Aspirin" not in [t.get("head") for t in triplets]
    assert "Aspirin" not in [t.get("tail") for t in triplets]


@pytest.mark.asyncio
async def test_cogitator_uncertainty():
    """High uncertainty when reasoning doesn't mention triplet entities."""
    base = MockLLMBackend()
    base._chat = AsyncMock(return_value='{"is_sound": true, "issues": [], "suggested_removals": [], "suggested_additions": []}')
    cogitator = COGITATORBackend(base_backend=base)

    patient_note = "Patient has dyspnea"
    result = await cogitator.generate_path(patient_note)

    triplets = result.get("triplets", [])
    assert len(triplets) > 0

    for t in triplets:
        assert "uncertainty" in t
        head = t.get("head", "").lower()
        tail = t.get("tail", "").lower()
        reasoning = result.get("reasoning", "").lower()

        # Calibration invariant always holds
        assert t["uncertainty"] + t.get("confidence", 0.5) <= 1.0

        # When reasoning doesn't mention either entity, uncertainty should be
        # at its raw level or clamped by calibration
        if head and head not in reasoning:
            if tail and tail not in reasoning:
                # Raw uncertainty is 0.7, but clamped to 1.0 - confidence
                expected_raw = 0.7
                clamped = min(expected_raw, 1.0 - t.get("confidence", 0.5))
                assert t["uncertainty"] == clamped or t["uncertainty"] == 0.7
        else:
            assert t["uncertainty"] < 0.7


@pytest.mark.asyncio
async def test_cogitator_calibration():
    """Uncertainty + confidence <= 1.0 for all triplets."""
    base = MockLLMBackend()
    base._chat = AsyncMock(return_value='{"is_sound": false, "issues": ["Issue"], "suggested_removals": [], "suggested_additions": []}')
    cogitator = COGITATORBackend(base_backend=base)

    result = await cogitator.generate_path("Fever and chest pain")

    for t in result["triplets"]:
        confidence = t.get("confidence", 0.5)
        uncertainty = t.get("uncertainty", 0.5)
        assert confidence + uncertainty <= 1.0, f"Calibration violated: {confidence} + {uncertainty} > 1.0"


@pytest.mark.asyncio
async def test_cogitator_delegates_methods():
    """COGITATOR should delegate non-critique methods to base backend."""
    base = MockLLMBackend()
    cogitator = COGITATORBackend(base_backend=base)

    symptoms = await cogitator.extract_symptoms("Patient has fever")
    assert "symptoms" in symptoms

    result = await cogitator.assess_differential(["fever"], [])
    assert "triplets" in result
    assert "uncertainty" in result["triplets"][0]
