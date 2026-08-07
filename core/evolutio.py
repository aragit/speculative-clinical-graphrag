import json
import os
import shutil
import logging
from typing import Dict, List, Optional
from collections import defaultdict
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class OverrideAnalytics:
    def __init__(self, trace_store, min_confidence: float = 0.8):
        self.trace_store = trace_store
        self.min_confidence = min_confidence
        self.proposed_rules: List[Dict] = []
        self.staging_dir = os.getenv("RULES_STAGING_DIR", "config/safety_rules/staging")
        self.active_dir = os.getenv("RULES_ACTIVE_DIR", "config/safety_rules")
        os.makedirs(self.staging_dir, exist_ok=True)

    async def analyze_recent(self, hours: int = 24) -> Dict:
        traces = await self.trace_store.list_recent(limit=1000)

        overrides = [t for t in traces if t.get("status", "").startswith("clinician_")]

        patterns = {
            "drug_interactions": defaultdict(int),
            "symptom_conditions": defaultdict(int),
            "age_groups": defaultdict(int),
            "override_actions": defaultdict(int),
        }

        for trace in overrides:
            action = trace.get("override_action", "unknown")
            patterns["override_actions"][action] += 1

            path = trace.get("proposed_path", []) or []
            if not path and trace.get("modified_path"):
                path = trace.get("modified_path")

            for triplet in path:
                head = triplet.get("head", "")
                tail = triplet.get("tail", "")
                relation = triplet.get("relation", "")

                if relation == "CONTRAINDICATES":
                    key = f"{head}+{tail}"
                    patterns["drug_interactions"][key] += 1

                if relation == "INDICATES":
                    key = f"{head}->{tail}"
                    patterns["symptom_conditions"][key] += 1

            ctx = trace.get("patient_context", {})
            if not ctx and isinstance(ctx, str):
                try:
                    ctx = json.loads(ctx)
                except (json.JSONDecodeError, TypeError):
                    ctx = {}
            age = ctx.get("age") if ctx else None
            if age is not None:
                group = f"{(age // 10) * 10}-{(age // 10) * 10 + 9}"
                patterns["age_groups"][group] += 1

        self._generate_proposed_rules(patterns)

        return {
            "total_overrides": len(overrides),
            "patterns": {k: dict(v) for k, v in patterns.items()},
            "proposed_rules": self.proposed_rules,
        }

    def _generate_proposed_rules(self, patterns: Dict):
        self.proposed_rules = []

        for drug_combo, count in patterns["drug_interactions"].items():
            if count >= 2:
                drugs = drug_combo.split("+")
                self.proposed_rules.append({
                    "type": "drug_interaction",
                    "drugs": drugs,
                    "frequency": count,
                    "confidence": min(0.5 + count * 0.1, 0.95),
                    "status": "pending_approval",
                    "reason": f"Clinician overrode {count} times involving {drug_combo}",
                })

        for sym_cond, count in patterns["symptom_conditions"].items():
            if count >= 3:
                self.proposed_rules.append({
                    "type": "false_positive_mapping",
                    "mapping": sym_cond,
                    "frequency": count,
                    "confidence": min(0.6 + count * 0.05, 0.9),
                    "status": "pending_approval",
                    "reason": f"High override rate for mapping {sym_cond}",
                })

    async def approve_rule(self, rule_id: int) -> bool:
        if rule_id >= len(self.proposed_rules):
            return False

        rule = self.proposed_rules[rule_id]
        rule["status"] = "approved"
        rule["approved_at"] = datetime.now(timezone.utc).isoformat()
        rule["rule_id"] = rule_id

        self._write_rule_to_yaml(rule, self.staging_dir)
        logger.info(f"Rule approved and staged: {rule}")
        return True

    def _write_rule_to_yaml(self, rule: Dict, directory: str) -> str:
        import yaml
        os.makedirs(directory, exist_ok=True)
        filename = f"auto_generated_{rule['type']}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.yaml"
        filepath = os.path.join(directory, filename)

        yaml_content = {"rules": [rule]}
        with open(filepath, "w") as f:
            yaml.dump(yaml_content, f, default_flow_style=False)

        return filepath

    async def apply_approved_rules(self) -> Dict:
        staged_files = [f for f in os.listdir(self.staging_dir) if f.endswith(".yaml")]

        if not staged_files:
            return {"applied": 0, "message": "No staged rules to apply"}

        backup_dir = os.path.join(self.active_dir, f"backup_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}")
        os.makedirs(backup_dir, exist_ok=True)

        for filename in os.listdir(self.active_dir):
            if filename.endswith(".yaml") and filename != "staging":
                src = os.path.join(self.active_dir, filename)
                if os.path.isfile(src):
                    shutil.copy2(src, os.path.join(backup_dir, filename))

        applied = []
        for filename in staged_files:
            src = os.path.join(self.staging_dir, filename)
            dst = os.path.join(self.active_dir, filename)
            shutil.move(src, dst)
            applied.append(filename)

        logger.info(f"Applied {len(applied)} rules from staging to active")
        return {
            "applied": len(applied),
            "files": applied,
            "backup_location": backup_dir,
        }

    async def reject_rule(self, rule_id: int) -> bool:
        if rule_id >= len(self.proposed_rules):
            return False

        self.proposed_rules[rule_id]["status"] = "rejected"
        return True
