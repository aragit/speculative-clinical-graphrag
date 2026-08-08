"""Locust load testing for Speculative Clinical GraphRAG API.

Run with:
    locust -f scripts/load_test.py --host http://localhost:8001
"""
from locust import HttpUser, task, between


class ClinicalUser(HttpUser):
    wait_time = between(1, 3)

    @task(3)
    def speculate_simple(self):
        self.client.post("/v1/speculate", json={
            "patient_note": "Patient has dyspnea and chest pain",
            "patient_context": {"age": 65, "gender": "male"},
        })

    @task(1)
    def speculate_complex(self):
        self.client.post("/v1/speculate", json={
            "patient_note": "Patient has dyspnea, orthopnea, and edema. Currently on Warfarin and Aspirin.",
            "patient_context": {"age": 72, "gender": "female", "medications": ["Warfarin", "Aspirin"]},
        })

    @task(1)
    def health_check(self):
        self.client.get("/health")
