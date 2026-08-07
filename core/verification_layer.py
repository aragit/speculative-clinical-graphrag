from typing import List, Dict, Optional
from neo4j import GraphDatabase
import os
import logging
import asyncio
import yaml
from core.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError

logger = logging.getLogger(__name__)

_SYMPTOMS = [
    ("Dyspnea", "C0013404", "finding"),
    ("Orthopnea", "C0029124", "finding"),
    ("Chest Pain", "C0008031", "finding"),
    ("Fatigue", "C0015672", "finding"),
    ("Edema", "C0013604", "finding"),
    ("Palpitations", "C0030252", "finding"),
    ("Cough", "C0010200", "finding"),
    ("Wheeze", "C0043142", "finding"),
    ("Fever", "C0015967", "finding"),
    ("Chills", "C0085593", "finding"),
    ("Nausea", "C0027497", "finding"),
    ("Vomiting", "C0042963", "finding"),
    ("Diarrhea", "C0011991", "finding"),
    ("Constipation", "C0009806", "finding"),
    ("Headache", "C0018681", "finding"),
    ("Dizziness", "C0012833", "finding"),
    ("Confusion", "C0009676", "finding"),
    ("Syncope", "C0039070", "finding"),
    ("Jaundice", "C0022346", "finding"),
    ("Hematuria", "C0478113", "finding"),
    ("Hemoptysis", "C0019079", "finding"),
    ("Night Sweats", "C0028081", "finding"),
    ("Weight Loss", "C0042963", "finding"),
    ("Anorexia", "C0003123", "finding"),
    ("Abdominal Pain", "C0000737", "finding"),
    ("Back Pain", "C0004604", "finding"),
    ("Joint Pain", "C0003862", "finding"),
    ("Rash", "C0015231", "finding"),
    ("Seizure", "C0036572", "finding"),
    ("Weakness", "C0003698", "finding"),
]

_CONDITIONS = [
    ("Heart Failure", "C0018802", "disorder"),
    ("COPD", "C0024117", "disorder"),
    ("Asthma", "C0004096", "disorder"),
    ("Pneumonia", "C0032285", "disorder"),
    ("Myocardial Infarction", "C0027051", "disorder"),
    ("Angina", "C0002962", "disorder"),
    ("Pulmonary Embolism", "C0034065", "disorder"),
    ("Pericarditis", "C0031046", "disorder"),
    ("Aortic Dissection", "C0340507", "disorder"),
    ("Pericardial Effusion", "C0031058", "disorder"),
    ("Anemia", "C0002871", "disorder"),
    ("Hypothyroidism", "C0020676", "disorder"),
    ("Depression", "C0011570", "disorder"),
    ("Chronic Kidney Disease", "C1561643", "disorder"),
    ("Cirrhosis", "C0023890", "disorder"),
    ("Nephrotic Syndrome", "C0027726", "disorder"),
    ("Atrial Fibrillation", "C0004238", "disorder"),
    ("Anxiety", "C0003469", "disorder"),
    ("Ventricular Tachycardia", "C0042514", "disorder"),
    ("Lung Cancer", "C0242379", "disorder"),
    ("Sepsis", "C0036690", "disorder"),
    ("Meningitis", "C0025289", "disorder"),
    ("Malaria", "C0024530", "disorder"),
    ("Hepatitis", "C0019158", "disorder"),
    ("Biliary Obstruction", "C0008370", "disorder"),
    ("Hemolysis", "C0019059", "disorder"),
    ("Bladder Cancer", "C0005684", "disorder"),
    ("Kidney Stones", "C0022650", "disorder"),
    ("UTI", "C0042029", "disorder"),
    ("Glomerulonephritis", "C0017658", "disorder"),
    ("Arrhythmia", "C0003811", "disorder"),
    ("Orthostatic Hypotension", "C0085619", "disorder"),
    ("Gastroenteritis", "C0017160", "disorder"),
    ("Migraine", "C0149931", "disorder"),
    ("Tension Headache", "C0033901", "disorder"),
    ("Subarachnoid Hemorrhage", "C0036545", "disorder"),
    ("Delirium", "C0011206", "disorder"),
    ("Stroke", "C0038454", "disorder"),
    ("Hypoglycemia", "C0020615", "disorder"),
    ("Uremia", "C0041948", "disorder"),
    ("Diabetes Mellitus", "C0011849", "disorder"),
    ("Diabetic Ketoacidosis", "C0011880", "disorder"),
    ("Hypertension", "C0020538", "disorder"),
    ("Hyperlipidemia", "C0020473", "disorder"),
    ("Obesity", "C0028754", "disorder"),
    ("Sleep Apnea", "C0037315", "disorder"),
    ("Tuberculosis", "C0041296", "disorder"),
    ("Lymphoma", "C0024299", "disorder"),
    ("Appendicitis", "C0003615", "disorder"),
    ("Pancreatitis", "C0030305", "disorder"),
    ("Spinal Infection", "C0038029", "disorder"),
    ("Rheumatoid Arthritis", "C0003873", "disorder"),
    ("Gout", "C0018099", "disorder"),
    ("Allergic Reaction", "C0020517", "disorder"),
    ("Epilepsy", "C0014544", "disorder"),
    ("Myasthenia Gravis", "C0026896", "disorder"),
    ("Colon Cancer", "C0009376", "disorder"),
    ("AKI", "C0022660", "disorder"),
    ("Neuropathy", "C0442874", "disorder"),
    ("Hepatic Encephalopathy", "C0019158", "disorder"),
    ("Ascites", "C0003962", "disorder"),
]

