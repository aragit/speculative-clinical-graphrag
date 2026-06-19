from abc import ABC, abstractmethod
from typing import List, Dict
import json
import httpx


class LLMBackend(ABC):
    @abstractmethod
    def generate_path(self, patient_note: str) -> List[Dict]:
        pass

    @abstractmethod
    def regenerate_with_feedback(
        self, patient_note: str, violations: List[Dict]
    ) -> List[Dict]:
        pass


class MockLLMBackend(LLMBackend):
    MOCK_KNOWLEDGE = {
        "dyspnea": [
            {"head": "Dyspnea", "relation": "INDICATES", "tail": "Heart Failure", "confidence": 0.92},
            {"head": "Dyspnea", "relation": "INDICATES", "tail": "COPD", "confidence": 0.78},
        ],
        "orthopnea": [
            {"head": "Orthopnea", "relation": "INDICATES", "tail": "Heart Failure", "confidence": 0.95},
        ],
        "chest pain": [
            {"head": "Chest Pain", "relation": "INDICATES", "tail": "Myocardial Infarction", "confidence": 0.88},
        ],
    }

    def generate_path(self, patient_note: str) -> List[Dict]:
        note_lower = patient_note.lower()
        triplets = []
        for keyword, paths in self.MOCK_KNOWLEDGE.items():
            if keyword in note_lower:
                triplets.extend(paths)
        if not triplets:
            triplets = [
                {"head": "Unknown Symptom", "relation": "INDICATES", "tail": "Unknown Condition", "confidence": 0.5}
            ]
        return triplets

    def regenerate_with_feedback(
        self, patient_note: str, violations: List[Dict]
    ) -> List[Dict]:
        # Try partial matches first
        note_lower = patient_note.lower()
        triplets = []
        for keyword, paths in self.MOCK_KNOWLEDGE.items():
            if keyword in note_lower:
                triplets.extend(paths)
        
        if triplets:
            for t in triplets:
                t["confidence"] = max(t["confidence"] - 0.1, 0.5)
                t["corrected"] = True
            return triplets
        
        # No matches - return empty to force escalation
        return []


class OllamaBackend(LLMBackend):
    def __init__(
        self,
        model: str = "gemma2:2b",
        host: str = "http://localhost:11434",
        timeout: float = 60.0,
    ):
        self.model = model
        self.host = host
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)

    async def generate_path(self, patient_note: str) -> List[Dict]:
        prompt = self._build_prompt(patient_note)
        response = await self.client.post(
            f"{self.host}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
            },
        )
        response.raise_for_status()
        data = response.json()
        return json.loads(data["response"])

    async def regenerate_with_feedback(
        self, patient_note: str, violations: List[Dict]
    ) -> List[Dict]:
        prompt = self._build_correction_prompt(patient_note, violations)
        response = await self.client.post(
            f"{self.host}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
            },
        )
        response.raise_for_status()
        data = response.json()
        return json.loads(data["response"])

    def _build_prompt(self, patient_note: str) -> str:
        return f"""You are a clinical reasoning engine. Given a patient note, extract structured diagnostic pathways as JSON.

Patient note: {patient_note}

Output a JSON array of objects with keys: head, relation, tail, confidence.
Example: [{{"head": "Dyspnea", "relation": "INDICATES", "tail": "Heart Failure", "confidence": 0.92}}]
"""

    def _build_correction_prompt(
        self, patient_note: str, violations: List[Dict]
    ) -> str:
        return f"""The following diagnostic pathway was rejected by the medical taxonomy validator:

Violations: {json.dumps(violations)}

Patient note: {patient_note}

Please regenerate a corrected pathway that respects the taxonomy constraints.
Output a JSON array of objects with keys: head, relation, tail, confidence.
"""
