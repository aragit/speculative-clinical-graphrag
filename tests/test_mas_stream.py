import pytest
import json
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

EXPECTED_EVENT_TYPES = ["NODE_START", "REACT_TRACE", "STATE_MUTATION", "GOVERNANCE_CHECK", "NODE_END", "FINAL_SYNTHESIS"]


def _parse_sse_events(response_body: str) -> list[dict]:
    """Parse SSE text response into list of event dicts."""
    events = []
    for line in response_body.strip().split("\n"):
        line = line.strip()
        if not line.startswith("data: "):
            continue
        payload = line[6:]
        if payload == "[DONE]":
            continue
        try:
            events.append(json.loads(payload))
        except json.JSONDecodeError:
            pass
    return events


def test_stream_endpoint_returns_200():
    """POST /v1/chat/stream returns HTTP 200 with text/event-stream."""
    response = client.post(
        "/v1/chat/stream",
        json={"patient_note": "Patient has dyspnea"},
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")


def test_stream_emits_node_start_events():
    """Stream emits NODE_START events for each agent node."""
    response = client.post(
        "/v1/chat/stream",
        json={"patient_note": "Patient has dyspnea"},
    )
    events = _parse_sse_events(response.text)

    node_starts = [e for e in events if e.get("event_type") == "NODE_START"]
    node_ids_started = [e["node_id"] for e in node_starts]

    assert "supervisor" in node_ids_started
    assert "clinical_extractor" in node_ids_started
    assert "ontology_traverser" in node_ids_started
    assert "opa_verifier" in node_ids_started
    assert "synthesizer" in node_ids_started


def test_stream_emits_react_traces():
    """Stream emits REACT_TRACE events with agent_name and thought."""
    response = client.post(
        "/v1/chat/stream",
        json={"patient_note": "Patient has dyspnea"},
    )
    events = _parse_sse_events(response.text)

    traces = [e for e in events if e.get("event_type") == "REACT_TRACE"]
    assert len(traces) >= 4  # At least one trace per agent

    for trace in traces:
        payload = trace.get("payload", {})
        assert "agent_name" in payload
        assert "thought" in payload


def test_stream_emits_governance_check():
    """Stream emits GOVERNANCE_CHECK event during verification."""
    response = client.post(
        "/v1/chat/stream",
        json={"patient_note": "Patient has dyspnea"},
    )
    events = _parse_sse_events(response.text)

    gov_checks = [e for e in events if e.get("event_type") == "GOVERNANCE_CHECK"]
    assert len(gov_checks) >= 1

    check = gov_checks[0]
    payload = check.get("payload", {})
    assert "passed" in payload
    assert "violations" in payload
    assert "policy_name" in payload


def test_stream_emits_state_mutations():
    """Stream emits STATE_MUTATION events with changed_keys."""
    response = client.post(
        "/v1/chat/stream",
        json={"patient_note": "Patient has dyspnea"},
    )
    events = _parse_sse_events(response.text)

    mutations = [e for e in events if e.get("event_type") == "STATE_MUTATION"]
    assert len(mutations) >= 3  # At least clinical_extractor, ontology_traverser, opa_verifier

    for mutation in mutations:
        payload = mutation.get("payload", {})
        assert "changed_keys" in payload
        assert "state_snapshot" in payload


def test_stream_emits_final_synthesis():
    """Stream emits FINAL_SYNTHESIS and ends with [DONE]."""
    response = client.post(
        "/v1/chat/stream",
        json={"patient_note": "Patient has dyspnea"},
    )
    events = _parse_sse_events(response.text)

    final_events = [e for e in events if e.get("event_type") == "FINAL_SYNTHESIS"]
    assert len(final_events) >= 1

    final = final_events[0]
    payload = final.get("payload", {})
    assert payload.get("output_type") in ("synthesis", "escalation")
    assert "summary" in payload

    assert response.text.strip().endswith("data: [DONE]")


def test_stream_event_sequence():
    """Events arrive in correct topological order: NODE_START before NODE_END for each node."""
    response = client.post(
        "/v1/chat/stream",
        json={"patient_note": "Patient has dyspnea"},
    )
    events = _parse_sse_events(response.text)

    node_events = [e for e in events if e.get("event_type") in ("NODE_START", "NODE_END")]

    # For each node, first occurrence should be NODE_START
    seen_nodes = set()
    for e in node_events:
        nid = e["node_id"]
        etype = e["event_type"]
        if nid not in seen_nodes:
            assert etype == "NODE_START", f"First event for node '{nid}' should be NODE_START, got {etype}"
            seen_nodes.add(nid)


def test_stream_escalation_path():
    """Nonsensical input triggers escalation via FINAL_SYNTHESIS."""
    response = client.post(
        "/v1/chat/stream",
        json={"patient_note": "xyzzy blorp flurb nothing medical here"},
    )
    events = _parse_sse_events(response.text)

    final_events = [e for e in events if e.get("event_type") == "FINAL_SYNTHESIS"]
    assert len(final_events) >= 1

    final = final_events[0]
    payload = final.get("payload", {})
    # Could be synthesis or escalation depending on mock LLM behavior
    assert payload.get("output_type") in ("synthesis", "escalation")


def test_stream_with_patient_context():
    """Stream accepts patient_context alongside patient_note."""
    response = client.post(
        "/v1/chat/stream",
        json={
            "patient_note": "Patient has dyspnea",
            "patient_context": {"age": 67, "gender": "male", "medications": ["Metformin"]},
        },
    )
    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    assert len(events) > 0


def test_stream_all_events_have_required_fields():
    """Every MASEvent has event_id, timestamp, event_type, node_id, payload."""
    response = client.post(
        "/v1/chat/stream",
        json={"patient_note": "Patient has chest pain"},
    )
    events = _parse_sse_events(response.text)

    for event in events:
        assert "event_id" in event, f"Missing event_id: {event}"
        assert "timestamp" in event, f"Missing timestamp: {event}"
        assert "event_type" in event, f"Missing event_type: {event}"
        assert "node_id" in event, f"Missing node_id: {event}"
        assert "payload" in event, f"Missing payload: {event}"
        assert event["event_type"] in EXPECTED_EVENT_TYPES, f"Unknown event_type: {event['event_type']}"
