from typing import Dict, Any, List, Optional
import logging
import json
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SpeculativePath(BaseModel):
    path_id: str
    nodes: List[str] = Field(description="Entities in the clinical chain (e.g., ['DrugA', 'CytochromeP450', 'DrugB'])")
    relations: List[str] = Field(description="Relationships between entities (e.g., ['inhibits', 'metabolizes'])")
    rationale: str = Field(description="Clinical justification for this speculative pathway")
    confidence_score: float = Field(ge=0.0, le=1.0)


class GraphReasonerAgent:
    """
    Speculative Clinical Graph Reasoner.
    Constructs candidate diagnostic or multi-drug interaction paths
    using the LLM backend prior to symbolic graph validation.
    """

    def __init__(self, llm_backend: Any):
        self.llm = llm_backend

    async def generate_paths(self, query: str, graph_context: Dict[str, Any]) -> List[SpeculativePath]:
        prompt = self._build_prompt(query, graph_context)

        try:
            if hasattr(self.llm, '_chat'):
                raw_response = await self.llm._chat(prompt)
            elif hasattr(self.llm, 'generate'):
                raw_response = self.llm.generate(prompt)
            else:
                raw_response = await self.llm.generate_path(query, graph_context)
                triplets = raw_response.get("triplets", [])
                return self._triplets_to_paths(triplets)
        except Exception as e:
            logger.warning(f"LLM call failed in GraphReasonerAgent: {e}")
            return []

        return self._parse_response(raw_response)

    def _triplets_to_paths(self, triplets: List[Dict]) -> List[SpeculativePath]:
        """Convert legacy triplet format to SpeculativePath objects."""
        paths = []
        for i, t in enumerate(triplets):
            paths.append(SpeculativePath(
                path_id=f"path_{i + 1}",
                nodes=[t.get("head", ""), t.get("tail", "")],
                relations=[t.get("relation", "INDICATES")],
                rationale=f"Auto-generated from triplet: {t.get('head')} {t.get('relation')} {t.get('tail')}",
                confidence_score=t.get("confidence", 0.5),
            ))
        return paths

    def _parse_response(self, raw_response: str) -> List[SpeculativePath]:
        """Parse LLM JSON response into SpeculativePath objects."""
        try:
            parsed = json.loads(raw_response)
            if isinstance(parsed, list):
                return [SpeculativePath(**p) for p in parsed if isinstance(p, dict)]
            if isinstance(parsed, dict) and "paths" in parsed:
                return [SpeculativePath(**p) for p in parsed["paths"] if isinstance(p, dict)]
            return []
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code blocks
            import re
            json_match = re.search(r'```(?:json)?\s*\n?(.*?)```', raw_response, re.DOTALL)
            if json_match:
                try:
                    parsed = json.loads(json_match.group(1))
                    if isinstance(parsed, list):
                        return [SpeculativePath(**p) for p in parsed if isinstance(p, dict)]
                except Exception:
                    pass
            logger.warning(f"Failed to parse speculative paths from LLM response: {raw_response[:200]}")
            return []
        except Exception as e:
            logger.warning(f"Failed to parse speculative paths: {e}")
            return []

    def _build_prompt(self, query: str, graph_context: Dict[str, Any]) -> str:
        ctx_str = json.dumps(graph_context, indent=2, default=str) if graph_context else "{}"
        return f"""You are a specialized clinical reasoning agent. Analyze the patient query and retrieved sub-graph context.
Propose speculative clinical paths (multi-drug interactions, contraindications, or treatment pathways).

Query: {query}
Retrieved Graph Context: {ctx_str}

Output a JSON array matching this format:
[
  {{
    "path_id": "path_1",
    "nodes": ["Drug_A", "Target_X", "Symptom_Y"],
    "relations": ["targets", "causes"],
    "rationale": "Clinical explanation...",
    "confidence_score": 0.88
  }}
]

Output JSON array only, no additional text."""

    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """LangGraph-compatible callable interface."""
        logger.info(f"[{state.get('trace_id')}] Running Graph Reasoner Agent...")
        query = state.get("query", state.get("patient_note", ""))
        context = state.get("retrieved_context", state.get("retrieval_context", {}))

        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Already in an async context, create a task
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, self.generate_paths(query, context))
                    speculative_paths = future.result(timeout=30)
            else:
                speculative_paths = loop.run_until_complete(self.generate_paths(query, context))
        except RuntimeError:
            speculative_paths = asyncio.run(self.generate_paths(query, context))

        return {
            "speculative_paths": [p.model_dump() for p in speculative_paths],
            "status": "speculative_reasoning_complete",
        }

    async def __acall__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Async LangGraph-compatible callable interface."""
        logger.info(f"[{state.get('trace_id')}] Running Graph Reasoner Agent...")
        query = state.get("query", state.get("patient_note", ""))
        context = state.get("retrieved_context", state.get("retrieval_context", {}))

        speculative_paths = await self.generate_paths(query, context)

        return {
            "speculative_paths": [p.model_dump() for p in speculative_paths],
            "status": "speculative_reasoning_complete",
        }
