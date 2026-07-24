import { useMemo } from 'react';
import {
  ReactFlow,
  Background,
  type Node,
  type Edge,
  MarkerType,
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

// Hub-and-spoke layout: Supervisor top-center, MCP tools spread below
const NODE_POSITIONS: Record<string, { x: number; y: number }> = {
  supervisor:          { x: 200, y: 20 },
  clinical_extractor:  { x: 20,  y: 180 },
  ontology_traverser:  { x: 200, y: 180 },
  opa_verifier:        { x: 380, y: 180 },
  synthesizer:         { x: 200, y: 340 },
};

// Hub-and-spoke edges: Supervisor delegates to each MCP skill,
// plus sequential flow between MCP skills
const EDGES: Edge[] = [
  // Supervisor → MCP Skills (hub-spoke delegation)
  {
    id: 'e-sup-ext',
    source: 'supervisor',
    target: 'clinical_extractor',
    label: 'mcp:call',
    labelStyle: { fill: '#94a3b8', fontSize: 9, fontWeight: 500 },
    labelBgStyle: { fill: '#1e293b', fillOpacity: 0.9 },
    labelBgPadding: [4, 2] as [number, number],
    style: { stroke: '#6366f1', strokeWidth: 2 },
    animated: false,
    markerEnd: { type: MarkerType.ArrowClosed, color: '#6366f1', width: 16, height: 16 },
  },
  {
    id: 'e-sup-ont',
    source: 'supervisor',
    target: 'ontology_traverser',
    label: 'mcp:call',
    labelStyle: { fill: '#94a3b8', fontSize: 9, fontWeight: 500 },
    labelBgStyle: { fill: '#1e293b', fillOpacity: 0.9 },
    labelBgPadding: [4, 2] as [number, number],
    style: { stroke: '#6366f1', strokeWidth: 2 },
    animated: false,
    markerEnd: { type: MarkerType.ArrowClosed, color: '#6366f1', width: 16, height: 16 },
  },
  {
    id: 'e-sup-gov',
    source: 'supervisor',
    target: 'opa_verifier',
    label: 'mcp:call',
    labelStyle: { fill: '#94a3b8', fontSize: 9, fontWeight: 500 },
    labelBgStyle: { fill: '#1e293b', fillOpacity: 0.9 },
    labelBgPadding: [4, 2] as [number, number],
    style: { stroke: '#6366f1', strokeWidth: 2 },
    animated: false,
    markerEnd: { type: MarkerType.ArrowClosed, color: '#6366f1', width: 16, height: 16 },
  },
  // Sequential MCP skill flow
  {
    id: 'e-ext-ont',
    source: 'clinical_extractor',
    target: 'ontology_traverser',
    label: 'obs:return',
    labelStyle: { fill: '#64748b', fontSize: 8, fontWeight: 400 },
    labelBgStyle: { fill: '#1e293b', fillOpacity: 0.9 },
    labelBgPadding: [4, 2] as [number, number],
    style: { stroke: '#475569', strokeWidth: 1.5, strokeDasharray: '6 3' },
    animated: false,
    markerEnd: { type: MarkerType.ArrowClosed, color: '#475569', width: 12, height: 12 },
  },
  {
    id: 'e-ont-gov',
    source: 'ontology_traverser',
    target: 'opa_verifier',
    label: 'obs:return',
    labelStyle: { fill: '#64748b', fontSize: 8, fontWeight: 400 },
    labelBgStyle: { fill: '#1e293b', fillOpacity: 0.9 },
    labelBgPadding: [4, 2] as [number, number],
    style: { stroke: '#475569', strokeWidth: 1.5, strokeDasharray: '6 3' },
    animated: false,
    markerEnd: { type: MarkerType.ArrowClosed, color: '#475569', width: 12, height: 12 },
  },
  {
    id: 'e-gov-syn',
    source: 'opa_verifier',
    target: 'synthesizer',
    label: 'obs:return',
    labelStyle: { fill: '#64748b', fontSize: 8, fontWeight: 400 },
    labelBgStyle: { fill: '#1e293b', fillOpacity: 0.9 },
    labelBgPadding: [4, 2] as [number, number],
    style: { stroke: '#475569', strokeWidth: 1.5, strokeDasharray: '6 3' },
    animated: false,
    markerEnd: { type: MarkerType.ArrowClosed, color: '#475569', width: 12, height: 12 },
  },
];

export default function DAGCanvas({ agentNodes }: DAGCanvasProps) {
  const nodes: Node[] = useMemo(() =>
    agentNodes.map(n => {
      const style = STATUS_STYLES[n.status] || STATUS_STYLES.idle;
      const isSupervisor = n.id === 'supervisor';
      return {
        id: n.id,
        type: 'default',
        position: NODE_POSITIONS[n.id] || { x: 0, y: 0 },
        data: {
          label: (
            <div className="flex flex-col items-center gap-1 py-1 px-2">
              {isSupervisor && (
                <span className="text-[9px] text-indigo-400 uppercase tracking-widest font-medium mb-0.5">
                  Control Plane
                </span>
              )}
              <span className={`text-xs font-semibold text-gray-100 ${isSupervisor ? 'text-sm' : ''}`}>
                {n.label}
              </span>
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
          width: isSupervisor ? 220 : 180,
          borderWidth: 2,
          borderColor: style.border,
          backgroundColor: style.bg,
          boxShadow: style.shadow,
          borderRadius: isSupervisor ? 12 : 8,
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
        fitViewOptions={{ padding: 0.2 }}
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
