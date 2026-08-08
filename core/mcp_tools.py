import logging
import os
from typing import Dict

logger = logging.getLogger(__name__)


async def tool_query_ehr(arguments: Dict) -> Dict:
    """Query EHR for patient data via FHIR."""
    patient_id = arguments.get("patient_id")
    resource_type = arguments.get("resource_type", "Patient")

    # Mock implementation — R5 would integrate real FHIR client
    return {
        "patient_id": patient_id,
        "resource_type": resource_type,
        "data": {
            "name": "Mock Patient",
            "age": 65,
            "gender": "male",
            "conditions": ["Hypertension", "Diabetes Mellitus"],
            "medications": ["Metformin", "Lisinopril"],
        },
        "source": "mock_fhir_server",
    }


async def tool_order_lab(arguments: Dict) -> Dict:
    """Order a lab test. Admin-only tool."""
    test_code = arguments.get("test_code")
    patient_id = arguments.get("patient_id")
    urgency = arguments.get("urgency", "routine")

    # Mock implementation
    return {
        "order_id": f"LAB-{os.urandom(4).hex().upper()}",
        "patient_id": patient_id,
        "test_code": test_code,
        "urgency": urgency,
        "status": "ordered",
        "estimated_turnaround_hours": 24 if urgency == "routine" else 2,
    }


async def tool_check_drug_interaction(arguments: Dict) -> Dict:
    """Check drug-drug or drug-condition interactions."""
    drug_a = arguments.get("drug_a")
    drug_b = arguments.get("drug_b")

    # Use existing SymbolicVerifier knowledge
    from core.verification_layer import SymbolicVerifier
    verifier = SymbolicVerifier()

    # Check if pair is in drug interactions
    key = (drug_a, drug_b)
    reverse_key = (drug_b, drug_a)

    interaction = None
    if key in verifier.drug_interactions:
        interaction = verifier.drug_interactions[key]
    elif reverse_key in verifier.drug_interactions:
        interaction = verifier.drug_interactions[reverse_key]

    if interaction:
        return {
            "drug_a": drug_a,
            "drug_b": drug_b,
            "interaction_found": True,
            "severity": interaction.get("severity", "major"),
            "reason": interaction.get("reason", "Unknown interaction"),
        }

    return {
        "drug_a": drug_a,
        "drug_b": drug_b,
        "interaction_found": False,
        "severity": None,
        "reason": "No known interaction in current rule set",
    }


async def tool_retrieve_literature(arguments: Dict) -> Dict:
    """Retrieve clinical literature (mock PubMed search)."""
    query = arguments.get("query")
    max_results = arguments.get("max_results", 5)

    # Mock implementation
    return {
        "query": query,
        "results": [
            {
                "pmid": f"1234567{i}",
                "title": f"Mock study about {query} #{i+1}",
                "abstract": f"This study examines {query} in clinical populations...",
                "year": 2023 - i,
            }
            for i in range(min(max_results, 3))
        ],
        "source": "mock_pubmed",
    }


def register_all_clinical_tools(registry, cb_factory=None):
    """Register all clinical tools with the MCP registry."""
    from core.mcp_protocol import ToolSchema, PermissionLevel

    registry.register(
        ToolSchema(
            name="query_ehr",
            description="Query electronic health record for patient data (FHIR)",
            input_schema={
                "type": "object",
                "properties": {
                    "patient_id": {"type": "string"},
                    "resource_type": {"type": "string", "enum": ["Patient", "Observation", "Condition", "MedicationRequest"]},
                },
                "required": ["patient_id"],
            },
            required_permission=PermissionLevel.CLINICIAN,
            capabilities=["ehr", "fhir", "read"],
        ),
        tool_query_ehr,
    )

    registry.register(
        ToolSchema(
            name="order_lab",
            description="Order a laboratory test for a patient",
            input_schema={
                "type": "object",
                "properties": {
                    "patient_id": {"type": "string"},
                    "test_code": {"type": "string"},
                    "urgency": {"type": "string", "enum": ["routine", "urgent", "stat"]},
                },
                "required": ["patient_id", "test_code"],
            },
            required_permission=PermissionLevel.ADMIN,
            timeout_seconds=30.0,
            capabilities=["lab", "order", "write"],
        ),
        tool_order_lab,
    )

    registry.register(
        ToolSchema(
            name="check_drug_interaction",
            description="Check for drug-drug or drug-condition interactions",
            input_schema={
                "type": "object",
                "properties": {
                    "drug_a": {"type": "string"},
                    "drug_b": {"type": "string"},
                },
                "required": ["drug_a", "drug_b"],
            },
            required_permission=PermissionLevel.CLINICIAN,
            capabilities=["drug", "safety", "read"],
        ),
        tool_check_drug_interaction,
    )

    registry.register(
        ToolSchema(
            name="retrieve_literature",
            description="Search clinical literature for evidence",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "max_results": {"type": "integer", "maximum": 20},
                },
                "required": ["query"],
            },
            required_permission=PermissionLevel.CLINICIAN,
            capabilities=["literature", "evidence", "read"],
        ),
        tool_retrieve_literature,
    )

    logger.info("All clinical tools registered with MCP")