_DRUGS = [
    ("Warfarin", "C0043031", "substance"),
    ("Aspirin", "C0004057", "substance"),
    ("Metformin", "C0025598", "substance"),
    ("Insulin", "C0021641", "substance"),
    ("Lisinopril", "C0065371", "substance"),
    ("Atorvastatin", "C0286651", "substance"),
    ("Amiodarone", "C0002598", "substance"),
    ("Digoxin", "C0012265", "substance"),
    ("Furosemide", "C0016860", "substance"),
    ("Ibuprofen", "C0020740", "substance"),
    ("Acetaminophen", "C0000970", "substance"),
    ("Prednisone", "C0032952", "substance"),
    ("Albuterol", "C0001644", "substance"),
    ("Omeprazole", "C0028978", "substance"),
    ("Levothyroxine", "C0021048", "substance"),
    ("Amlodipine", "C0051696", "substance"),
    ("Metoprolol", "C0025859", "substance"),
    ("Losartan", "C0065370", "substance"),
    ("Heparin", "C0019134", "substance"),
    ("Clopidogrel", "C0070166", "substance"),
    ("Finasteride", "C0016277", "substance"),
    ("ACE Inhibitor", "C0003015", "substance"),
    ("NSAID", "C0027410", "substance"),
]

_PROCEDURES = [
    ("ECG", "C0013798", "procedure"),
    ("Echocardiogram", "C0013516", "procedure"),
    ("Chest X-Ray", "C0001624", "procedure"),
    ("CT Scan", "C0040405", "procedure"),
    ("MRI", "C0024485", "procedure"),
    ("Blood Culture", "C0005792", "procedure"),
    ("Arterial Blood Gas", "C0002778", "procedure"),
    ("Spirometry", "C0037981", "procedure"),
    ("Cardiac Catheterization", "C0007130", "procedure"),
    ("Colonoscopy", "C0009376", "procedure"),
]

ALL_CONCEPTS = _SYMPTOMS + _CONDITIONS + _DRUGS + _PROCEDURES

