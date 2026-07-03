package clinical

default allow := false

violation contains msg if {
    some path in input.proposed_path
    path.tail == "Warfarin"
    path.head == "Aspirin"
    msg := "Contraindication: Aspirin + Warfarin"
}

violation contains msg if {
    some path in input.proposed_path
    path.tail == "Warfarin"
    path.head == "Ibuprofen"
    msg := "Contraindication: NSAID + Warfarin"
}

violation contains msg if {
    some path in input.proposed_path
    path.head == "Metformin"
    path.tail == "Severe Renal Impairment"
    msg := "Contraindication: Metformin in eGFR <30"
}

allow if {
    count(violation) == 0
}
