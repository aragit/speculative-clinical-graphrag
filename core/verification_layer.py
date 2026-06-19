from typing import List, Dict
from neo4j import GraphDatabase


class Neo4jVerifier:
    def __init__(self, uri: str = "bolt://localhost:7687", auth: tuple = ("neo4j", "speculative123")):
        self.driver = GraphDatabase.driver(uri, auth=auth)

    def close(self):
        self.driver.close()

    def validate(self, proposed_path: List[Dict]) -> Dict:
        # Reject empty paths
        if not proposed_path:
            return {
                "is_valid": False,
                "valid_edges": [],
                "violations": [{"reason": "Empty path: no diagnostic entities extracted"}],
                "total_checked": 0,
            }

        violations = []
        valid_edges = []

        for triplet in proposed_path:
            head = triplet.get("head")
            relation = triplet.get("relation")
            tail = triplet.get("tail")

            is_valid = self._check_edge_exists(head, relation, tail)
            if is_valid:
                valid_edges.append(triplet)
            else:
                violations.append({
                    "triplet": triplet,
                    "reason": f"Edge ({head})-[:{relation}]->({tail}) not found in taxonomy",
                })

        return {
            "is_valid": len(violations) == 0 and len(valid_edges) > 0,
            "valid_edges": valid_edges,
            "violations": violations,
            "total_checked": len(proposed_path),
        }

    def _check_edge_exists(self, head: str, relation: str, tail: str) -> bool:
        query = """
        MATCH (h:Concept {label: $head})-[r:RELATION {type: $relation}]->(t:Concept {label: $tail})
        RETURN count(r) > 0 AS exists
        """
        with self.driver.session() as session:
            result = session.run(query, head=head, relation=relation, tail=tail)
            record = result.single()
            return record["exists"] if record else False

    def seed_mock_taxonomy(self):
        queries = [
            "CREATE CONSTRAINT concept_label IF NOT EXISTS FOR (c:Concept) REQUIRE c.label IS UNIQUE",
            "MERGE (:Concept {label: 'Dyspnea', cui: 'C0013404'})",
            "MERGE (:Concept {label: 'Orthopnea', cui: 'C0029124'})",
            "MERGE (:Concept {label: 'Heart Failure', cui: 'C0018802'})",
            "MERGE (:Concept {label: 'COPD', cui: 'C0024117'})",
            "MERGE (:Concept {label: 'Chest Pain', cui: 'C0008031'})",
            "MERGE (:Concept {label: 'Myocardial Infarction', cui: 'C0027051'})",
            "MATCH (h:Concept {label: 'Dyspnea'}), (t:Concept {label: 'Heart Failure'}) MERGE (h)-[:RELATION {type: 'INDICATES'}]->(t)",
            "MATCH (h:Concept {label: 'Dyspnea'}), (t:Concept {label: 'COPD'}) MERGE (h)-[:RELATION {type: 'INDICATES'}]->(t)",
            "MATCH (h:Concept {label: 'Orthopnea'}), (t:Concept {label: 'Heart Failure'}) MERGE (h)-[:RELATION {type: 'INDICATES'}]->(t)",
            "MATCH (h:Concept {label: 'Chest Pain'}), (t:Concept {label: 'Myocardial Infarction'}) MERGE (h)-[:RELATION {type: 'INDICATES'}]->(t)",
        ]
        with self.driver.session() as session:
            for q in queries:
                session.run(q)
        print("Mock taxonomy seeded successfully.")
