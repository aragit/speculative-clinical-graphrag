from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


class SupervisorAgent:
    def __init__(self, workers: List[Any] = None, llm_backend=None, verifier=None, symbolic_verifier=None):
        self.workers = workers or []
        self.llm = llm_backend
        self.verifier = verifier
        self.symbolic = symbolic_verifier
        self._register_default_workers()

    def _register_default_workers(self):
        self.workers = [
            {"name": "symptom_extractor", "capability": "extract_symptoms"},
            {"name": "ontology_mapper", "capability": "map_to_ontology"},
            {"name": "differential_assessor", "capability": "assess_differential"},
            {"name": "safety_verifier", "capability": "verify_safety"},
        ]

    async def _select_worker(self, task: str) -> Optional[Dict]:
        task_lower = task.lower()
        for w in self.workers:
            if w["capability"] in task_lower:
                return w
        return self.workers[0] if self.workers else None

    async def delegate(self, task: str, context: Dict) -> Dict:
        worker = await self._select_worker(task)
        if not worker:
            return {"task": task, "worker_results": [], "status": "no_worker_found"}

        results = []
        capability = worker["capability"]
        if capability == "extract_symptoms" and self.llm:
            symptoms = await self.llm.extract_symptoms(context.get("patient_note", ""))
            results = symptoms if symptoms else []
        elif capability == "map_to_ontology" and self.verifier:
            from core.verification_layer import lookup_all_by_symptoms
            symptoms = context.get("extracted_symptoms", [])
            symptom_terms = [s["term"] if isinstance(s, dict) else s for s in symptoms]
            mapping = lookup_all_by_symptoms(symptom_terms)
            results = [{"symptom": s, "edges": mapping.get(s, [])} for s in symptom_terms]
        elif capability == "assess_differential" and self.llm:
            diff = await self.llm.assess_differential(
                context.get("patient_note", ""),
                context.get("ontology_mappings", {}),
            )
            results = diff if diff else []
        elif capability == "verify_safety" and self.symbolic:
            proposed = context.get("proposed_path", [])
            result = self.symbolic.validate(proposed, context.get("patient_context", {}))
            results = [result] if result else []
        else:
            logger.info(f"Worker {worker['name']} has no handler for {task}")

        return {
            "task": task,
            "worker": worker["name"],
            "worker_results": results,
            "status": "completed",
        }
