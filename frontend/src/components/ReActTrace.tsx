import { useEffect, useRef } from 'react';
import type { TraceEntry } from '../types/mas';

const ICONS: Record<string, string> = {
  thought: '\uD83E\uDDE0',
  action: '\u26A1',
  observation: '\uD83D\uDC41',
  governance: '\uD83D\uDEE1',
  synthesis: '\uD83D\uDCA1',
};

const BORDER_COLORS: Record<string, string> = {
  thought: 'border-l-blue-400',
  action: 'border-l-amber-400',
  observation: 'border-l-green-400',
  governance: 'border-l-purple-400',
  synthesis: 'border-l-cyan-400',
};

interface ReActTraceProps {
  traces: TraceEntry[];
}

export default function ReActTrace({ traces }: ReActTraceProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [traces.length]);

  return (
    <div className="h-full overflow-y-auto p-3 space-y-1 font-mono text-sm">
      {traces.length === 0 && (
        <div className="text-gray-500 text-center mt-8">
          Waiting for agent execution...
        </div>
      )}
      {traces.map(t => (
        <div
          key={t.id}
          className={`border-l-2 ${BORDER_COLORS[t.type]} pl-3 py-1.5`}
        >
          <div className="flex items-center gap-2 text-xs text-gray-400 mb-0.5">
            <span>{ICONS[t.type]}</span>
            <span className="font-semibold text-gray-300">{t.agent_name}</span>
            <span>{new Date(t.timestamp).toLocaleTimeString()}</span>
          </div>
          {t.thought && (
            <div className="text-blue-300">{t.thought}</div>
          )}
          {t.action && (
            <div className="text-amber-300">
              <span className="text-gray-500">action:</span> {t.action}
            </div>
          )}
          {t.observation && (
            <div className="text-green-300 text-xs mt-0.5 break-all">
              <span className="text-gray-500">obs:</span> {t.observation}
            </div>
          )}
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
