import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

def test_health_probes():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "neo4j_connected" in data
    assert "qdrant_connected" in data
    assert "opa_connected" in data
    assert data["version"] == "0.3.0"

def test_speculate_endpoint():
    response = client.post("/v1/speculate", json={"patient_note": "Patient has dyspnea"})
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] in ("valid", "corrected", "escalated")

def test_reasoning_trace_endpoint():
    r1 = client.post("/v1/speculate", json={"patient_note": "Patient has chest pain"})
    assert r1.status_code == 200

def test_speculate_escalation():
    response = client.post("/v1/speculate", json={"patient_note": "nonsense text that matches nothing"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "escalated"
