import { type Node, type Edge } from '@xyflow/react';

export const AGENT_NODES: Node[] = [
  {
    id: 'supervisor',
    type: 'default',
    position: { x: 300, y: 0 },
    data: { label: 'Supervisor Agent' },
    style: { width: 200 },
  },
  {
    id: 'clinical_extractor',
    type: 'default',
    position: { x: 300, y: 120 },
    data: { label: 'Clinical Extraction Agent' },
    style: { width: 200 },
  },
  {
    id: 'ontology_traverser',
    type: 'default',
    position: { x: 300, y: 240 },
    data: { label: 'Ontology Traversal Agent' },
    style: { width: 200 },
  },
  {
    id: 'opa_verifier',
    type: 'default',
    position: { x: 300, y: 360 },
    data: { label: 'Policy Governance Agent' },
    style: { width: 200 },
  },
  {
    id: 'synthesizer',
    type: 'default',
    position: { x: 300, y: 480 },
    data: { label: 'Synthesis Agent' },
    style: { width: 200 },
  },
];

export const AGENT_EDGES: Edge[] = [
  { id: 'e-sup-ext', source: 'supervisor', target: 'clinical_extractor', animated: false },
  { id: 'e-ext-ont', source: 'clinical_extractor', target: 'ontology_traverser', animated: false },
  { id: 'e-ont-gov', source: 'ontology_traverser', target: 'opa_verifier', animated: false },
  { id: 'e-gov-syn', source: 'opa_verifier', target: 'synthesizer', animated: false },
];
