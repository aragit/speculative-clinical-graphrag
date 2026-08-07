import os
import pytest
import tempfile
import shutil
from core.evolutio import OverrideAnalytics
from core.persistence import InMemoryTraceStore
from core.verification_layer import SymbolicVerifier


@pytest.fixture
def temp_dirs():
    staging = tempfile.mkdtemp(prefix="staging_")
    active = tempfile.mkdtemp(prefix="active_")
    os.makedirs(os.path.join(active, "staging"), exist_ok=True)

    old_staging = os.environ.get("RULES_STAGING_DIR")
    old_active = os.environ.get("RULES_ACTIVE_DIR")

    os.environ["RULES_STAGING_DIR"] = staging
    os.environ["RULES_ACTIVE_DIR"] = active

    yield {"staging": staging, "active": active}

    os.environ["RULES_STAGING_DIR"] = old_staging or ""
    os.environ["RULES_ACTIVE_DIR"] = old_active or ""
    shutil.rmtree(staging, ignore_errors=True)
    shutil.rmtree(active, ignore_errors=True)


@pytest.fixture
def analytics(temp_dirs):
    store = InMemoryTraceStore()
    return OverrideAnalytics(store)


@pytest.fixture
def symbolic_verifier(temp_dirs):
    sv = SymbolicVerifier(rules_dir=temp_dirs["active"])
    return sv


def _seed_proposed_rules(analytics, count=1):
    for i in range(count):
        analytics.proposed_rules.append({
            "type": "drug_interaction",
            "drugs": ["Warfarin", "Aspirin"],
            "frequency": 3,
            "confidence": 0.75,
            "status": "pending_approval",
            "reason": "Test rule",
        })


@pytest.mark.asyncio
async def test_rule_persistence(analytics, temp_dirs, symbolic_verifier):
    _seed_proposed_rules(analytics)

    approved = await analytics.approve_rule(0)
    assert approved is True
    assert analytics.proposed_rules[0]["status"] == "approved"

    staged_files = [f for f in os.listdir(temp_dirs["staging"]) if f.endswith(".yaml")]
    assert len(staged_files) == 1

    result = await analytics.apply_approved_rules()
    assert result["applied"] == 1
    assert len(result["files"]) == 1

    active_files = [f for f in os.listdir(temp_dirs["active"]) if f.endswith(".yaml") and f != "staging"]
    assert len(active_files) == 1

    # Hot reload the verifier
    loaded = symbolic_verifier.hot_reload()
    assert loaded > 0
    assert ("Warfarin", "Aspirin") in symbolic_verifier.drug_interactions


@pytest.mark.asyncio
async def test_rule_backup(analytics, temp_dirs, symbolic_verifier):
    _seed_proposed_rules(analytics)

    # Create an existing rule file in active dir
    existing_yaml = os.path.join(temp_dirs["active"], "existing_rule.yaml")
    with open(existing_yaml, "w") as f:
        f.write('rules: [{"type": "drug_interaction", "drugs": ["A", "B"], "status": "active"}]')

    approved = await analytics.approve_rule(0)
    assert approved is True

    result = await analytics.apply_approved_rules()
    assert result["applied"] == 1

    backup_dir = result["backup_location"]
    assert os.path.exists(backup_dir)

    backup_files = os.listdir(backup_dir)
    assert "existing_rule.yaml" in backup_files


@pytest.mark.asyncio
async def test_approve_invalid_rule_id(analytics):
    _seed_proposed_rules(analytics)
    approved = await analytics.approve_rule(99)
    assert approved is False


@pytest.mark.asyncio
async def test_apply_no_staged_rules(analytics):
    result = await analytics.apply_approved_rules()
    assert result["applied"] == 0

    files = [f for f in os.listdir(analytics.staging_dir) if f.endswith(".yaml")]
    assert len(files) == 0