EDGES = [
    ("Dyspnea","INDICATES","Heart Failure"),
    ("Dyspnea","INDICATES","COPD"),
    ("Dyspnea","INDICATES","Pneumonia"),
    ("Dyspnea","INDICATES","Asthma"),
    ("Dyspnea","INDICATES","Pulmonary Embolism"),
    ("Orthopnea","INDICATES","Heart Failure"),
    ("Orthopnea","INDICATES","Pericardial Effusion"),
    ("Chest Pain","INDICATES","Myocardial Infarction"),
    ("Chest Pain","INDICATES","Angina"),
    ("Chest Pain","INDICATES","Pulmonary Embolism"),
    ("Chest Pain","INDICATES","Pericarditis"),
    ("Chest Pain","INDICATES","Aortic Dissection"),
    ("Fatigue","INDICATES","Anemia"),
    ("Fatigue","INDICATES","Heart Failure"),
    ("Fatigue","INDICATES","Hypothyroidism"),
    ("Fatigue","INDICATES","Depression"),
    ("Edema","INDICATES","Heart Failure"),
    ("Edema","INDICATES","Chronic Kidney Disease"),
    ("Edema","INDICATES","Cirrhosis"),
    ("Edema","INDICATES","Nephrotic Syndrome"),
    ("Palpitations","INDICATES","Atrial Fibrillation"),
    ("Palpitations","INDICATES","Anxiety"),
    ("Palpitations","INDICATES","Ventricular Tachycardia"),
    ("Cough","INDICATES","COPD"),
    ("Cough","INDICATES","Pneumonia"),
    ("Cough","INDICATES","Asthma"),
    ("Cough","INDICATES","Lung Cancer"),
    ("Fever","INDICATES","Sepsis"),
    ("Fever","INDICATES","Pneumonia"),
    ("Fever","INDICATES","Meningitis"),
    ("Fever","INDICATES","Malaria"),
    ("Jaundice","INDICATES","Hepatitis"),
    ("Jaundice","INDICATES","Cirrhosis"),
    ("Jaundice","INDICATES","Biliary Obstruction"),
    ("Jaundice","INDICATES","Hemolysis"),
    ("Hematuria","INDICATES","Bladder Cancer"),
    ("Hematuria","INDICATES","Kidney Stones"),
    ("Hematuria","INDICATES","UTI"),
    ("Hematuria","INDICATES","Glomerulonephritis"),
    ("Syncope","INDICATES","Arrhythmia"),
    ("Syncope","INDICATES","Orthostatic Hypotension"),
    ("Syncope","INDICATES","Pulmonary Embolism"),
    ("Headache","INDICATES","Migraine"),
    ("Headache","INDICATES","Tension Headache"),
    ("Headache","INDICATES","Subarachnoid Hemorrhage"),
    ("Headache","INDICATES","Meningitis"),
    ("Nausea","INDICATES","Gastroenteritis"),
    ("Nausea","INDICATES","Myocardial Infarction"),
    ("Nausea","INDICATES","Migraine"),
    ("Wheeze","INDICATES","Asthma"),
    ("Wheeze","INDICATES","COPD"),
    ("Wheeze","INDICATES","Anaphylaxis"),
    ("Confusion","INDICATES","Delirium"),
    ("Confusion","INDICATES","Stroke"),
    ("Confusion","INDICATES","Hypoglycemia"),
    ("Confusion","INDICATES","Uremia"),
    ("Hemoptysis","INDICATES","Lung Cancer"),
    ("Hemoptysis","INDICATES","Pulmonary Embolism"),
    ("Hemoptysis","INDICATES","Tuberculosis"),
    ("Night Sweats","INDICATES","Tuberculosis"),
    ("Night Sweats","INDICATES","Lymphoma"),
    ("Weight Loss","INDICATES","Lung Cancer"),
    ("Weight Loss","INDICATES","Diabetes Mellitus"),
    ("Anorexia","INDICATES","Colon Cancer"),
    ("Anorexia","INDICATES","Depression"),
    ("Abdominal Pain","INDICATES","Gastroenteritis"),
    ("Abdominal Pain","INDICATES","Appendicitis"),
    ("Abdominal Pain","INDICATES","Pancreatitis"),
    ("Back Pain","INDICATES","Kidney Stones"),
    ("Back Pain","INDICATES","Spinal Infection"),
    ("Joint Pain","INDICATES","Rheumatoid Arthritis"),
    ("Joint Pain","INDICATES","Gout"),
    ("Rash","INDICATES","Meningitis"),
    ("Rash","INDICATES","Allergic Reaction"),
    ("Seizure","INDICATES","Epilepsy"),
    ("Seizure","INDICATES","Hypoglycemia"),
    ("Weakness","INDICATES","Stroke"),
    ("Weakness","INDICATES","Myasthenia Gravis"),
    ("Chills","INDICATES","Sepsis"),
    ("Chills","INDICATES","Malaria"),
    ("Vomiting","INDICATES","Gastroenteritis"),
    ("Vomiting","INDICATES","Migraine"),
    ("Diarrhea","INDICATES","Gastroenteritis"),
    ("Constipation","INDICATES","Colon Cancer"),
    ("Dizziness","INDICATES","Orthostatic Hypotension"),
    ("Dizziness","INDICATES","Anemia"),
    ("Aspirin","TREATS","Myocardial Infarction"),
    ("Aspirin","TREATS","Angina"),
    ("Furosemide","TREATS","Heart Failure"),
    ("Furosemide","TREATS","Edema"),
    ("Insulin","TREATS","Diabetes Mellitus"),
    ("Insulin","TREATS","Diabetic Ketoacidosis"),
    ("Metformin","TREATS","Diabetes Mellitus"),
    ("Lisinopril","TREATS","Hypertension"),
    ("Lisinopril","TREATS","Heart Failure"),
    ("Atorvastatin","TREATS","Hyperlipidemia"),
    ("Amiodarone","TREATS","Atrial Fibrillation"),
    ("Amiodarone","TREATS","Ventricular Tachycardia"),
    ("Digoxin","TREATS","Atrial Fibrillation"),
    ("Digoxin","TREATS","Heart Failure"),
    ("Albuterol","TREATS","Asthma"),
    ("Albuterol","TREATS","COPD"),
    ("Prednisone","TREATS","Asthma"),
    ("Prednisone","TREATS","COPD"),
    ("Levothyroxine","TREATS","Hypothyroidism"),
    ("Omeprazole","TREATS","Gastroenteritis"),
    ("Amlodipine","TREATS","Hypertension"),
    ("Metoprolol","TREATS","Hypertension"),
    ("Metoprolol","TREATS","Atrial Fibrillation"),
    ("Losartan","TREATS","Hypertension"),
    ("Losartan","TREATS","Heart Failure"),
    ("Heparin","TREATS","Pulmonary Embolism"),
    ("Heparin","TREATS","Myocardial Infarction"),
    ("Clopidogrel","TREATS","Myocardial Infarction"),
    ("Clopidogrel","TREATS","Stroke"),
    ("Ibuprofen","TREATS","Headache"),
    ("Ibuprofen","TREATS","Joint Pain"),
    ("Acetaminophen","TREATS","Fever"),
    ("Acetaminophen","TREATS","Headache"),
    ("Warfarin","CONTRAINDICATES","Aspirin"),
    ("Warfarin","CONTRAINDICATES","Ibuprofen"),
    ("Warfarin","CONTRAINDICATES","Heparin"),
    ("Metformin","CONTRAINDICATES","Chronic Kidney Disease"),
    ("Metformin","CONTRAINDICATES","Severe Renal Impairment"),
    ("Aspirin","CONTRAINDICATES","Warfarin"),
    ("Ibuprofen","CONTRAINDICATES","Warfarin"),
    ("Amiodarone","CONTRAINDICATES","Digoxin"),
    ("ACE Inhibitor","CONTRAINDICATES","Angioedema"),
    ("NSAID","CONTRAINDICATES","Chronic Kidney Disease"),
    ("Diabetes Mellitus","CAUSES","Chronic Kidney Disease"),
    ("Diabetes Mellitus","CAUSES","Neuropathy"),
    ("Hypertension","CAUSES","Heart Failure"),
    ("Hypertension","CAUSES","Chronic Kidney Disease"),
    ("Hypertension","CAUSES","Stroke"),
    ("COPD","ASSOCIATED_WITH","Heart Failure"),
    ("COPD","WORSENS","Pulmonary Embolism"),
    ("Sleep Apnea","CAUSES","Hypertension"),
    ("Sleep Apnea","CAUSES","Atrial Fibrillation"),
    ("Obesity","WORSENS","Diabetes Mellitus"),
    ("Obesity","WORSENS","Hypertension"),
    ("Obesity","WORSENS","Sleep Apnea"),
    ("Hyperlipidemia","CAUSES","Myocardial Infarction"),
    ("Hyperlipidemia","CAUSES","Stroke"),
    ("Anemia","WORSENS","Heart Failure"),
    ("Chronic Kidney Disease","CAUSES","Anemia"),
    ("Chronic Kidney Disease","CAUSES","Hyperlipidemia"),
    ("Cirrhosis","CAUSES","Hepatic Encephalopathy"),
    ("Cirrhosis","CAUSES","Ascites"),
    ("Hepatitis","CAUSES","Cirrhosis"),
    ("Atrial Fibrillation","CAUSES","Stroke"),
    ("Myocardial Infarction","CAUSES","Heart Failure"),
    ("Heart Failure","CAUSES","Chronic Kidney Disease"),
    ("Sepsis","CAUSES","AKI"),
    ("Pneumonia","CAUSES","Sepsis"),
    ("Meningitis","CAUSES","Sepsis"),
    ("Tuberculosis","CAUSES","Chronic Kidney Disease"),
    ("Lymphoma","CAUSES","Anemia"),
    ("ECG","DIAGNOSES","Myocardial Infarction"),
    ("ECG","DIAGNOSES","Atrial Fibrillation"),
    ("ECG","DIAGNOSES","Ventricular Tachycardia"),
    ("Echocardiogram","DIAGNOSES","Heart Failure"),
    ("Echocardiogram","DIAGNOSES","Pericardial Effusion"),
    ("Chest X-Ray","DIAGNOSES","Pneumonia"),
    ("Chest X-Ray","DIAGNOSES","COPD"),
    ("Chest X-Ray","DIAGNOSES","Lung Cancer"),
    ("CT Scan","DIAGNOSES","Pulmonary Embolism"),
    ("CT Scan","DIAGNOSES","Stroke"),
    ("CT Scan","DIAGNOSES","Aortic Dissection"),
    ("MRI","DIAGNOSES","Stroke"),
    ("MRI","DIAGNOSES","Meningitis"),
    ("Blood Culture","DIAGNOSES","Sepsis"),
    ("Arterial Blood Gas","DIAGNOSES","COPD"),
    ("Arterial Blood Gas","DIAGNOSES","Pulmonary Embolism"),
    ("Spirometry","DIAGNOSES","Asthma"),
    ("Spirometry","DIAGNOSES","COPD"),
    ("Cardiac Catheterization","DIAGNOSES","Myocardial Infarction"),
    ("Cardiac Catheterization","DIAGNOSES","Angina"),
    ("Colonoscopy","DIAGNOSES","Colon Cancer"),
]


