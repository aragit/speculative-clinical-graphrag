import re
from typing import Tuple, List, Dict

REASONING_PATTERN = re.compile(r'<think>(.*?)</think>', re.DOTALL)

def extract_reasoning_trace(raw_output: str) -> Tuple[str, List[Dict]]:
    """Extract (reasoning_trace, triplets) from DeepSeek-R1 output."""
    match = REASONING_PATTERN.search(raw_output)
    if match:
        reasoning = match.group(1).strip()
        surface = REASONING_PATTERN.sub("", raw_output).strip()
    else:
        reasoning = ""
        surface = raw_output

    # Try JSON parse on surface
    triplets: List[Dict] = []
    try:
        import json
        parsed = json.loads(surface)
        if isinstance(parsed, list):
            triplets = parsed
        elif isinstance(parsed, dict):
            triplets = parsed.get("triplets", [])
    except json.JSONDecodeError:
        # Regex fallback: extract {"head":...} objects
        obj_pattern = re.compile(r'\{[^{}]*"head"[^}]*\}')
        for m in obj_pattern.finditer(surface):
            try:
                obj = json.loads(m.group())
                if "head" in obj and "relation" in obj and "tail" in obj:
                    triplets.append(obj)
            except Exception:
                continue
    return reasoning, triplets


def validate_reasoning_coherence(current_reasoning: str, prior_reasoning: str, violations: List[Dict]) -> bool:
    """Heuristic: current reasoning must mention at least one violation concept."""
    if not violations:
        return True
    current_lower = current_reasoning.lower()
    for v in violations:
        triplet = v.get("triplet", {})
        for key in ["head", "tail", "relation"]:
            val = triplet.get(key, "")
            if val and val.lower() in current_lower:
                return True
    return False


def surface_reasoning_for_clinician(reasoning_trace: str, max_length: int = 2000) -> str:
    """Truncate and format reasoning trace for API response.
    The returned string (including truncation suffix) strictly respects max_length."""
    if not reasoning_trace or len(reasoning_trace) <= max_length:
        return reasoning_trace or ""
    suffix = f"... [truncated, total length: {len(reasoning_trace)}]"
    if max_length <= len(suffix):
        return reasoning_trace[:max_length]
    slice_len = max_length - len(suffix)
    return reasoning_trace[:slice_len] + suffix
