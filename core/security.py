import re
import json
import time
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

_PII_PATTERNS = [
    (r'\b\d{3}-\d{2}-\d{4}\b', '[SSN_REDACTED]'),
    (r'\b\d{3}-\d{3}-\d{4}\b', '[PHONE_REDACTED]'),
    (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL_REDACTED]'),
    (r'\b\d{1,2}/\d{1,2}/\d{2,4}\b', '[DOB_REDACTED]'),
    (r'\b\d{2,4}-\d{1,2}-\d{1,2}\b', '[DOB_REDACTED]'),
    (r'MRN[:\s]*\d+', '[MRN_REDACTED]'),
    (r'Patient ID[:\s]*\w+', '[PATIENT_ID_REDACTED]'),
]

_INJECTION_PATTERNS = [
    r'ignore previous instructions',
    r'ignore all (?:prior|previous) (?:instructions|rules)',
    r'you are now (?:an?|in) ',
    r'system prompt',
    r'<!--',
    r'\{\{.*\}\}',
    r'<\|.*\|>',
    r'### (?:system|assistant|user)',
    r'new (?:role|persona)',
]


class InputSanitizer:
    """Sanitize clinical inputs: PII redaction + prompt injection filtering."""

    def __init__(self, redact_pii: bool = True, block_injection: bool = True):
        self.redact_pii = redact_pii
        self.block_injection = block_injection

    def sanitize_patient_note(self, note: str) -> str:
        """Redact PII from patient notes before LLM processing."""
        if not self.redact_pii:
            return note

        sanitized = note
        for pattern, replacement in _PII_PATTERNS:
            sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)

        if sanitized != note:
            logger.info("PII redaction applied to patient note")

        return sanitized

    def check_prompt_injection(self, text: str) -> Dict:
        """Check for prompt injection attempts. Returns {safe: bool, violations: list}."""
        if not self.block_injection:
            return {"safe": True, "violations": []}

        violations = []
        text_lower = text.lower()
        for pattern in _INJECTION_PATTERNS:
            if re.search(pattern, text_lower):
                violations.append(f"Potential prompt injection pattern: {pattern}")

        special_ratio = sum(1 for c in text if not c.isalnum() and not c.isspace()) / max(len(text), 1)
        if special_ratio > 0.3 and len(text) > 200:
            violations.append("High special character ratio - possible encoding attack")

        return {
            "safe": len(violations) == 0,
            "violations": violations,
        }

    def sanitize_context(self, context: Optional[Dict]) -> Dict:
        """Recursively sanitize string values in patient_context dict."""
        if context is None:
            return {}

        sanitized = {}
        for key, value in context.items():
            if isinstance(value, str):
                sanitized[key] = self.sanitize_patient_note(value)
            elif isinstance(value, dict):
                sanitized[key] = self.sanitize_context(value)
            elif isinstance(value, list):
                sanitized[key] = [
                    self.sanitize_patient_note(v) if isinstance(v, str) else v
                    for v in value
                ]
            else:
                sanitized[key] = value

        return sanitized


class AuditLogger:
    """Structured audit logging for clinical safety compliance."""

    def __init__(self, request_id: Optional[str] = None):
        self.request_id = request_id

    def log_decision(self, trace_id: str, decision: str, reasoning: str, patient_hash: str):
        """Log a clinical decision with non-PII identifiers."""
        logger.info(json.dumps({
            "event": "clinical_decision",
            "trace_id": trace_id,
            "request_id": self.request_id,
            "decision": decision,
            "reasoning_summary": reasoning[:200],
            "patient_hash": patient_hash,
            "timestamp": time.time(),
        }))

    def log_override(self, trace_id: str, clinician_action: str, notes: str):
        """Log clinician override for audit trail."""
        logger.info(json.dumps({
            "event": "clinician_override",
            "trace_id": trace_id,
            "request_id": self.request_id,
            "action": clinician_action,
            "timestamp": time.time(),
        }))

    def log_safety_violation(self, trace_id: str, violation_type: str, details: str):
        """Log safety layer violations."""
        logger.warning(json.dumps({
            "event": "safety_violation",
            "trace_id": trace_id,
            "request_id": self.request_id,
            "violation_type": violation_type,
            "details": details,
            "timestamp": time.time(),
        }))
