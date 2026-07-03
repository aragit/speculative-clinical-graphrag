from core.reasoning_extractor import extract_reasoning_trace, validate_reasoning_coherence, surface_reasoning_for_clinician

def test_extract_reasoning_trace():
    raw = 'First, consider symptoms. [{"head":"Fever","relation":"INDICATES","tail":"Sepsis","confidence":0.8}]'
    reasoning, triplets = extract_reasoning_trace(raw)
    assert len(triplets) == 1

def test_validate_coherence():
    current = "I will avoid Aspirin with Warfarin due to bleed risk."
    prior = "previous"
    violations = [{"triplet": {"head": "Aspirin", "relation": "CONTRAINDICATES", "tail": "Warfarin"}}]
    assert validate_reasoning_coherence(current, prior, violations) is True
    current_bad = "This reasoning ignores all issues."
    assert validate_reasoning_coherence(current_bad, prior, violations) is False

def test_surface_reasoning_for_clinician():
    long_text = "x" * 3000
    out = surface_reasoning_for_clinician(long_text, max_length=2000)
    assert out.endswith("... [truncated, total length: 3000]")
    assert len(out) < 2100
