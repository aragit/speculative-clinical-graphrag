export interface MASEvent {
  event_id: string;
  timestamp: string;
  event_type:
    | 'NODE_START'
    | 'REACT_TRACE'
    | 'STATE_MUTATION'
    | 'GOVERNANCE_CHECK'
    | 'NODE_END'
    | 'FINAL_SYNTHESIS';
  node_id: string;
  payload: Record<string, any>;
}

export interface ReActTracePayload {
  agent_name: string;
  thought: string;
  action?: string;
  action_input?: Record<string, any>;
  observation?: any;
}

export interface GovernanceCheckPayload {
  policy_name: string;
  passed: boolean;
  violations: Array<{ reason: string; triplet?: any }>;
  details: Record<string, any>;
}

export interface StateMutationPayload {
  changed_keys: string[];
  state_snapshot: Record<string, any>;
}

export interface FinalSynthesisPayload {
  output_type: 'synthesis' | 'escalation';
  summary: string;
  full_output: Record<string, any>;
}

export type NodeStatus = 'idle' | 'active' | 'completed' | 'blocked';

export interface AgentNode {
  id: string;
  label: string;
  status: NodeStatus;
}

export interface TraceEntry {
  id: string;
  timestamp: string;
  agent_name: string;
  thought: string;
  action?: string;
  observation?: string;
  type: 'thought' | 'action' | 'observation' | 'governance' | 'synthesis';
}
