import React, { useEffect, useRef } from 'react'

export default function Terminal({ logs }) {
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  return (
    <div className="h-40 bg-gray-950 border-t border-gray-800 flex flex-col">
      {/* Terminal header */}
      <div className="flex items-center gap-2 px-3 py-1.5 border-b border-gray-800">
        <div className="flex gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-red-500" />
          <span className="w-2.5 h-2.5 rounded-full bg-yellow-500" />
          <span className="w-2.5 h-2.5 rounded-full bg-green-500" />
        </div>
        <span className="text-xs text-gray-500 font-mono">AgentForge — Output</span>
      </div>

      {/* Log output */}
      <div className="flex-1 overflow-y-auto px-4 py-2 font-mono text-xs leading-relaxed">
        {logs.map((line, i) => (
          <div key={i} className="flex gap-2">
            <span className="text-gray-600 select-none">{String(i + 1).padStart(2, '0')}</span>
            <span className="text-green-400">{line}</span>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
