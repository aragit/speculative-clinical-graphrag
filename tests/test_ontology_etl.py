import pytest
from core.ontology_etl import OntologyETL


@pytest.mark.asyncio
async def test_ingest_snomed_ct_not_found():
    etl = OntologyETL()
    result = await etl.ingest_snomed_ct("/nonexistent/rf2")
    assert result["status"] == "not_implemented"


@pytest.mark.asyncio
async def test_ingest_icd10_not_found():
    etl = OntologyETL()
    result = await etl.ingest_icd10_cm("/nonexistent/icd10.txt")
    assert result["status"] == "not_implemented"


@pytest.mark.asyncio
async def test_ingest_rxnorm_not_found():
    etl = OntologyETL()
    result = await etl.ingest_rxnorm("/nonexistent/rxnorm.rrf")
    assert result["status"] == "not_implemented"


def test_create_mock_ontology_noop_without_neo4j():
    etl = OntologyETL()
    etl.create_mock_ontology(scale=50)
    assert True
