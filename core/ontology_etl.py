from typing import Dict
import logging
logger = logging.getLogger(__name__)

class OntologyETL:
    """Stub: automated ETL for SNOMED-CT/ICD-10-CM/RxNorm/UMLS."""
    def __init__(self, neo4j_verifier=None):
        self.neo4j = neo4j_verifier

    async def ingest_snomed_ct(self, rf2_path: str) -> Dict:
        logger.warning("MOCK_MODE: SNOMED-CT ETL not implemented. Use seed_mock_ontology().")
        return {"status": "not_implemented", "concepts": 0}

    async def ingest_icd10_cm(self, txt_path: str) -> Dict:
        return {"status": "not_implemented", "concepts": 0}

    async def ingest_rxnorm(self, rrf_path: str) -> Dict:
        return {"status": "not_implemented", "concepts": 0}

    async def ingest_umls(self, mrconso_path: str, mrrel_path: str) -> Dict:
        return {"status": "not_implemented", "concepts": 0}

    def create_mock_ontology(self, scale: int = 100) -> None:
        if self.neo4j:
            self.neo4j.seed_mock_ontology(scale=scale)
