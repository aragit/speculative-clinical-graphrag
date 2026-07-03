
from abc import ABC, abstractmethod
from typing import List, Dict, Tuple, Optional
import re
import json
import httpx
import os
import copy

class LLMBackend(ABC):
    @abstractmethod
    async def generate_path(self, patient_note: str, context: Optional[Dict] = None) -> Dict:
        return {}

    @abstractmethod
    async def regenerate_with_feedback(self, patient_note: str, violations: List[Dict], prior_reasoning: str, context: Optional[Dict] = None) -> Dict:
        return {}

    @abstractmethod
    async def extract_symptoms(self, patient_note: str, context: Optional[Dict] = None) -> Dict:
        return {"symptoms": []}

    @abstractmethod
    async def assess_differential(self, symptoms: List[str], ontology_mappings: List[Dict], patient_context: Optional[Dict] = None) -> Dict:
        return {"triplets": [], "reasoning": ""}

    @property
    @abstractmethod
    def backend_type(self) -> str:
        return ""

class MockLLMBackend(LLMBackend):
    _MOCK_KNOWLEDGE_TEMPLATE = {
        "dyspnea": [
            {"head": "Dyspnea", "relation": "INDICATES", "tail": "Heart Failure", "confidence": 0.92},
            {"head": "Dyspnea", "relation": "INDICATES", "tail": "COPD", "confidence": 0.78},
            {"head": "Dyspnea", "relation": "INDICATES", "tail": "Pneumonia", "confidence": 0.74},
            {"head": "Dyspnea", "relation": "INDICATES", "tail": "Asthma", "confidence": 0.70},
            {"head": "Dyspnea", "relation": "INDICATES", "tail": "Pulmonary Embolism", "confidence": 0.65},
        ],
        "orthopnea": [
            {"head": "Orthopnea", "relation": "INDICATES", "tail": "Heart Failure", "confidence": 0.95},
            {"head": "Orthopnea", "relation": "INDICATES", "tail": "Pericardial Effusion", "confidence": 0.60},
        ],
        "chest pain": [
            {"head": "Chest Pain", "relation": "INDICATES", "tail": "Myocardial Infarction", "confidence": 0.88},
            {"head": "Chest Pain", "relation": "INDICATES", "tail": "Angina", "confidence": 0.82},
            {"head": "Chest Pain", "relation": "INDICATES", "tail": "Pulmonary Embolism", "confidence": 0.75},
            {"head": "Chest Pain", "relation": "INDICATES", "tail": "Pericarditis", "confidence": 0.68},
            {"head": "Chest Pain", "relation": "INDICATES", "tail": "Aortic Dissection", "confidence": 0.55},
        ],
        "fatigue": [
            {"head": "Fatigue", "relation": "INDICATES", "tail": "Anemia", "confidence": 0.72},
            {"head": "Fatigue", "relation": "INDICATES", "tail": "Heart Failure", "confidence": 0.68},
            {"head": "Fatigue", "relation": "INDICATES", "tail": "Hypothyroidism", "confidence": 0.65},
            {"head": "Fatigue", "relation": "INDICATES", "tail": "Depression", "confidence": 0.60},
        ],
        "edema": [
            {"head": "Edema", "relation": "INDICATES", "tail": "Heart Failure", "confidence": 0.85},
            {"head": "Edema", "relation": "INDICATES", "tail": "Chronic Kidney Disease", "confidence": 0.70},
            {"head": "Edema", "relation": "INDICATES", "tail": "Cirrhosis", "confidence": 0.65},
            {"head": "Edema", "relation": "INDICATES", "tail": "Nephrotic Syndrome", "confidence": 0.62},
        ],
        "palpitations": [
            {"head": "Palpitations", "relation": "INDICATES", "tail": "Atrial Fibrillation", "confidence": 0.80},
            {"head": "Palpitations", "relation": "INDICATES", "tail": "Anxiety", "confidence": 0.75},
            {"head": "Palpitations", "relation": "INDICATES", "tail": "Ventricular Tachycardia", "confidence": 0.60},
        ],
        "cough": [
            {"head": "Cough", "relation": "INDICATES", "tail": "COPD", "confidence": 0.78},
            {"head": "Cough", "relation": "INDICATES", "tail": "Pneumonia", "confidence": 0.76},
            {"head": "Cough", "relation": "INDICATES", "tail": "Asthma", "confidence": 0.72},
            {"head": "Cough", "relation": "INDICATES", "tail": "Lung Cancer", "confidence": 0.50},
        ],
        "fever": [
            {"head": "Fever", "relation": "INDICATES", "tail": "Sepsis", "confidence": 0.80},
            {"head": "Fever", "relation": "INDICATES", "tail": "Pneumonia", "confidence": 0.75},
            {"head": "Fever", "relation": "INDICATES", "tail": "Meningitis", "confidence": 0.65},
            {"head": "Fever", "relation": "INDICATES", "tail": "Malaria", "confidence": 0.55},
        ],
        "jaundice": [
            {"head": "Jaundice", "relation": "INDICATES", "tail": "Hepatitis", "confidence": 0.82},
            {"head": "Jaundice", "relation": "INDICATES", "tail": "Cirrhosis", "confidence": 0.78},
            {"head": "Jaundice", "relation": "INDICATES", "tail": "Biliary Obstruction", "confidence": 0.75},
            {"head": "Jaundice", "relation": "INDICATES", "tail": "Hemolysis", "confidence": 0.60},
        ],
        "hematuria": [
            {"head": "Hematuria", "relation": "INDICATES", "tail": "Bladder Cancer", "confidence": 0.70},
            {"head": "Hematuria", "relation": "INDICATES", "tail": "Kidney Stones", "confidence": 0.75},
            {"head": "Hematuria", "relation": "INDICATES", "tail": "UTI", "confidence": 0.72},
            {"head": "Hematuria", "relation": "INDICATES", "tail": "Glomerulonephritis", "confidence": 0.65},
        ],
        "syncope": [
            {"head": "Syncope", "relation": "INDICATES", "tail": "Arrhythmia", "confidence": 0.78},
            {"head": "Syncope", "relation": "INDICATES", "tail": "Orthostatic Hypotension", "confidence": 0.70},
            {"head": "Syncope", "relation": "INDICATES", "tail": "Pulmonary Embolism", "confidence": 0.55},
        ],
        "headache": [
            {"head": "Headache", "relation": "INDICATES", "tail": "Migraine", "confidence": 0.80},
            {"head": "Headache", "relation": "INDICATES", "tail": "Tension Headache", "confidence": 0.75},
            {"head": "Headache", "relation": "INDICATES", "tail": "Subarachnoid Hemorrhage", "confidence": 0.45},
            {"head": "Headache", "relation": "INDICATES", "tail": "Meningitis", "confidence": 0.55},
        ],
        "warfarin": [
            {"head": "Warfarin", "relation": "CONTRAINDICATES", "tail": "Aspirin", "confidence": 0.95},
            {"head": "Warfarin", "relation": "CONTRAINDICATES", "tail": "Ibuprofen", "confidence": 0.92},
        ],
        "metformin": [
            {"head": "Metformin", "relation": "CONTRAINDICATES", "tail": "Severe Renal Impairment", "confidence": 0.90},
        ],
        "aspirin": [
            {"head": "Aspirin", "relation": "TREATS", "tail": "Myocardial Infarction", "confidence": 0.88},
            {"head": "Aspirin", "relation": "TREATS", "tail": "Angina", "confidence": 0.82},
        ],
        "furosemide": [
            {"head": "Furosemide", "relation": "TREATS", "tail": "Heart Failure", "confidence": 0.90},
            {"head": "Furosemide", "relation": "TREATS", "tail": "Edema", "confidence": 0.88},
        ],
        "insulin": [
            {"head": "Insulin", "relation": "TREATS", "tail": "Diabetes Mellitus", "confidence": 0.95},
            {"head": "Insulin", "relation": "TREATS", "tail": "Diabetic Ketoacidosis", "confidence": 0.92},
        ],
        "nausea": [
            {"head": "Nausea", "relation": "INDICATES", "tail": "Gastroenteritis", "confidence": 0.70},
            {"head": "Nausea", "relation": "INDICATES", "tail": "Myocardial Infarction", "confidence": 0.55},
            {"head": "Nausea", "relation": "INDICATES", "tail": "Migraine", "confidence": 0.60},
        ],
        "wheeze": [
            {"head": "Wheeze", "relation": "INDICATES", "tail": "Asthma", "confidence": 0.85},
            {"head": "Wheeze", "relation": "INDICATES", "tail": "COPD", "confidence": 0.78},
            {"head": "Wheeze", "relation": "INDICATES", "tail": "Anaphylaxis", "confidence": 0.65},
        ],
        "confusion": [
            {"head": "Confusion", "relation": "INDICATES", "tail": "Delirium", "confidence": 0.80},
            {"head": "Confusion", "relation": "INDICATES", "tail": "Stroke", "confidence": 0.70},
            {"head": "Confusion", "relation": "INDICATES", "tail": "Hypoglycemia", "confidence": 0.75},
            {"head": "Confusion", "relation": "INDICATES", "tail": "Uremia", "confidence": 0.65},
        ],
    }

    def __init__(self, seed: int = 42):
        import copy
        self.seed = seed
        self.MOCK_KNOWLEDGE = copy.deepcopy(self._MOCK_KNOWLEDGE_TEMPLATE)

    @property
    def backend_type(self) -> str:
        return "mock"

    async def generate_path(self, patient_note: str, context: Optional[Dict] = None) -> Dict:
        note_lower = patient_note.lower()
        triplets = []
        for keyword, paths in self.MOCK_KNOWLEDGE.items():
            if keyword in note_lower:
                triplets.extend(copy.deepcopy(paths))
        if not triplets:
            triplets = [{"head": "Unknown Symptom", "relation": "INDICATES", "tail": "Unknown Condition", "confidence": 0.5}]
        reasoning = "MockLLM deterministic extraction from keywords"
        return {"triplets": triplets, "reasoning": reasoning, "dag_plan": None}

    async def regenerate_with_feedback(self, patient_note: str, violations: List[Dict], prior_reasoning: str, context: Optional[Dict] = None) -> Dict:
        note_lower = patient_note.lower()
        triplets = []
        for keyword, paths in self.MOCK_KNOWLEDGE.items():
            if keyword in note_lower:
                triplets.extend(copy.deepcopy(paths))
        if triplets:
            for t in triplets:
                t["confidence"] = max(t.get("confidence", 0.8) - 0.1, 0.5)
                t["corrected"] = True
            reasoning = "MockLLM correction attempt"
        else:
            triplets = []
            reasoning = "MockLLM: no valid matches after correction, forcing escalation."
        return {"triplets": triplets, "reasoning": reasoning, "dag_plan": None}

    async def extract_symptoms(self, patient_note: str, context: Optional[Dict] = None) -> Dict:
        note_lower = patient_note.lower()
        symptoms = []
        for keyword in self.MOCK_KNOWLEDGE:
            if keyword in note_lower:
                symptoms.append({"term": keyword.title(), "confidence": 0.95})
        return {"symptoms": symptoms}

    async def assess_differential(self, symptoms: List[str], ontology_mappings: List[Dict], patient_context: Optional[Dict] = None) -> Dict:
        matched = []
        for symptom in symptoms:
            key = symptom.lower()
            if key in self.MOCK_KNOWLEDGE:
                for t in self.MOCK_KNOWLEDGE[key]:
                    matched.append(copy.deepcopy(t))
        if not matched:
            matched = [{"head": "Unknown", "relation": "INDICATES", "tail": "Unknown Condition", "confidence": 0.5}]
        return {"triplets": matched, "reasoning": "MockLLM differential from ontology mappings"}

