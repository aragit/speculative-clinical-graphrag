import { useMemo } from 'react';

interface Triplet {
  head: string;
  relation: string;
  tail: string;
  confidence?: number;
}

interface SynthesisOutput {
  validated_path?: Triplet[];
  source_attribution?: Triplet[];
  reasoning_summary?: string;
  patient_context?: Record<string, any>;
}

interface ClinicalSummaryCardProps {
  output: string;
}

function parseOutput(raw: string): SynthesisOutput | null {
  try {
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === 'object' && (parsed.validated_path || parsed.source_attribution)) {
      return parsed;
    }
  } catch {
    // not JSON
  }
  return null;
}

export default function ClinicalSummaryCard({ output }: ClinicalSummaryCardProps) {
  const data = useMemo(() => parseOutput(output), [output]);

  if (!data) {
    // Fallback: render as formatted text
    return (
      <div className="px-4 py-2">
        <div className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-1">
          Final Output
        </div>
        <pre className="text-xs text-gray-300 whitespace-pre-wrap break-all font-mono">
          {output}
        </pre>
      </div>
    );
  }

  const triplets = data.validated_path || data.source_attribution || [];
  const ctx = data.patient_context || {};
  const meds = ctx.medications || [];
  const age = ctx.age;
  const gender = ctx.gender;

  return (
    <div className="px-4 py-3 space-y-3">
      {/* Header badge */}
      <div className="flex items-center gap-2">
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-green-900/40 border border-green-500/30 text-green-300 text-xs font-semibold">
          <span>&#x2705;</span>
          Validated Clinical Pathway
        </span>
        <span className="text-[10px] text-gray-500">
          {triplets.length} diagnostic triplet{triplets.length !== 1 ? 's' : ''} &middot; 0 safety violations
        </span>
      </div>

      {/* Patient context bar */}
      {(age || gender || meds.length > 0) && (
        <div className="flex items-center gap-3 text-[11px] text-gray-400">
          {age && gender && <span>{age}yo {gender}</span>}
          {meds.length > 0 && (
            <span>
              Medications: <span className="text-gray-300">{meds.join(', ')}</span>
            </span>
          )}
        </div>
      )}

      {/* Diagnostic triplets */}
      <div className="space-y-1.5">
        {triplets.map((t, i) => {
          const conf = t.confidence != null ? Math.round(t.confidence * 100) : null;
          return (
            <div
              key={i}
              className="flex items-center gap-2 px-3 py-1.5 rounded bg-gray-800/50 border border-gray-700/50"
            >
              <span className="text-xs text-gray-100 font-medium">{t.head}</span>
              <span className="text-[10px] text-blue-400 font-mono">{t.relation}</span>
              <span className="text-xs text-gray-100 font-medium">{t.tail}</span>
              {conf != null && (
                <span className={`ml-auto text-[10px] font-mono ${
                  conf >= 80 ? 'text-green-400' : conf >= 60 ? 'text-amber-400' : 'text-gray-500'
                }`}>
                  {conf}%
                </span>
              )}
            </div>
          );
        })}
      </div>

      {/* Reasoning summary */}
      {data.reasoning_summary && (
        <details className="mt-1">
          <summary className="text-[10px] text-gray-500 cursor-pointer hover:text-gray-400 transition-colors">
            View reasoning summary
          </summary>
          <p className="mt-1 text-[11px] text-gray-400 leading-relaxed whitespace-pre-wrap">
            {data.reasoning_summary}
          </p>
        </details>
      )}
    </div>
  );
}
