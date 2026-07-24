from typing import Dict, List, Optional
import logging
import os

logger = logging.getLogger(__name__)


class HybridRetriever:
    def __init__(self, qdrant_host: str = None, neo4j_verifier=None, embed_model: str = None):
        self.qdrant_host = qdrant_host or os.getenv("QDRANT_HOST", "http://localhost:6333")
        self.neo4j = neo4j_verifier
        self.embed_model_name = embed_model or os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        self.embed_device = os.getenv("EMBEDDING_DEVICE", "cpu")
        self._encoder = None
        self._qdrant_client = None

    def _get_encoder(self):
        if self._encoder is None:
            from sentence_transformers import SentenceTransformer
            self._encoder = SentenceTransformer(self.embed_model_name, device=self.embed_device)
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
                    WHERE h.label CONTAINS $search_term OR t.label CONTAINS $search_term
                    RETURN h.label AS head, r.type AS relation, t.label AS tail
                    LIMIT 20
                """, search_term=query)
                edges = [{"head": r["head"], "relation": r["relation"], "tail": r["tail"]} for r in result]
            driver.close()
            return edges
        except Exception as e:
            logger.warning(f"Neo4j graph search failed: {e}")
            return []

    @staticmethod
    def _fusion_score(vector_score: float, graph_score: float, alpha: float = 0.7) -> float:
        return alpha * vector_score + (1 - alpha) * graph_score

    async def _build_concept_map(self, graph_results: List[Dict]) -> Dict[str, List[Dict]]:
        concept_map: Dict[str, List[Dict]] = {}
        for e in graph_results:
            head = e.get("head", "").lower()
            tail = e.get("tail", "").lower()
            if head not in concept_map:
                concept_map[head] = []
            concept_map[head].append(e)
            if tail not in concept_map:
                concept_map[tail] = []
            concept_map[tail].append(e)
        return concept_map

    async def retrieve(self, query: str, proposed_path: Optional[List[Dict]] = None) -> Dict:
        vector_results = await self._vector_search(query)
        graph_results = await self._graph_search(query)

        concept_map = await self._build_concept_map(graph_results)

        merged_context_parts = []
        fused_results = []
        seen_labels = set()

        if vector_results:
            for r in vector_results[:5]:
                payload = r.get("payload") or {}
                label = payload.get("label", "").lower()
                seen_labels.add(label)
                graph_matches = concept_map.get(label, [])
                graph_score = min(1.0, len(graph_matches) * 0.2)
                vector_score = r["score"]
                fusion = self._fusion_score(vector_score, graph_score)
                fused_results.append({
                    "source": "vector",
                    "label": payload.get("label", r.get("id", "unknown")),
                    "vector_score": round(vector_score, 3),
                    "graph_score": round(graph_score, 3),
                    "fusion_score": round(fusion, 3),
                    "graph_edges": graph_matches[:3],
                })
                merged_context_parts.append(f"[fusion:{fusion:.2f}] {payload.get('label', label)}")

        if graph_results:
            for e in graph_results[:5]:
                head = e.get("head", "")
                if head.lower() not in seen_labels:
                    merged_context_parts.append(f"[graph] {head} -[{e['relation']}]-> {e['tail']}")
                    fused_results.append({
                        "source": "graph",
                        "label": head,
                        "vector_score": 0.0,
                        "graph_score": 1.0,
                        "fusion_score": 0.7,
                        "graph_edges": [e],
                    })

        return {
            "vector_results": vector_results,
            "graph_results": graph_results,
            "fused_results": sorted(fused_results, key=lambda x: x["fusion_score"], reverse=True),
            "merged_context": "\n".join(merged_context_parts) if merged_context_parts else "",
        }
