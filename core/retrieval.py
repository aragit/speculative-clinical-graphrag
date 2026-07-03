from typing import Dict, List, Optional
import logging
import os

logger = logging.getLogger(__name__)


class HybridRetriever:
    def __init__(self, qdrant_host: str = None, neo4j_verifier=None, embed_model: str = "all-MiniLM-L6-v2"):
        self.qdrant_host = qdrant_host or os.getenv("QDRANT_HOST", "http://localhost:6333")
        self.neo4j = neo4j_verifier
        self.embed_model_name = embed_model
        self._encoder = None
        self._qdrant_client = None

    def _get_encoder(self):
        if self._encoder is None:
            from sentence_transformers import SentenceTransformer
            self._encoder = SentenceTransformer(self.embed_model_name)
        return self._encoder

    def _get_qdrant(self):
        if self._qdrant_client is None:
            from qdrant_client import QdrantClient
            self._qdrant_client = QdrantClient(url=self.qdrant_host)
        return self._qdrant_client

    async def _embed(self, text: str) -> List[float]:
        enc = self._get_encoder()
        return enc.encode(text).tolist()

    async def _vector_search(self, query: str, collection: str = "clinical_ontology", top_k: int = 10) -> List[Dict]:
        try:
            client = self._get_qdrant()
            query_vec = await self._embed(query)
            results = client.search(
                collection_name=collection,
                query_vector=query_vec,
                limit=top_k,
            )
            return [
                {"id": r.id, "score": r.score, "payload": r.payload}
                for r in results
            ]
        except Exception as e:
            logger.warning(f"Qdrant search failed: {e}")
            return []

    async def _graph_search(self, query: str) -> List[Dict]:
        from core.verification_layer import lookup_edges
        results = lookup_edges(query)
        if results:
            return results
        try:
            from neo4j import GraphDatabase
            uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
            auth = (os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "speculative123"))
            driver = GraphDatabase.driver(uri, auth=auth)
            with driver.session() as session:
                result = session.run("""
                    MATCH (h:Concept)-[r:RELATION]->(t:Concept)
                    WHERE h.label CONTAINS $query OR t.label CONTAINS $query
                    RETURN h.label AS head, r.type AS relation, t.label AS tail
                    LIMIT 20
                """, query=query)
                edges = [{"head": r["head"], "relation": r["relation"], "tail": r["tail"]} for r in result]
            driver.close()
            return edges
        except Exception as e:
            logger.warning(f"Neo4j graph search failed: {e}")
            return []

    @staticmethod
    def _fusion_score(vector_score: float, graph_score: float, alpha: float = 0.7) -> float:
        return alpha * vector_score + (1 - alpha) * graph_score

    async def retrieve(self, query: str, proposed_path: Optional[List[Dict]] = None) -> Dict:
        vector_results = await self._vector_search(query)
        graph_results = await self._graph_search(query)

        merged_context_parts = []
        if vector_results:
            for r in vector_results[:3]:
                payload = r.get("payload") or {}
                label = payload.get("label", payload.get("id", r.get("id", "unknown")))
                merged_context_parts.append(f"[vector:{r['score']:.2f}] {label}")
        if graph_results:
            for e in graph_results[:5]:
                merged_context_parts.append(f"[graph] {e['head']} -[{e['relation']}]-> {e['tail']}")

        return {
            "vector_results": vector_results,
            "graph_results": graph_results,
            "merged_context": "\n".join(merged_context_parts) if merged_context_parts else "",
        }
