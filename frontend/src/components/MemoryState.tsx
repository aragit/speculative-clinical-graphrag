import { useMemo } from 'react';

interface MemoryStateProps {
  stateSnapshot: Record<string, any>;
}

function renderValue(value: any, depth: number = 0): React.ReactNode {
  if (value === null) return <span className="json-null">null</span>;
  if (value === undefined) return <span className="json-null">undefined</span>;

  if (typeof value === 'boolean') {
    return <span className="json-boolean">{String(value)}</span>;
  }
  if (typeof value === 'number') {
    return <span className="json-number">{value}</span>;
  }
  if (typeof value === 'string') {
    const truncated = value.length > 120 ? value.slice(0, 120) + '...' : value;
    return <span className="json-string">"{truncated}"</span>;
  }

  if (Array.isArray(value)) {
    if (value.length === 0) return <span className="text-gray-500">[]</span>;
    const indent = '  '.repeat(depth + 1);
    const closeIndent = '  '.repeat(depth);
    return (
      <span>
        [<br />
        {value.map((item, i) => (
          <span key={i}>
            {indent}
            {renderValue(item, depth + 1)}
            {i < value.length - 1 ? ',' : ''}
            <br />
          </span>
        ))}
        {closeIndent}]
      </span>
    );
  }

  if (typeof value === 'object') {
    const keys = Object.keys(value);
    if (keys.length === 0) return <span className="text-gray-500">{'{}'}</span>;
    const indent = '  '.repeat(depth + 1);
    const closeIndent = '  '.repeat(depth);
    return (
      <span>
        {'{'}<br />
        {keys.map((key, i) => (
          <span key={key}>
            {indent}
            <span className="json-key">"{key}"</span>: {renderValue(value[key], depth + 1)}
            {i < keys.length - 1 ? ',' : ''}
            <br />
          </span>
        ))}
        {closeIndent}{'}'}
      </span>
    );
  }

  return <span>{String(value)}</span>;
}

export default function MemoryState({ stateSnapshot }: MemoryStateProps) {
  const changedKeys = useMemo(() => {
    return new Set(stateSnapshot._changed_keys || []);
  }, [stateSnapshot._changed_keys]);

  const displayState = useMemo(() => {
    const { _changed_keys, _last_update, ...rest } = stateSnapshot;
    return rest;
  }, [stateSnapshot]);

  const hasContent = Object.keys(displayState).length > 0;

  return (
    <div className="h-full overflow-y-auto p-3 font-mono text-sm">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
          Global Memory State
        </span>
        {stateSnapshot._last_update && (
          <span className="text-[10px] text-gray-500">
            {new Date(stateSnapshot._last_update).toLocaleTimeString()}
          </span>
        )}
      </div>

      {!hasContent && (
        <div className="text-gray-500 text-center mt-8">
          No state mutations yet...
        </div>
      )}

      {hasContent && (
        <div className="bg-gray-900 rounded p-3 border border-gray-800">
          <pre className="whitespace-pre-wrap break-all text-xs leading-relaxed">
            {Object.entries(displayState).map(([key, value]) => {
              const isNew = changedKeys.has(key);
              return (
                <div key={key} className={isNew ? 'json-new' : ''}>
                  <span className="json-key">"{key}"</span>: {renderValue(value, 0)}
                </div>
              );
            })}
          </pre>
        </div>
      )}

      {changedKeys.size > 0 && (
        <div className="mt-3 text-[10px] text-gray-500">
          Changed: {[...changedKeys].join(', ')}
        </div>
      )}
    </div>
  );
}
