from typing import Dict, List, Optional, Literal
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)


class TopologyChange(BaseModel):
    action: Literal["add_node", "remove_node", "add_edge", "remove_edge"]
    node_name: Optional[str] = None
    node_func_name: Optional[str] = None
    edges: Optional[List[str]] = None
    target_node: Optional[str] = None
    reason: str = ""


class DAGModifier:
    """Controlled topology modification with safety invariants."""

    IMMUTABLE_NODES = {"ingest", "verify_safety", "escalate", "fhir_parse"}

    PROTECTED_NODES = {"verify_safety", "escalate"}

    def __init__(self, topology):
        self.topology = topology
        self.pending_changes: List[TopologyChange] = []
        self.applied_changes: List[TopologyChange] = []

    def propose(self, change: TopologyChange) -> bool:
        if not self._validate_safety(change):
            logger.warning(f"Topology change rejected by safety schema: {change}")
            return False

        self.pending_changes.append(change)
        logger.info(f"Topology change proposed: {change.action} {change.node_name}")
        return True

    def _validate_safety(self, change: TopologyChange) -> bool:
        if change.action == "remove_node" and change.node_name in self.IMMUTABLE_NODES:
            logger.error(f"SAFETY VIOLATION: cannot remove immutable node {change.node_name}")
            return False

        if change.action == "add_edge" and change.target_node in self.PROTECTED_NODES:
            logger.error(f"SAFETY VIOLATION: cannot modify edges to protected node {change.target_node}")
            return False

        return True

    def apply_pending(self):
        for change in self.pending_changes:
            self._apply(change)
            self.applied_changes.append(change)
        self.pending_changes.clear()

    def _apply(self, change: TopologyChange):
        if change.action == "remove_node":
            self.topology.unregister(change.node_name)
            logger.info(f"Removed node: {change.node_name}")

    def get_change_log(self) -> List[Dict]:
        return [c.model_dump() for c in self.applied_changes]
