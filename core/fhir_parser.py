from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class FHIRParser:
    """Parse FHIR R4 resources into patient context fields."""

    @staticmethod
    def parse_bundle(bundle: Dict) -> Dict:
        """Parse a FHIR Bundle containing Patient, Observations, Conditions, etc."""
        context = {}
        entries = bundle.get("entry", [])
        for entry in entries:
            resource = entry.get("resource", {})
            resource_type = resource.get("resourceType")
            if resource_type == "Patient":
                context.update(FHIRParser._parse_patient(resource))
            elif resource_type == "Observation":
                obs = FHIRParser._parse_observation(resource)
                if "observations" not in context:
                    context["observations"] = []
                context["observations"].append(obs)
            elif resource_type == "MedicationRequest":
                meds = FHIRParser._parse_medication_request(resource)
                if "medications" not in context:
                    context["medications"] = []
                context["medications"].append(meds)
            elif resource_type == "Condition":
                conds = FHIRParser._parse_condition(resource)
                if "conditions" not in context:
                    context["conditions"] = []
                context["conditions"].append(conds)
            elif resource_type == "AllergyIntolerance":
                allergies = FHIRParser._parse_allergy(resource)
                if "allergies" not in context:
                    context["allergies"] = []
                context["allergies"].append(allergies)
        return context

    @staticmethod
    def _parse_patient(resource: Dict) -> Dict:
        result = {}
        if "birthDate" in resource:
            from datetime import datetime, timezone
            try:
                birth = datetime.strptime(resource["birthDate"], "%Y-%m-%d")
                result["age"] = int((datetime.now(timezone.utc).replace(tzinfo=None) - birth).days / 365.25)
            except ValueError:
                pass
        if "gender" in resource:
            result["gender"] = resource["gender"]
        return result

    @staticmethod
    def _parse_observation(resource: Dict) -> Dict:
        code = resource.get("code", {}).get("text", "Unknown")
        value = resource.get("valueQuantity", {}).get("value")
        unit = resource.get("valueQuantity", {}).get("unit")
        return {
            "code": code,
            "value": value,
            "unit": unit,
            "status": resource.get("status"),
        }

    @staticmethod
    def _parse_medication_request(resource: Dict) -> Dict:
        med = resource.get("medicationCodeableConcept", {}).get("text", "Unknown")
        return {
            "medication": med,
            "status": resource.get("status"),
            "intent": resource.get("intent"),
        }

    @staticmethod
    def _parse_condition(resource: Dict) -> Dict:
        code = resource.get("code", {}).get("text", "Unknown")
        return {
            "condition": code,
            "clinical_status": resource.get("clinicalStatus", {}).get("text"),
            "verification_status": resource.get("verificationStatus", {}).get("text"),
        }

    @staticmethod
    def _parse_allergy(resource: Dict) -> Dict:
        code = resource.get("code", {}).get("text", "Unknown")
        return {
            "allergen": code,
            "clinical_status": resource.get("clinicalStatus"),
            "verification_status": resource.get("verificationStatus"),
        }

    @classmethod
    def extract_from_context(cls, patient_context: Dict) -> Dict:
        """Try to parse FHIR from patient_context, or return empty if not FHIR."""
        if not patient_context:
            return {}
        if patient_context.get("resourceType") == "Bundle":
            return cls.parse_bundle(patient_context)
        if "resourceType" in patient_context:
            bundle = {"entry": [{"resource": patient_context}]}
            return cls.parse_bundle(bundle)
        return {}
