from typing import Dict, List, Tuple
import logging
import os

logger = logging.getLogger(__name__)


class OntologyETL:
    def __init__(self, neo4j_verifier=None, qdrant_host: str = None):
        self.neo4j = neo4j_verifier
        self.qdrant_host = qdrant_host or os.getenv("QDRANT_HOST", "http://localhost:6333")

    async def _get_encoder(self):
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer("all-MiniLM-L6-v2")

    async def _get_qdrant(self):
        from qdrant_client import QdrantClient
        return QdrantClient(url=self.qdrant_host)

    async def _ensure_collection(self, collection: str = "clinical_ontology"):
        from qdrant_client.models import VectorParams, Distance
        client = await self._get_qdrant()
        collections = [c.name for c in client.get_collections().collections]
        if collection not in collections:
            client.create_collection(
                collection_name=collection,
                vectors_config=VectorParams(size=384, distance=Distance.COSINE),
            )
            logger.info(f"Created Qdrant collection '{collection}'")
        return client

    async def embed_and_index(self, concepts: List[Tuple[str, str, str]], collection: str = "clinical_ontology") -> Dict:
        import uuid
        encoder = await self._get_encoder()
        client = await self._ensure_collection(collection)
        from qdrant_client.models import PointStruct

        points = []
        for label, cui, tag in concepts:
            text = f"{label} ({tag})"
            vec = encoder.encode(text).tolist()
            points.append(PointStruct(
                id=str(uuid.uuid5(uuid.NAMESPACE_DNS, cui)),
                vector=vec,
                payload={"label": label, "cui": cui, "semantic_tag": tag, "text": text},
            ))

        if points:
            client.upsert(collection_name=collection, points=points)
        logger.info(f"Indexed {len(points)} concepts into Qdrant '{collection}'")
        return {"status": "ok", "concepts": len(points)}

    async def ingest_snomed_ct(self, rf2_path: str) -> Dict:
        import csv
        concepts = []
        concept_file = os.path.join(rf2_path, "Snapshot", "Terminology", "sct2_Concept_Snapshot_INT_20240101.txt")
        desc_file = os.path.join(rf2_path, "Snapshot", "Terminology", "sct2_Description_Snapshot-en_INT_20240101.txt")
        if not os.path.exists(concept_file):
            logger.warning(f"SNOMED RF2 not found at {concept_file}. Use license + download.")
            return {"status": "not_implemented", "concepts": 0, "note": "Download SNOMED-CT from MLDS"}
        desc_map = {}
        with open(desc_file, "r") as f:
            reader = csv.reader(f, delimiter="\t")
            next(reader)
            for row in reader:
                desc_map[row[4]] = row[7]
        with open(concept_file, "r") as f:
            reader = csv.reader(f, delimiter="\t")
            next(reader)
            for row in reader:
                cui = row[0]
                active = row[2]
                definition_status = row[6]
                if active == "1" and definition_status == "900000000000073002":
                    label = desc_map.get(cui, "unknown")
                    concepts.append((label, cui, "snomed-concept"))
        result = await self.embed_and_index(concepts)
        if self.neo4j:
            self.neo4j.seed_mock_ontology(scale=len(concepts))
        return result

    async def ingest_icd10_cm(self, txt_path: str) -> Dict:
        import csv
        concepts = []
        if not os.path.exists(txt_path):
            return {"status": "not_implemented", "concepts": 0, "note": "Download ICD-10-CM from NCHS"}
        with open(txt_path, "r") as f:
            reader = csv.reader(f, delimiter="\t")
            for row in reader:
                if len(row) >= 2:
                    concepts.append((row[1], row[0], "icd10cm"))
        result = await self.embed_and_index(concepts)
        return result

    async def ingest_rxnorm(self, rrf_path: str) -> Dict:
        concepts = []
        if not os.path.exists(rrf_path):
            return {"status": "not_implemented", "concepts": 0}
        import csv
        with open(rrf_path, "r") as f:
            reader = csv.reader(f, delimiter="|")
            for row in reader:
                if len(row) >= 15 and row[11] == "ENG":
                    concepts.append((row[14], row[0], "rxnorm"))
        result = await self.embed_and_index(concepts)
        return result

    async def ingest_umls(self, mrconso_path: str, mrrel_path: str) -> Dict:
        return await self.ingest_snomed_ct(mrconso_path)

    def create_mock_ontology(self, scale: int = 100) -> None:
        if self.neo4j:
            self.neo4j.seed_mock_ontology(scale=scale)
