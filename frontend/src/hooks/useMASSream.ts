import { useState, useCallback, useRef } from 'react';
import type { MASEvent, AgentNode, TraceEntry, NodeStatus } from '../types/mas';

const INITIAL_NODES: AgentNode[] = [
  { id: 'supervisor', label: 'Central MCP Orchestrator', status: 'idle' },
  { id: 'clinical_extractor', label: 'MCP Skill: Clinical Extraction', status: 'idle' },
  { id: 'ontology_traverser', label: 'MCP Skill: Ontology Traversal', status: 'idle' },
  { id: 'opa_verifier', label: 'MCP Skill: Policy Governance', status: 'idle' },
  { id: 'synthesizer', label: 'MCP Skill: Bounded Synthesis', status: 'idle' },
];

export interface EscalationData {
  violations: string[];
  output: string;
}

export function useMASSream() {
  const [nodes, setNodes] = useState<AgentNode[]>(INITIAL_NODES);
  const [traces, setTraces] = useState<TraceEntry[]>([]);
  const [stateSnapshot, setStateSnapshot] = useState<Record<string, any>>({});
  const [isStreaming, setIsStreaming] = useState(false);
  const [finalOutput, setFinalOutput] = useState<string | null>(null);
  const [escalationData, setEscalationData] = useState<EscalationData | null>(null);
  const traceIdRef = useRef(0);

  const reset = useCallback(() => {
    setNodes(INITIAL_NODES.map(n => ({ ...n, status: 'idle' as NodeStatus })));
    setTraces([]);
    setStateSnapshot({});
    setIsStreaming(false);
    setFinalOutput(null);
    setEscalationData(null);
    traceIdRef.current = 0;
  }, []);

  const processEvent = useCallback((event: MASEvent) => {
    const { event_type, node_id, payload } = event;

    switch (event_type) {
      case 'NODE_START':
        setNodes(prev => prev.map(n =>
          n.id === node_id ? { ...n, status: 'active' as NodeStatus } : n
        ));
        break;

      case 'NODE_END':
        setNodes(prev => prev.map(n =>
          n.id === node_id ? { ...n, status: 'completed' as NodeStatus } : n
        ));
        break;

      case 'REACT_TRACE': {
        const trace: TraceEntry = {
          id: String(++traceIdRef.current),
          timestamp: event.timestamp,
          agent_name: payload.agent_name || node_id,
          thought: payload.thought || '',
          action: payload.action,
          observation: typeof payload.observation === 'string'
            ? payload.observation
            : payload.observation != null ? JSON.stringify(payload.observation) : undefined,
          type: 'thought',
        };
        setTraces(prev => [...prev, trace]);

        if (payload.action) {
          setTraces(prev => [...prev, {
            id: String(++traceIdRef.current),
            timestamp: event.timestamp,
            agent_name: payload.agent_name || node_id,
            thought: '',
            action: payload.action,
            type: 'action',
          }]);
        }
        if (payload.observation != null) {
          setTraces(prev => [...prev, {
            id: String(++traceIdRef.current),
            timestamp: event.timestamp,
            agent_name: payload.agent_name || node_id,
            thought: '',
            observation: typeof payload.observation === 'string'
              ? payload.observation
              : JSON.stringify(payload.observation),
            type: 'observation',
          }]);
        }
        break;
      }

      case 'GOVERNANCE_CHECK': {
        const check = payload as { passed: boolean; violations: any[]; policy_name: string };
        setNodes(prev => prev.map(n =>
          n.id === node_id
            ? { ...n, status: check.passed ? 'completed' as NodeStatus : 'blocked' as NodeStatus }
            : n
        ));
        setTraces(prev => [...prev, {
          id: String(++traceIdRef.current),
          timestamp: event.timestamp,
          agent_name: 'Policy Governance',
          thought: `Policy "${check.policy_name}" evaluation: ${check.passed ? 'PASSED' : 'BLOCKED'}`,
          observation: check.violations.length > 0
            ? `Violations: ${check.violations.map(v => v.reason).join('; ')}`
            : 'No violations detected.',
          type: 'governance',
        }]);
        break;
      }

      case 'STATE_MUTATION': {
        const mutation = payload as { changed_keys: string[]; state_snapshot: Record<string, any> };
        setStateSnapshot(prev => ({
          ...prev,
          ...mutation.state_snapshot,
          _changed_keys: mutation.changed_keys,
          _last_update: event.timestamp,
        }));
        break;
      }

      case 'FINAL_SYNTHESIS': {
        const synth = payload as { output_type: string; summary: string };
        setFinalOutput(synth.summary);
        if (synth.output_type === 'escalation') {
          // Extract violation details from the summary for the escalation card
          const violations: string[] = [];
          const violationMatch = synth.summary.match(/Violations?:?\s*(.+?)(?:\n|$)/i);
          if (violationMatch) {
            violations.push(violationMatch[1].trim());
          }
          // Also check for symbolic rule mentions
          const symbolicMatch = synth.summary.match(/Symbolic rule:\s*(.+?)(?:\n|";)/gi);
          if (symbolicMatch) {
            symbolicMatch.forEach(m => {
              const cleaned = m.replace(/^Symbolic rule:\s*/i, '').replace(/[";]/g, '').trim();
              if (cleaned && !violations.includes(cleaned)) violations.push(cleaned);
            });
          }
          // Check for drug/condition conflicts
          const drugMatch = synth.summary.match(/([\w]+)\s*(?:➔|->|→|contraindicates?)\s*([\w\s]+)/gi);
          if (drugMatch) {
            drugMatch.forEach(m => {
              if (!violations.some(v => v.includes(m))) violations.push(m.trim());
            });
          }
          setEscalationData({ violations, output: synth.summary });
        } else {
          setEscalationData(null);
        }
        setTraces(prev => [...prev, {
          id: String(++traceIdRef.current),
          timestamp: event.timestamp,
          agent_name: 'Synthesis Agent',
          thought: synth.output_type === 'synthesis'
            ? 'Clinical synthesis complete.'
            : 'Escalated to human review.',
          observation: synth.summary,
          type: 'synthesis',
        }]);
        break;
      }
    }
  }, []);

  const startStream = useCallback(async (patientNote: string, patientContext?: Record<string, any>) => {
    reset();
    setIsStreaming(true);

    try {
      const response = await fetch('/v1/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          patient_note: patientNote,
          patient_context: patientContext || null,
        }),
      });

      if (!response.ok) {
        throw new Error(`Stream failed: ${response.status}`);
      }

      const reader = response.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed || !trimmed.startsWith('data: ')) continue;

          const data = trimmed.slice(6);
          if (data === '[DONE]') break;

          try {
            const event: MASEvent = JSON.parse(data);
            processEvent(event);
          } catch {
            // skip malformed events
          }
        }
      }
    } catch (err) {
      console.error('Stream error:', err);
    } finally {
      setIsStreaming(false);
    }
  }, [reset, processEvent]);

  return { nodes, traces, stateSnapshot, isStreaming, finalOutput, escalationData, startStream, reset };
}
