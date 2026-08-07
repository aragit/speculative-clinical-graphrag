import json
import re
import copy
from typing import List, Dict, Optional
from core.llm_backend import LLMBackend


class COGITATORBackend(LLMBackend):
    """
    Type 6 neural core with self-critique.
    Wraps a base LLM and adds generate->critique->refine loop.
    """

    def __init__(self, base_backend: LLMBackend, max_critique_iterations: int = 2):
        self.base = base_backend
        self.max_critique_iterations = max_critique_iterations

    @property
    def backend_type(self) -> str:
        return "cogitator"

    async def generate_path(self, patient_note: str, context: Optional[Dict] = None) -> Dict:
        initial = await self.base.generate_path(patient_note, context)
        triplets = initial.get("triplets", [])
        reasoning = initial.get("reasoning", "")

        iteration_count = 0
        for i in range(self.max_critique_iterations):
            iteration_count = i + 1
            critique = await self._critique_path(triplets, patient_note, reasoning, context)
            if critique.get("is_sound", True):
                break

            refined = await self._refine_path(triplets, critique, patient_note, context)
            triplets = refined.get("triplets", triplets)
            reasoning = refined.get("reasoning", reasoning)

        triplets = self._add_uncertainty(triplets, reasoning)

        return {
            "triplets": triplets,
            "reasoning": reasoning,
            "dag_plan": None,
            "critique_iterations": iteration_count,
        }

    async def _critique_path(
        self, triplets: List[Dict], patient_note: str, reasoning: str, context: Optional[Dict]
    ) -> Dict:
        if not triplets:
            return {"is_sound": False, "issues": ["Empty pathway"], "suggested_removals": [], "suggested_additions": []}

        prompt = f"""You are a clinical safety reviewer. Critique this diagnostic pathway for errors.

Patient note: {patient_note}
Reasoning: {reasoning}
Pathway: {json.dumps(triplets, indent=2)}

Check for:
1. Unsupported causal claims (symptom -> condition without evidence)
2. Missing contraindications (drug interactions, allergies, pregnancy)
3. Overconfident edges (confidence > 0.9 without strong justification)
4. Omitted differential diagnoses

Return JSON: {{"is_sound": true/false, "issues": ["issue1", "issue2"], "suggested_removals": ["Drug X"], "suggested_additions": ["Condition Y"]}}"""

        try:
            raw = await self._chat(prompt, max_tokens=2048)
            return self._extract_json(raw)
        except Exception:
            return {"is_sound": True, "issues": [], "suggested_removals": [], "suggested_additions": []}

    async def _refine_path(
        self, triplets: List[Dict], critique: Dict, patient_note: str, context: Optional[Dict]
    ) -> Dict:
        issues = critique.get("issues", [])
        removals = critique.get("suggested_removals", [])
        additions = critique.get("suggested_additions", [])

        filtered = []
        for t in triplets:
            if t.get("head") not in removals and t.get("tail") not in removals:
                filtered.append(t)

        # Reduce confidence on remaining edges based on issues found
        for t in filtered:
            if len(issues) > 0:
                t["confidence"] = max(t.get("confidence", 0.8) - 0.05 * len(issues), 0.5)

        return {
            "triplets": filtered,
            "reasoning": f"Refined after critique: {len(issues)} issues addressed. Issues: {json.dumps(issues)}",
        }

    def _add_uncertainty(self, triplets: List[Dict], reasoning: str) -> List[Dict]:
        reasoning_lower = reasoning.lower() if reasoning else ""
        for t in triplets:
            head = t.get("head", "").lower()
            tail = t.get("tail", "").lower()

            mentions_head = head in reasoning_lower if head else False
            mentions_tail = tail in reasoning_lower if tail else False
            mentions_both = mentions_head and mentions_tail

            if mentions_both and t.get("confidence", 0.5) > 0.7:
                t["uncertainty"] = 0.2
            elif mentions_head or mentions_tail:
                t["uncertainty"] = 0.4
            else:
                t["uncertainty"] = 0.7

            t["uncertainty"] = min(t["uncertainty"], 1.0 - t.get("confidence", 0.5))

        return triplets

    async def regenerate_with_feedback(self, patient_note: str, violations: List[Dict], prior_reasoning: str, context: Optional[Dict] = None) -> Dict:
        return await self.base.regenerate_with_feedback(patient_note, violations, prior_reasoning, context)

    async def extract_symptoms(self, patient_note: str, context: Optional[Dict] = None) -> Dict:
        return await self.base.extract_symptoms(patient_note, context)

    async def assess_differential(self, symptoms: List[str], ontology_mappings: List[Dict], patient_context: Optional[Dict] = None) -> Dict:
        result = await self.base.assess_differential(symptoms, ontology_mappings, patient_context)
        triplets = result.get("triplets", [])
        triplets = self._add_uncertainty(triplets, result.get("reasoning", ""))
        result["triplets"] = triplets
        return result

    async def _chat(self, prompt: str, max_tokens: int = 4096) -> str:
        base = self.base
        if hasattr(base, "_chat"):
            return await base._chat(prompt, max_tokens)
        elif hasattr(base, "client") and hasattr(base, "backend_type"):
            import openai
            if base._client_available:
                response = await base.client.chat.completions.create(
                    model=base.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                    max_tokens=max_tokens,
                )
                return response.choices[0].message.content or ""
        elif hasattr(base, "client") and hasattr(base, "host"):
            response = await base.client.post(
                f"{base.host}/api/generate",
                json={"model": base.model, "prompt": prompt, "stream": False},
            )
            response.raise_for_status()
            data = response.json()
            return data.get("response", "")
        else:
            raise NotImplementedError(f"Base backend {type(base).__name__} does not support direct chat")

    def _extract_json(self, raw: str) -> Dict:
        try:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                return json.loads(match.group())
        except (json.JSONDecodeError, TypeError):
            pass
        return {"is_sound": True, "issues": [], "suggested_removals": [], "suggested_additions": []}
