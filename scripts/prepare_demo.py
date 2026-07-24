#!/usr/bin/env python3
"""
E2E Demo Preparation Script
============================
Checks Docker services, seeds Neo4j + Qdrant + OPA, and confirms readiness.

Usage:
    python scripts/prepare_demo.py
"""

import sys
import os
import json
import time
import httpx

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "speculative123")
QDRANT_HOST = os.getenv("QDRANT_HOST", "http://localhost:6333")
OPA_URL = os.getenv("OPA_URL", "http://localhost:8181")
OPA_POLICY_PATH = os.path.join(os.path.dirname(__file__), "..", "infra", "opa", "policies", "clinical.rego")


class Status:
    def __init__(self):
        self.results = {}

    def check(self, name: str, ok: bool, detail: str = ""):
        icon = "  OK" if ok else "FAIL"
        self.results[name] = ok
        suffix = f"  ({detail})" if detail else ""
        print(f"  [{icon}] {name}{suffix}")
        return ok

    def summary(self):
        all_ok = all(self.results.values())
        print()
        if all_ok:
            print("=" * 60)
            print("  FULL E2E REAL INFRASTRUCTURE READY")
            print("=" * 60)
            print()
            print("  Start the backend:  python -m uvicorn api.main:app --port 8001")
            print("  Start the frontend: cd frontend && npm run dev")
            print()
        else:
            failed = [k for k, v in self.results.items() if not v]
            print("=" * 60)
            print(f"  BLOCKED — {len(failed)} service(s) unavailable:")
            for f in failed:
                print(f"    - {f}")
            print("=" * 60)
            print()
            print("  Run: docker-compose up -d")
            print()
        return all_ok


def check_neo4j(status: Status):
    try:
        from neo4j import GraphDatabase
        d = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        with d.session() as s:
            result = s.run("RETURN 1 AS n")
            result.single()
        d.close()
        return status.check("Neo4j", True, NEO4J_URI)
    except Exception as e:
        return status.check("Neo4j", False, str(e)[:80])


def check_qdrant(status: Status):
    try:
        r = httpx.get(f"{QDRANT_HOST}/", timeout=5.0)
        ok = r.status_code < 500
        return status.check("Qdrant", ok, f"HTTP {r.status_code}")
    except Exception as e:
        return status.check("Qdrant", False, str(e)[:80])


def check_opa(status: Status):
    try:
        r = httpx.get(f"{OPA_URL.rstrip('/v1/data/clinical')}/health", timeout=5.0)
        ok = r.status_code < 500
        return status.check("OPA", ok, f"HTTP {r.status_code}")
    except Exception as e:
        return status.check("OPA", False, str(e)[:80])


def seed_neo4j(status: Status):
    try:
        from core.verification_layer import Neo4jVerifier
        v = Neo4jVerifier()
        v.seed_mock_ontology()
        v.close()
        return status.check("Neo4j Seed", True, "126 concepts, 178 edges")
    except Exception as e:
        return status.check("Neo4j Seed", False, str(e)[:80])


def seed_qdrant(status: Status):
    try:
        from core.ontology_etl import OntologyETL
        from core.verification_layer import ALL_CONCEPTS
        etl = OntologyETL()
        import asyncio
        result = asyncio.run(etl.embed_and_index(ALL_CONCEPTS))
        count = result.get("indexed", len(ALL_CONCEPTS))
        return status.check("Qdrant Embed", True, f"{count} concepts indexed (CPU)")
    except Exception as e:
        return status.check("Qdrant Embed", False, str(e)[:80])


def seed_opa(status: Status):
    try:
        if not os.path.exists(OPA_POLICY_PATH):
            return status.check("OPA Policy", False, f"File not found: {OPA_POLICY_PATH}")

        with open(OPA_POLICY_PATH, "r") as f:
            rego_code = f.read()

        opa_base = OPA_URL.rstrip("/v1/data/clinical")
        put_url = f"{opa_base}/v1/policies/clinical_safety"

        r = httpx.put(
            put_url,
            content=rego_code,
            headers={"Content-Type": "text/plain"},
            timeout=10.0,
        )
        ok = r.status_code < 400
        return status.check("OPA Policy Upload", ok, f"HTTP {r.status_code}")
    except Exception as e:
        return status.check("OPA Policy Upload", False, str(e)[:80])


def check_ollama(status: Status):
    try:
        host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        r = httpx.get(f"{host}/api/tags", timeout=5.0)
        if r.status_code == 200:
            models = r.json().get("models", [])
            names = [m.get("name", "") for m in models]
            return status.check("Ollama", True, f"{len(models)} models: {', '.join(names[:3])}")
        return status.check("Ollama", False, f"HTTP {r.status_code}")
    except Exception as e:
        return status.check("Ollama", False, "not running (mock mode will be used)")


def check_embedding_model(status: Status):
    try:
        from sentence_transformers import SentenceTransformer
        model_name = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        device = os.getenv("EMBEDDING_DEVICE", "cpu")
        m = SentenceTransformer(model_name, device=device)
        vec = m.encode("test")
        return status.check("Embedding Model", True, f"{model_name} on {device} (dim={len(vec)})")
    except Exception as e:
        return status.check("Embedding Model", False, str(e)[:80])


def main():
    print()
    print("=" * 60)
    print("  Speculative Clinical GraphRAG — E2E Demo Preparation")
    print("=" * 60)
    print()

    status = Status()

    print("Phase 1: Infrastructure Connectivity")
    print("-" * 40)
    neo_ok = check_neo4j(status)
    qdrant_ok = check_qdrant(status)
    opa_ok = check_opa(status)
    ollama_ok = check_ollama(status)
    embed_ok = check_embedding_model(status)

    print()
    print("Phase 2: Data Seeding")
    print("-" * 40)
    if neo_ok:
        seed_neo4j(status)
    else:
        status.check("Neo4j Seed", False, "skipped (Neo4j unavailable)")

    if qdrant_ok:
        seed_qdrant(status)
    else:
        status.check("Qdrant Embed", False, "skipped (Qdrant unavailable)")

    if opa_ok:
        seed_opa(status)
    else:
        status.check("OPA Policy Upload", False, "skipped (OPA unavailable)")

    status.summary()
    return 0 if all(status.results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