class OllamaBackend(LLMBackend):
    def __init__(self, model: str = "gemma2:2b", host: str = "http://localhost:11434", timeout: float = 60.0):
        self.model = model
        self.host = host
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)

    @property
    def backend_type(self) -> str:
        return "ollama"

    async def generate_path(self, patient_note: str, context: Optional[Dict] = None) -> Dict:
        prompt = self._build_prompt(patient_note, context)
        try:
            response = await self.client.post(
                f"{self.host}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False, "format": "json"},
            )
            response.raise_for_status()
            data = response.json()
            parsed = json.loads(data["response"])
            if isinstance(parsed, list):
                triplets = parsed
            elif isinstance(parsed, dict) and "triplets" in parsed:
                triplets = parsed["triplets"]
            else:
                triplets = []
            return {"triplets": triplets, "reasoning": f"Ollama ({self.model}) generation", "dag_plan": None}
        except Exception as e:
            return {"triplets": [], "reasoning": f"Ollama error: {e}", "dag_plan": None}

    async def regenerate_with_feedback(self, patient_note: str, violations: List[Dict], prior_reasoning: str, context: Optional[Dict] = None) -> Dict:
        prompt = self._build_correction_prompt(patient_note, violations, prior_reasoning, context)
        try:
            response = await self.client.post(
                f"{self.host}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False, "format": "json"},
            )
            response.raise_for_status()
            data = response.json()
            parsed = json.loads(data["response"])
            triplets = parsed if isinstance(parsed, list) else parsed.get("triplets", [])
            return {"triplets": triplets, "reasoning": f"Ollama correction. Prior: {prior_reasoning[:50]}...", "dag_plan": None}
        except Exception as e:
            return {"triplets": [], "reasoning": f"Ollama correction error: {e}", "dag_plan": None}

    def _build_prompt(self, patient_note: str, context: Optional[Dict]) -> str:
        ctx = f"Context: {json.dumps(context)}\n" if context else ""
        return f"""You are a clinical reasoning engine. Extract structured diagnostic pathways as JSON.
{ctx}Patient note: {patient_note}
Output a JSON array: [{"head": "...", "relation": "INDICATES", "tail": "...", "confidence": 0.9}]"""

    def _build_correction_prompt(self, patient_note: str, violations: List[Dict], prior_reasoning: str, context: Optional[Dict]) -> str:
        return f"""The following pathway was rejected by the medical ontology validator.
Violations: {json.dumps(violations)}
Prior reasoning: {prior_reasoning}
Patient note: {patient_note}
Regenerate respecting constraints. Output JSON array only."""

    async def extract_symptoms(self, patient_note: str, context: Optional[Dict] = None) -> Dict:
        prompt = f"""Extract only the medical symptoms and findings from this text.
Return a JSON object with a "symptoms" array of strings.
Patient note: {patient_note}
Output JSON: {{"symptoms": ["symptom1", "symptom2"]}}"""
        try:
            response = await self.client.post(
                f"{self.host}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False, "format": "json"},
            )
            response.raise_for_status()
            data = response.json()
            parsed = json.loads(data["response"])
            return {"symptoms": parsed.get("symptoms", [])}
        except Exception as e:
            return {"symptoms": []}

    async def assess_differential(self, symptoms: List[str], ontology_mappings: List[Dict], patient_context: Optional[Dict] = None) -> Dict:
        prompt = f"""You are a clinical reasoning engine. Given these extracted symptoms and their known ontology mappings, produce a ranked differential diagnosis.
Symptoms: {json.dumps(symptoms)}
Known ontology mappings (symptom → condition): {json.dumps(ontology_mappings)}
Patient context: {json.dumps(patient_context or {})}
Output a JSON array of triples: [{{"head": "Symptom", "relation": "INDICATES", "tail": "Condition", "confidence": 0.9}}]"""
        try:
            response = await self.client.post(
                f"{self.host}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False, "format": "json"},
            )
            response.raise_for_status()
            data = response.json()
            parsed = json.loads(data["response"])
            triplets = parsed if isinstance(parsed, list) else parsed.get("triplets", [])
            return {"triplets": triplets, "reasoning": f"Ollama differential for {len(symptoms)} symptoms"}
        except Exception as e:
            return {"triplets": [], "reasoning": f"Ollama differential error: {e}"}

