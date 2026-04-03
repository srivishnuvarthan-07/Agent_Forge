import React from 'react'

const AGENT_LIST = [
  { id: 'planner',   label: 'Planner Agent',   icon: '🗂️' },
  { id: 'research',  label: 'Research Agent',   icon: '🔍' },
  { id: 'execution', label: 'Execution Agent',  icon: '⚙️' },
  { id: 'summary',   label: 'Summary Agent',    icon: '📋' },
]

const STATUS_DOT = {
  idle:      'bg-gray-300',
  running:   'bg-yellow-400 animate-pulse',
  completed: 'bg-green-400',
}

export default function Sidebar({ activeAgent, nodes, onClear, onRun }) {
  const getStatus = (id) => nodes.find(n => n.id === id)?.status ?? 'idle'

  return (
    <div className="w-52 flex-shrink-0 border-r border-gray-200 bg-gray-50 flex flex-col text-sm">
      {/* Agents section */}
      <div className="px-3 pt-4 pb-2">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-widest mb-2">Agents</p>
        <ul className="space-y-1">
          {AGENT_LIST.map(a => {
            const status = getStatus(a.id)
            const isActive = activeAgent === a.id
            return (
              <li
                key={a.id}
                className={`flex items-center gap-2 px-2 py-1.5 rounded-md transition
                  ${isActive ? 'bg-gray-900 text-white' : 'text-gray-700 hover:bg-gray-100'}`}
              >
                <span>{a.icon}</span>
                <span className="flex-1 truncate">{a.label}</span>
                <span className={`w-2 h-2 rounded-full flex-shrink-0 ${STATUS_DOT[status]}`} />
              </li>
            )
          })}
        </ul>
      </div>

      <div className="border-t border-gray-200 mx-3 my-2" />

      {/* Actions section */}
      <div className="px-3 pb-4">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-widest mb-2">Actions</p>
        <div className="space-y-1.5">
          <button
            onClick={onClear}
            className="w-full flex items-center gap-2 px-2 py-1.5 rounded-md
                       text-gray-700 hover:bg-gray-100 transition text-left"
          >
            <span>🗑️</span> Clear Canvas
          </button>
        </div>
      </div>

      {/* Status legend */}
      <div className="mt-auto px-3 pb-4 space-y-1">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-widest mb-1">Legend</p>
        {[['idle','bg-gray-300','Idle'],['running','bg-yellow-400','Running'],['completed','bg-green-400','Done']].map(([,cls,label]) => (
          <div key={label} className="flex items-center gap-2 text-xs text-gray-500">
            <span className={`w-2 h-2 rounded-full ${cls}`} />
            {label}
          </div>
        ))}
      </div>
    </div>
  )
}
