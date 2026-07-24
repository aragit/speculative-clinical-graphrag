import { useState } from 'react';
import { ReactFlowProvider } from '@xyflow/react';
import { useMASSream } from '../hooks/useMASSream';
import DAGCanvas from './DAGCanvas';
import ReActTrace from './ReActTrace';
import MemoryState from './MemoryState';
import EscalationCard from './EscalationCard';
import ClinicalSummaryCard from './ClinicalSummaryCard';

const SAMPLE_NOTE = `67-year-old male with acute dyspnea and orthopnea presenting to ER.
History of CKD Stage 3, hypertension, and type 2 diabetes.
Currently on Metformin 1000mg BID, Lisinopril 10mg daily.
Worsening shortness of breath over 2 days, unable to lie flat.`;

export default function MASCockpit() {
  const { nodes, traces, stateSnapshot, isStreaming, finalOutput, escalationData, startStream } = useMASSream();
  const [patientNote, setPatientNote] = useState(SAMPLE_NOTE);

  const handleRun = () => {
    if (!patientNote.trim() || isStreaming) return;
    startStream(patientNote);
  };

  return (
    <div className="h-screen flex flex-col bg-gray-950">
      {/* Header */}
      <header className="flex items-center justify-between px-4 py-2 border-b border-gray-800 bg-gray-900/50">
        <div className="flex items-center gap-3">
          <h1 className="text-sm font-bold text-gray-100 tracking-wide">
            MAS Glass Box Cockpit
          </h1>
          <span className="text-[10px] text-gray-500 uppercase tracking-widest">
            Speculative Clinical GraphRAG
          </span>
        </div>
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${isStreaming ? 'bg-green-400 animate-pulse' : 'bg-gray-600'}`} />
          <span className="text-xs text-gray-400">
            {isStreaming ? 'Streaming...' : 'Idle'}
          </span>
        </div>
      </header>

      {/* Input Bar */}
      <div className="flex gap-2 px-4 py-2 border-b border-gray-800 bg-gray-900/30">
        <textarea
          value={patientNote}
          onChange={e => setPatientNote(e.target.value)}
          placeholder="Enter patient note..."
          rows={2}
          className="flex-1 bg-gray-900 border border-gray-700 rounded px-3 py-1.5 text-xs text-gray-200 font-mono resize-none focus:outline-none focus:border-blue-500"
          disabled={isStreaming}
        />
        <div className="flex flex-col gap-1">
          <button
            onClick={handleRun}
            disabled={isStreaming || !patientNote.trim()}
            className="px-4 py-1.5 bg-green-700 hover:bg-green-600 disabled:bg-gray-700 disabled:text-gray-500 text-white text-xs font-semibold rounded transition-colors"
          >
            {isStreaming ? 'Running...' : 'Run'}
          </button>
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-1 bg-gray-700 hover:bg-gray-600 text-gray-300 text-[10px] rounded transition-colors"
          >
            Reset
          </button>
        </div>
      </div>

      {/* 3-Zone Layout */}
      <div className="flex-1 flex min-h-0">
        {/* Zone 1: DAG Canvas (40%) */}
        <div className="w-[40%] border-r border-gray-800 flex flex-col">
          <div className="px-3 py-1.5 border-b border-gray-800 bg-gray-900/30">
            <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">
              Orchestration Canvas
            </span>
          </div>
          <div className="flex-1 min-h-0 relative overflow-hidden h-full">
            <ReactFlowProvider>
              <DAGCanvas agentNodes={nodes} />
            </ReactFlowProvider>
          </div>
        </div>

        {/* Zone 2: ReAct Trace (35%) */}
        <div className="w-[35%] border-r border-gray-800 flex flex-col">
          <div className="px-3 py-1.5 border-b border-gray-800 bg-gray-900/30 flex items-center justify-between">
            <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">
              ReAct Reasoning Trace
            </span>
            <span className="text-[10px] text-gray-500">{traces.length} events</span>
          </div>
          <div className="flex-1 min-h-0 overflow-hidden">
            <ReActTrace traces={traces} />
          </div>
        </div>

        {/* Zone 3: Memory State (25%) */}
        <div className="w-[25%] flex flex-col">
          <div className="px-3 py-1.5 border-b border-gray-800 bg-gray-900/30">
            <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">
              Global Memory State
            </span>
          </div>
          <div className="flex-1 min-h-0 overflow-hidden">
            <MemoryState stateSnapshot={stateSnapshot} />
          </div>
        </div>
      </div>

      {/* Final Output Bar */}
      {finalOutput && (
        <div className="border-t border-gray-800 bg-gray-900/50 max-h-40 overflow-y-auto font-sans">
          {escalationData ? (
            <EscalationCard data={escalationData} />
          ) : (
            <ClinicalSummaryCard output={finalOutput} />
          )}
        </div>
      )}
    </div>
  );
}