def lookup_edges(from_node: str, relation: Optional[str] = None) -> List[Dict]:
    """Symbolic lookup: find all ontology edges originating from from_node.
    Pure in-memory operation on the EDGES constant. No LLM, no Neo4j needed."""
    results = []
    for h, r, t in EDGES:
        if h.lower() == from_node.lower() and (relation is None or r == relation):
            results.append({"head": h, "relation": r, "tail": t})
    return results


def lookup_all_by_symptoms(symptoms: List[str]) -> Dict[str, List[Dict]]:
    """Batch lookup: for each symptom, return all ontology edges.
    Returns {symptom: [{head, relation, tail}, ...]}"""
    mappings = {}
    for symptom in symptoms:
        edges = lookup_edges(symptom)
        if edges:
            mappings[symptom] = edges
    return mappings


class Neo4jVerifier:
    def __init__(self, uri: str = None, auth: tuple = None, max_pool_size: int = 50, query_timeout: float = None):
        uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        auth = auth or (os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "speculative123"))
        self.driver = GraphDatabase.driver(uri, auth=auth, max_connection_pool_size=max_pool_size)
        self.query_timeout = query_timeout if query_timeout is not None else float(os.getenv("NEO4J_QUERY_TIMEOUT", "5.0"))
        self.cb = CircuitBreaker("neo4j", failure_threshold=3, recovery_timeout=30.0)

    def close(self):
        self.driver.close()

    async def validate_async(self, proposed_path: List[Dict]) -> Dict:
        """Async-safe validation with timeout and circuit breaker."""
        try:
            return await self.cb.call(self._validate_async_impl, proposed_path)
        except CircuitBreakerOpenError:
            logger.error("Neo4j circuit breaker OPEN; falling back to in-memory validation")
            result = self._validate_in_memory(proposed_path)
            result["mode"] = "degraded"
            return result

    async def _validate_async_impl(self, proposed_path: List[Dict]) -> Dict:
        loop = asyncio.get_running_loop()
        return await asyncio.wait_for(
            loop.run_in_executor(None, self.validate, proposed_path),
            timeout=self.query_timeout + 2.0
        )

    async def seed_mock_ontology_async(self, scale: int = 100) -> None:
        """Async-safe seeding."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.seed_mock_ontology, scale)

    def validate(self, proposed_path: List[Dict]) -> Dict:
        if not proposed_path:
            return {
                "is_valid": False,
                "valid_edges": [],
                "violations": [{"reason": "Empty path: no diagnostic entities extracted"}],
                "total_checked": 0,
                "confidence_decay": 0.0,
                "mode": "symbolic_only",
            }
        try:
            with self.driver.session() as session:
                session.run("RETURN 1", timeout=self.query_timeout)
        except Exception as e:
            logger.warning(f"Neo4j unreachable ({e}). Falling back to in-memory validation (DEGRADED MODE).")
            result = self._validate_in_memory(proposed_path)
            result["mode"] = "degraded"
            return result
        violations = []
        valid_edges = []
        for triplet in proposed_path:
            head = triplet.get("head")
            relation = triplet.get("relation")
            tail = triplet.get("tail")
            head_cui = triplet.get("head_cui")
            tail_cui = triplet.get("tail_cui")
            is_valid = self._check_edge_exists(head, relation, tail, head_cui, tail_cui)
            if is_valid:
                valid_edges.append(triplet)
            else:
                violations.append({
                    "triplet": triplet,
                    "reason": f"Edge ({head})-[:{relation}]->({tail}) not found in taxonomy",
                })
        decay = max(0.0, 1.0 - (len(violations) * 0.15))
        return {
            "is_valid": len(violations) == 0 and len(valid_edges) > 0,
            "valid_edges": valid_edges,
            "violations": violations,
            "total_checked": len(proposed_path),
            "confidence_decay": decay,
            "mode": "full",
        }

    def _validate_in_memory(self, proposed_path: List[Dict]) -> Dict:
        """Fallback validation when Neo4j is unavailable. Uses in-memory EDGES."""
        violations = []
        valid_edges = []
        edge_set = {(h, r, t) for h, r, t in EDGES}
        for triplet in proposed_path:
            head = triplet.get("head")
            relation = triplet.get("relation")
            tail = triplet.get("tail")
            if (head, relation, tail) in edge_set:
                valid_edges.append(triplet)
            else:
                violations.append({
                    "triplet": triplet,
                    "reason": f"Edge ({head})-[:{relation}]->({tail}) not found in in-memory taxonomy",
                })
        decay = max(0.0, 1.0 - (len(violations) * 0.15))
        return {
            "is_valid": len(violations) == 0 and len(valid_edges) > 0,
            "valid_edges": valid_edges,
            "violations": violations,
            "total_checked": len(proposed_path),
            "confidence_decay": decay,
            "mode": "degraded",
        }

    def _check_edge_exists(self, head: str, relation: str, tail: str, head_cui: Optional[str] = None, tail_cui: Optional[str] = None) -> bool:
        if head_cui and tail_cui:
            query = """
            MATCH (h:Concept {cui: $head_cui})-[r:RELATION {type: $relation}]->(t:Concept {cui: $tail_cui})
            RETURN count(r) > 0 AS exists
            """
            params = {"head_cui": head_cui, "relation": relation, "tail_cui": tail_cui}
        else:
            query = """
            MATCH (h:Concept {label: $head})-[r:RELATION {type: $relation}]->(t:Concept {label: $tail})
            RETURN count(r) > 0 AS exists
            """
            params = {"head": head, "relation": relation, "tail": tail}
        try:
            with self.driver.session() as session:
                result = session.run(query, **params, timeout=self.query_timeout)
                record = result.single()
                return record["exists"] if record else False
        except Exception as e:
            logger.warning(f"Neo4j check failed: {e}")
            return False

    def seed_mock_ontology(self, scale: int = 100):
        logger.warning("MOCK_MODE: Seeding programmatically generated mock ontology. NOT real SNOMED-CT/UMLS.")
        with self.driver.session() as session:
            session.run("CREATE CONSTRAINT concept_cui IF NOT EXISTS FOR (c:Concept) REQUIRE c.cui IS UNIQUE", timeout=self.query_timeout)
            for label, cui, semantic_tag in ALL_CONCEPTS:
                session.run(
                    "MERGE (c:Concept {cui: $cui}) ON CREATE SET c.label = $label, c.semantic_tag = $tag",
                    cui=cui, label=label, tag=semantic_tag,
                    timeout=self.query_timeout,
                )
            for head, rel_type, tail in EDGES:
                session.run("""
                    MATCH (h:Concept {label: $head}), (t:Concept {label: $tail})
                    MERGE (h)-[:RELATION {type: $rel}]->(t)
                """, head=head, tail=tail, rel=rel_type, timeout=self.query_timeout)
        logger.info(f"Mock ontology seeded: {len(ALL_CONCEPTS)} concepts, {len(EDGES)} edges.")


class SymbolicVerifier:
    _HARDCODED_DRUG_INTERACTIONS = {
        ("Warfarin", "Aspirin"): {"severity": "major", "reason": "Major bleed risk: anticoagulant + antiplatelet"},
        ("Warfarin", "Ibuprofen"): {"severity": "major", "reason": "Major bleed risk: anticoagulant + NSAID"},
        ("Warfarin", "Heparin"): {"severity": "major", "reason": "Dual anticoagulation without indication"},
        ("Amiodarone", "Digoxin"): {"severity": "major", "reason": "Additive bradycardia / toxicity risk"},
        ("Metformin", "Severe Renal Impairment"): {"severity": "contraindicated", "reason": "Lactic acidosis risk"},
        ("ACE Inhibitor", "Angioedema"): {"severity": "contraindicated", "reason": "Contraindicated if history of ACEi angioedema"},
    }

    _HARDCODED_AGE_CONTRAINDICATIONS = {
        "Aspirin": {"max_age": 12, "reason": "Reye syndrome risk in children"},
    }

    def __init__(self, rules_dir: str = None):
        self.rules_dir = rules_dir or os.getenv("SAFETY_RULES_DIR", "config/safety_rules")
        self.drug_interactions = {}
        self.age_contraindications = {}
        self.allergy_contraindications = {}
        self.pregnancy_contraindications = []
        self._load_rules()

    def _load_rules(self):
        di_path = os.path.join(self.rules_dir, "drug_interactions.yaml")
        if os.path.exists(di_path):
            with open(di_path) as f:
                data = yaml.safe_load(f)
                for rule in data.get("rules", []):
                    drugs = rule["drugs"]
                    for i in range(len(drugs)):
                        for j in range(i + 1, len(drugs)):
                            self.drug_interactions[(drugs[i], drugs[j])] = rule
                            self.drug_interactions[(drugs[j], drugs[i])] = rule
        else:
            self.drug_interactions = dict(self._HARDCODED_DRUG_INTERACTIONS)

        al_path = os.path.join(self.rules_dir, "allergy_contraindications.yaml")
        if os.path.exists(al_path):
            with open(al_path) as f:
                data = yaml.safe_load(f)
                for rule in data.get("rules", []):
                    self.allergy_contraindications[rule["allergen"]] = rule

        pr_path = os.path.join(self.rules_dir, "pregnancy_contraindications.yaml")
        if os.path.exists(pr_path):
            with open(pr_path) as f:
                data = yaml.safe_load(f)
                self.pregnancy_contraindications = data.get("rules", [])

        ag_path = os.path.join(self.rules_dir, "age_contraindications.yaml")
        if os.path.exists(ag_path):
            with open(ag_path) as f:
                data = yaml.safe_load(f)
                for rule in data.get("rules", []):
                    drug = rule.get("drug", rule.get("allergen"))
                    if drug:
                        self.age_contraindications[drug] = rule
        else:
            self.age_contraindications = dict(self._HARDCODED_AGE_CONTRAINDICATIONS)

    def hot_reload(self) -> int:
        """Reload rules from YAML without restarting. Returns count of loaded rules."""
        before = len(self.drug_interactions) + len(self.allergy_contraindications) + len(self.pregnancy_contraindications) + len(self.age_contraindications)
        self.drug_interactions = {}
        self.allergy_contraindications = {}
        self.pregnancy_contraindications = []
        self.age_contraindications = {}
        self._load_rules()
        after = len(self.drug_interactions) + len(self.allergy_contraindications) + len(self.pregnancy_contraindications) + len(self.age_contraindications)
        logger.info(f"SymbolicVerifier hot reload: {after} rules loaded (was {before})")
        return after

    def validate(self, proposed_path: List[Dict], patient_context: Optional[Dict] = None) -> Dict:
        violations = []
        valid_edges = []
        patient_context = patient_context or {}
        age = patient_context.get("age")
        allergies = {a.lower() for a in patient_context.get("allergies", [])}
        is_pregnant = patient_context.get("pregnancy_status") in ("pregnant", True, "yes")

        for triplet in proposed_path:
            head = triplet.get("head", "")
            tail = triplet.get("tail", "")
            relation = triplet.get("relation", "")

            # Drug interaction check
            key = (head, tail)
            if key in self.drug_interactions:
                rule = self.drug_interactions[key]
                violations.append({
                    "triplet": triplet,
                    "reason": f"Symbolic rule [{rule['severity']}]: {rule['reason']}",
                })
                continue

            # Age contraindication
            if age is not None and head in self.age_contraindications:
                rule = self.age_contraindications[head]
                if age < rule.get("max_age", 0):
                    violations.append({
                        "triplet": triplet,
                        "reason": f"Age rule: {rule['reason']}",
                    })
                    continue

            # Allergy check
            if head in self.allergy_contraindications or tail in self.allergy_contraindications:
                allergen = head if head in self.allergy_contraindications else tail
                rule = self.allergy_contraindications[allergen]
                if allergen.lower() in allergies:
                    violations.append({
                        "triplet": triplet,
                        "reason": f"Allergy rule: {rule['reason']}",
                    })
                    continue

            # Pregnancy check
            if is_pregnant:
                for rule in self.pregnancy_contraindications:
                    if head in rule.get("drugs", []) or tail in rule.get("drugs", []):
                        violations.append({
                            "triplet": triplet,
                            "reason": f"Pregnancy rule: {rule['reason']}",
                        })
                        break
                else:
                    valid_edges.append(triplet)
                continue

            valid_edges.append(triplet)

        return {
            "is_valid": len(violations) == 0 and len(valid_edges) > 0,
            "valid_edges": valid_edges,
            "violations": violations,
            "total_checked": len(proposed_path),
            "confidence_decay": max(0.0, 1.0 - len(violations) * 0.2),
        }


class OPAClient:
    def __init__(self, opa_url: str = None):
        self.opa_url = opa_url or os.getenv("OPA_URL", "http://localhost:8181/v1/data/clinical")
        import httpx
        self.client = httpx.AsyncClient(timeout=10.0)
        self.cb = CircuitBreaker("opa", failure_threshold=3, recovery_timeout=15.0)

    async def evaluate(self, payload: Dict) -> Dict:
        try:
            return await self.cb.call(self._evaluate_impl, payload)
        except CircuitBreakerOpenError:
            logger.error("OPA circuit breaker OPEN; FAIL-CLOSED")
            return {
                "allow": False,
                "violations": [{"reason": "OPA circuit breaker OPEN", "triplet": {}}],
            }

    async def _evaluate_impl(self, payload: Dict) -> Dict:
        try:
            response = await self.client.post(
                f"{self.opa_url}/allow",
                json={"input": payload},
            )
            response.raise_for_status()
            data = response.json()
            result = data.get("result")
            if result is None:
                logger.error("OPA returned no result (policy not loaded). FAIL-CLOSED: denying request.")
                return {
                    "allow": False,
                    "violations": [{"reason": "OPA returned no result (policy not loaded)", "triplet": {}}],
                }
            return {"allow": bool(result), "violations": []}
        except Exception as e:
            logger.error(f"OPA unreachable: {e}. FAIL-CLOSED: denying request.")
            return {
                "allow": False,
                "violations": [{"reason": f"OPA policy engine unreachable: {e}", "triplet": {}}],
            }

    async def evaluate_tool_execution(self, tool_name: str, payload: Dict) -> Dict:
        try:
            return await self.cb.call(self._evaluate_tool_execution_impl, tool_name, payload)
        except CircuitBreakerOpenError:
            logger.error("OPA circuit breaker OPEN; FAIL-CLOSED (tool exec)")
            return {
                "allow": False,
                "violations": [{"reason": "OPA circuit breaker OPEN (tool exec)", "triplet": {}}],
            }

    async def _evaluate_tool_execution_impl(self, tool_name: str, payload: Dict) -> Dict:
        try:
            response = await self.client.post(
                f"{self.opa_url}/tool_execution/allow",
                json={"input": {"tool": tool_name, "payload": payload}},
            )
            response.raise_for_status()
            data = response.json()
            return {"allow": data.get("result", False), "violations": []}
        except Exception as e:
            logger.error(f"OPA tool eval unreachable: {e}. FAIL-CLOSED: denying tool execution.")
            return {
                "allow": False,
                "violations": [{"reason": f"OPA tool policy unreachable: {e}", "triplet": {}}],
            }
