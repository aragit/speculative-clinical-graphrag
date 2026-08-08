package clinical.tool_execution

default allow := false

# Clinicians can use read-only tools
allow {
    input.tool == "query_ehr"
    input.payload.caller_role == "clinician"
}

allow {
    input.tool == "check_drug_interaction"
    input.payload.caller_role == "clinician"
}

allow {
    input.tool == "retrieve_literature"
    input.payload.caller_role == "clinician"
}

# Only admins can order labs
allow {
    input.tool == "order_lab"
    input.payload.caller_role == "admin"
}

# System agents can use read tools
allow {
    input.tool == "query_ehr"
    input.payload.caller_role == "system"
}

allow {
    input.tool == "check_drug_interaction"
    input.payload.caller_role == "system"
}

allow {
    input.tool == "retrieve_literature"
    input.payload.caller_role == "system"
}

# System agents can also order labs (internal scheduling)
allow {
    input.tool == "order_lab"
    input.payload.caller_role == "system"
}