class OpenAICompatBackend(LLMBackend):
    def __init__(self, base_url: str, model: str, timeout: float = 120.0):
        self.base_url = base_url
        self.model = model
        self.timeout = timeout
        try:
            import openai
            self.client = openai.AsyncOpenAI(base_url=base_url, api_key="not-needed", timeout=timeout)
        except ImportError:
            self.client = None
        self._client_available = self.client is not None

    async def _chat(self, prompt: str, max_tokens: int = 4096) -> str:
        if not self._client_available:
            return ""
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""

    async def generate_path(self, patient_note: str, context: Optional[Dict] = None) -> Dict:
        if not self._client_available:
            return {"triplets": [], "reasoning": "OpenAI client not installed", "dag_plan": None}
        from core.reasoning_extractor import extract_reasoning_trace
        prompt = self._build_prompt(patient_note, context)
        try:
            raw = await self._chat(prompt)
            reasoning, triplets = extract_reasoning_trace(raw)
            return {"triplets": triplets, "reasoning": reasoning, "dag_plan": None}
        except Exception as e:
            return {"triplets": [], "reasoning": f"{self.backend_type} error: {e}", "dag_plan": None}

    async def regenerate_with_feedback(self, patient_note: str, violations: List[Dict], prior_reasoning: str, context: Optional[Dict] = None) -> Dict:
        if not self._client_available:
            return {"triplets": [], "reasoning": "OpenAI client not installed", "dag_plan": None}
        from core.reasoning_extractor import extract_reasoning_trace, validate_reasoning_coherence
        prompt = self._build_correction_prompt(patient_note, violations, prior_reasoning, context)
        try:
            raw = await self._chat(prompt)
            reasoning, triplets = extract_reasoning_trace(raw)
            coherent = validate_reasoning_coherence(reasoning, prior_reasoning, violations)
            if not coherent:
                reasoning += " [WARNING: reasoning may not fully address prior violations]"
            return {"triplets": triplets, "reasoning": reasoning, "dag_plan": None}
        except Exception as e:
            return {"triplets": [], "reasoning": f"{self.backend_type} correction error: {e}", "dag_plan": None}

    async def extract_symptoms(self, patient_note: str, context: Optional[Dict] = None) -> Dict:
        if not self._client_available:
            return {"symptoms": []}
        prompt = f"""<think>Identify the key medical symptoms and findings in this patient note.</think>
Patient note: {patient_note}
Output JSON: {{"symptoms": ["symptom1", "symptom2"]}}"""
        try:
            raw = await self._chat(prompt, max_tokens=1024)
            from core.reasoning_extractor import extract_reasoning_trace
            _, triplets = extract_reasoning_trace(raw)
            return {"symptoms": triplets if isinstance(triplets, list) else []}
        except Exception as e:
            return {"symptoms": []}

    async def assess_differential(self, symptoms: List[str], ontology_mappings: List[Dict], patient_context: Optional[Dict] = None) -> Dict:
        if not self._client_available:
            return {"triplets": [], "reasoning": "OpenAI client not installed"}
        prompt = f"""<think>Given these symptoms and their known ontology mappings, produce a ranked differential diagnosis.</think>
Symptoms: {json.dumps(symptoms)}
Known ontology mappings: {json.dumps(ontology_mappings)}
Patient context: {json.dumps(patient_context or {})}
Output JSON array: [{{"head": "Symptom", "relation": "INDICATES", "tail": "Condition", "confidence": 0.9}}]"""
        try:
            raw = await self._chat(prompt, max_tokens=2048)
            from core.reasoning_extractor import extract_reasoning_trace
            reasoning, triplets = extract_reasoning_trace(raw)
            return {"triplets": triplets, "reasoning": reasoning}
        except Exception as e:
            return {"triplets": [], "reasoning": f"{self.backend_type} differential error: {e}"}

    def _build_prompt(self, patient_note: str, context: Optional[Dict]) -> str:
        ctx = f"Context: {json.dumps(context)}\n" if context else ""
        return f"""You are a clinical reasoning engine. Think step by step inside <think> tags, then output JSON.
{ctx}Patient note: {patient_note}

Step 1: Identify key symptoms and entities.
Step 2: Map to known diagnostic pathways.
Step 3: Assess confidence.

Output JSON array: [{"head": "...", "relation": "INDICATES", "tail": "...", "confidence": 0.9}]"""

    def _build_correction_prompt(self, patient_note: str, violations: List[Dict], prior_reasoning: str, context: Optional[Dict]) -> str:
        return f"""Previous reasoning: {prior_reasoning}
The ontology validator rejected these violations: {json.dumps(violations)}
Patient note: {patient_note}
Think carefully inside <think> tags about why each violation occurred and how to fix it. Then output corrected JSON array."""


