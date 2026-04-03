import React, { useState } from 'react'

const STATUS_STYLES = {
  idle:      { border: 'border-gray-200',   bg: 'bg-white',       badge: 'bg-gray-100 text-gray-500',    dot: 'bg-gray-300' },
  running:   { border: 'border-yellow-400', bg: 'bg-yellow-50',   badge: 'bg-yellow-100 text-yellow-700', dot: 'bg-yellow-400 animate-pulse' },
  completed: { border: 'border-green-400',  bg: 'bg-green-50',    badge: 'bg-green-100 text-green-700',  dot: 'bg-green-400' },
}

export default function AgentNode({ node, width, height }) {
  const [expanded, setExpanded] = useState(false)
  const s = STATUS_STYLES[node.status] || STATUS_STYLES.idle
  const preview = node.output ? node.output.split('\n')[0].slice(0, 60) + (node.output.length > 60 ? '…' : '') : ''

  return (
    <div
      className={`agent-node absolute rounded-xl border-2 shadow-sm transition-all duration-300
                  ${s.border} ${s.bg} flex flex-col p-3 gap-1.5`}
      style={{ left: node.x, top: node.y, width: expanded ? width + 80 : width, minHeight: height }}
    >
      {/* Header */}
      <div className="flex items-center gap-1.5">
        <span className="text-base leading-none">{node.icon}</span>
        <span className="text-xs font-semibold text-gray-800 truncate flex-1">{node.label}</span>
        <span className={`w-2 h-2 rounded-full flex-shrink-0 ${s.dot}`} />
      </div>

      {/* Status badge */}
      <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full self-start ${s.badge}`}>
        {node.status.charAt(0).toUpperCase() + node.status.slice(1)}
      </span>

      {/* Output */}
      {node.output && (
        <div className="mt-0.5">
          {expanded ? (
            <p className="text-[10px] text-gray-600 leading-relaxed whitespace-pre-wrap break-words">
              {node.output}
            </p>
          ) : (
            <p className="text-[10px] text-gray-500 leading-tight">{preview}</p>
          )}
          <button
            onClick={() => setExpanded(e => !e)}
            className="text-[9px] text-blue-500 hover:text-blue-700 mt-0.5 underline"
          >
            {expanded ? 'collapse' : 'expand'}
          </button>
        </div>
      )}

      {/* Running spinner */}
      {node.status === 'running' && (
        <div className="flex items-center gap-1 mt-0.5">
          <span className="animate-spin inline-block w-2.5 h-2.5 border-2 border-yellow-500 border-t-transparent rounded-full" />
          <span className="text-[10px] text-yellow-600">Processing...</span>
        </div>
      )}
    </div>
  )
}
