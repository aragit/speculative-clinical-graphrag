from functools import lru_cache
from core.verification_layer import Neo4jVerifier, SymbolicVerifier, OPAClient
from core.llm_backend import MockLLMBackend, OllamaBackend, DeepSeekR1Backend, MedGemmaBackend
from core.cogitator import COGITATORBackend
from core.backend_router import BackendRouter
import os

@lru_cache
def get_neo4j_verifier() -> Neo4jVerifier:
    return Neo4jVerifier()

@lru_cache
def get_symbolic_verifier() -> SymbolicVerifier:
    return SymbolicVerifier()

@lru_cache
def get_opa_client() -> OPAClient:
    return OPAClient()

def get_llm_router() -> BackendRouter:
    """Construct a router with all available backends."""
    backends = {}
    backends["mock"] = MockLLMBackend()
    if os.getenv("OLLAMA_HOST") or os.getenv("RUNTIME_LLM") == "ollama":
        backends["ollama"] = OllamaBackend(
            model=os.getenv("LLM_MODEL", "gemma2:2b"),
            host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
        )
    if os.getenv("VLLM_URL") or os.getenv("RUNTIME_LLM") in ("deepseek_r1", "medgemma_4b_it"):
        backends["deepseek_r1"] = DeepSeekR1Backend(
            base_url=os.getenv("VLLM_URL", "http://localhost:8000/v1"),
            model=os.getenv("VLLM_MODEL", "deepseek-ai/deepseek-r1-distill-qwen-32b"),
        )
        backends["medgemma_4b_it"] = MedGemmaBackend(
            base_url=os.getenv("VLLM_URL", "http://localhost:8000/v1"),
            model=os.getenv("VLLM_MODEL", "google/MedGemma-4B-IT"),
        )

    # COGITATOR wrapper (wraps default backend)
    cogitator_base = os.getenv("COGITATOR_BASE", "mock")
    base = backends.get(cogitator_base, MockLLMBackend())
    backends["cogitator"] = COGITATORBackend(base_backend=base)

    default = os.getenv("RUNTIME_LLM", "mock")
    return BackendRouter(backends, default=default)

def get_llm_backend(backend_type: str = None):
    return get_llm_router().get_backend(backend_type)
