from functools import lru_cache
from core.verification_layer import Neo4jVerifier, SymbolicVerifier, OPAClient
from core.llm_backend import MockLLMBackend, OllamaBackend, DeepSeekR1Backend, MedGemmaBackend
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

def get_llm_backend(backend_type: str = None):
    mode = backend_type or os.getenv("RUNTIME_LLM") or os.getenv("LLM_BACKEND", "mock")
    if mode == "ollama":
        return OllamaBackend(
            model=os.getenv("LLM_MODEL", "gemma2:2b"),
            host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
        )
    elif mode == "deepseek_r1":
        return DeepSeekR1Backend(
            base_url=os.getenv("VLLM_URL", "http://localhost:8000/v1"),
            model=os.getenv("VLLM_MODEL", "deepseek-ai/deepseek-r1-distill-qwen-32b"),
        )
    elif mode == "medgemma_4b_it":
        return MedGemmaBackend(
            base_url=os.getenv("VLLM_URL", "http://localhost:8000/v1"),
            model=os.getenv("VLLM_MODEL", "google/MedGemma-4B-IT"),
        )
    return MockLLMBackend()
