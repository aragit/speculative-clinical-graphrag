import { useState } from 'react';
import type { EscalationData } from '../hooks/useMASSream';

interface EscalationCardProps {
  data: EscalationData;
}

export default function EscalationCard({ data }: EscalationCardProps) {
  const [showDetails, setShowDetails] = useState(true);

  return (
    <div className="mx-4 my-3 rounded-lg border border-red-500/50 bg-red-950/40 overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-2.5 bg-red-900/40 border-b border-red-500/30">
        <span className="text-lg">&#x1F6A8;</span>
        <div className="flex-1">
          <h3 className="text-sm font-bold text-red-300">
            Requires Physician Review
          </h3>
          <p className="text-[11px] text-red-400/70 mt-0.5">
            Escalated after 3 safety loops — autonomous synthesis blocked
          </p>
        </div>
        <button
          onClick={() => setShowDetails(!showDetails)}
          className="text-[10px] text-red-400 hover:text-red-300 px-2 py-1 rounded border border-red-500/30 hover:bg-red-900/30 transition-colors"
        >
          {showDetails ? 'Hide' : 'Details'}
        </button>
      </div>

      {/* Violation Details */}
      {showDetails && (
        <div className="px-4 py-3 space-y-2">
          {data.violations.length > 0 ? (
            data.violations.map((v, i) => (
              <div
                key={i}
                className="flex items-start gap-2 px-3 py-2 rounded bg-red-900/30 border border-red-500/20"
              >
                <span className="text-red-400 text-xs mt-0.5">&#x26A0;</span>
                <span className="text-xs text-red-200 break-words">{v}</span>
              </div>
            ))
          ) : (
            <div className="text-xs text-red-300/70 italic">
              Safety policy blocked the proposed diagnostic pathway.
            </div>
          )}

          {/* Raw output preview */}
          <details className="mt-2">
            <summary className="text-[10px] text-red-400/60 cursor-pointer hover:text-red-300 transition-colors">
              View full escalation details
            </summary>
            <pre className="mt-1 text-[10px] text-red-300/50 whitespace-pre-wrap break-all font-mono max-h-20 overflow-y-auto">
              {data.output}
            </pre>
          </details>
        </div>
      )}

      {/* Action Buttons */}
      <div className="flex gap-2 px-4 py-2.5 border-t border-red-500/20 bg-red-950/30">
        <button className="flex-1 px-3 py-1.5 bg-amber-700 hover:bg-amber-600 text-white text-xs font-semibold rounded transition-colors">
          &#x2705; Override &amp; Approve
        </button>
        <button className="flex-1 px-3 py-1.5 bg-blue-700 hover:bg-blue-600 text-white text-xs font-semibold rounded transition-colors">
          &#x270F; Modify Order
        </button>
        <button className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 text-gray-300 text-xs font-semibold rounded transition-colors">
          Dismiss
        </button>
      </div>
    </div>
  );
}
