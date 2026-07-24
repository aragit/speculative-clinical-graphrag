import { useMemo } from 'react';
import {
  ReactFlow,
  Background,
  type Node,
  type Edge,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import type { AgentNode } from '../types/mas';

const STATUS_STYLES: Record<string, { border: string; bg: string; shadow: string }> = {
  idle: { border: '#4b5563', bg: '#1f2937', shadow: 'none' },
  active: { border: '#4ade80', bg: 'rgba(20,83,45,0.4)', shadow: '0 0 20px rgba(74,222,128,0.4)' },
  completed: { border: '#60a5fa', bg: 'rgba(30,58,138,0.3)', shadow: '0 0 10px rgba(96,165,250,0.2)' },
  blocked: { border: '#f87171', bg: 'rgba(127,29,29,0.4)', shadow: '0 0 20px rgba(248,113,113,0.4)' },
};

interface DAGCanvasProps {
  agentNodes: AgentNode[];
}

const NODE_POSITIONS: Record<string, { x: number; y: number }> = {
  supervisor: { x: 100, y: 30 },
  clinical_extractor: { x: 100, y: 140 },
  ontology_traverser: { x: 100, y: 250 },
  opa_verifier: { x: 100, y: 360 },
  synthesizer: { x: 100, y: 470 },
};

const EDGES: Edge[] = [
  { id: 'e1', source: 'supervisor', target: 'clinical_extractor' },
  { id: 'e2', source: 'clinical_extractor', target: 'ontology_traverser' },
  { id: 'e3', source: 'ontology_traverser', target: 'opa_verifier' },
  { id: 'e4', source: 'opa_verifier', target: 'synthesizer' },
];

export default function DAGCanvas({ agentNodes }: DAGCanvasProps) {
  const nodes: Node[] = useMemo(() =>
    agentNodes.map(n => {
      const style = STATUS_STYLES[n.status] || STATUS_STYLES.idle;
      return {
        id: n.id,
        type: 'default',
        position: NODE_POSITIONS[n.id] || { x: 0, y: 0 },
        data: {
          label: (
            <div className="flex flex-col items-center gap-1 py-1">
              <span className="text-xs font-semibold text-gray-100">{n.label}</span>
              <span className={`text-[10px] uppercase tracking-wider ${
                n.status === 'active' ? 'text-green-400' :
                n.status === 'completed' ? 'text-blue-400' :
                n.status === 'blocked' ? 'text-red-400' :
                'text-gray-500'
              }`}>
                {n.status}
              </span>
            </div>
          ),
        },
        style: {
          width: 200,
          borderWidth: 2,
          borderColor: style.border,
          backgroundColor: style.bg,
          boxShadow: style.shadow,
          borderRadius: 8,
          transition: 'all 0.3s ease',
        },
      };
    }),
    [agentNodes]
  );

  return (
    <div className="w-full h-full relative overflow-hidden bg-gray-950 [&_.react-flow__attribution]:hidden [&_.react-flow__controls]:hidden">
      <ReactFlow
        nodes={nodes}
        edges={EDGES}
        fitView
        proOptions={{ hideAttribution: true }}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
      >
        <Background color="#374151" gap={20} />
      </ReactFlow>
    </div>
  );
}