class DeepSeekR1Backend(OpenAICompatBackend):
    def __init__(self, base_url: str = "http://localhost:8000/v1", model: str = "deepseek-ai/deepseek-r1-distill-qwen-32b", timeout: float = 120.0):
        super().__init__(base_url=base_url, model=model, timeout=timeout)

    @property
    def backend_type(self) -> str:
        return "deepseek_r1"


class VLLMBackend(OpenAICompatBackend):
    def __init__(self, base_url: str = "http://localhost:8000/v1", model: str = "deepseek-ai/deepseek-r1-distill-qwen-32b", timeout: float = 120.0):
        super().__init__(base_url=base_url, model=model, timeout=timeout)

    @property
    def backend_type(self) -> str:
        return "vllm"

class SemanticRouter:
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.simple_keywords = ["dyspnea", "chest pain", "fever", "cough", "headache", "fatigue"]

    async def route(self, patient_note: str) -> str:
        note_lower = patient_note.lower()
        word_count = len(patient_note.split())
        if any(k in note_lower for k in self.simple_keywords) and word_count < 30:
            return self.config.get("simple_backend", "mock")
        if any(phrase in note_lower for phrase in ["differential", "multiple comorbidities", "unclear diagnosis", "complex"]):
            return self.config.get("complex_backend", "deepseek_r1")
        return self.config.get("default_backend", "ollama")
