import React, { useState } from 'react'

export default function TopBar({ onRun, running, mode, onSwitchMode }) {
  const [task, setTask] = useState('')

  return (
    <div className="flex items-center gap-3 px-4 py-2 border-b border-gray-200 bg-white z-10 shadow-sm">
      {/* Logo */}
      <span className="text-sm font-bold tracking-tight text-gray-900 whitespace-nowrap">
        ⬡ AgentForge
      </span>

      {/* Mode switcher */}
      <div className="flex items-center gap-1 bg-gray-100 rounded-md p-0.5 flex-shrink-0">
        <button
          onClick={() => onSwitchMode('quick')}
          disabled={running}
          className={`px-3 py-1 text-xs font-medium rounded transition whitespace-nowrap
            ${mode === 'quick'
              ? 'bg-white text-gray-900 shadow-sm'
              : 'text-gray-500 hover:text-gray-700'
            } disabled:opacity-40 disabled:cursor-not-allowed`}
        >
          ⚡ Quick Mode
        </button>
        <button
          onClick={() => onSwitchMode('canvas')}
          disabled={running}
          className={`px-3 py-1 text-xs font-medium rounded transition whitespace-nowrap
            ${mode === 'canvas'
              ? 'bg-white text-gray-900 shadow-sm'
              : 'text-gray-500 hover:text-gray-700'
            } disabled:opacity-40 disabled:cursor-not-allowed`}
        >
          🧠 Canvas Mode
        </button>
      </div>

      {/* Mode badge */}
      <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium flex-shrink-0
        ${mode === 'quick'
          ? 'bg-blue-50 text-blue-600 border border-blue-200'
          : 'bg-purple-50 text-purple-600 border border-purple-200'
        }`}>
        {mode === 'quick' ? 'Node.js :3001' : 'CrewAI :8000'}
      </span>

      {/* Input */}
      <input
        className="flex-1 px-3 py-1.5 text-sm border border-gray-300 rounded-md outline-none
                   focus:border-gray-500 focus:ring-1 focus:ring-gray-400 bg-gray-50
                   placeholder-gray-400 transition"
        placeholder="Enter your task... e.g. Analyze market trends for AI startups"
        value={task}
        onChange={e => setTask(e.target.value)}
        onKeyDown={e => e.key === 'Enter' && onRun(task)}
        disabled={running}
      />

      {/* Run button */}
      <button
        onClick={() => onRun(task)}
        disabled={running || !task.trim()}
        className="px-4 py-1.5 text-sm font-medium rounded-md transition
                   bg-gray-900 text-white hover:bg-gray-700
                   disabled:opacity-40 disabled:cursor-not-allowed
                   flex items-center gap-2 whitespace-nowrap"
      >
        {running ? (
          <>
            <span className="animate-spin inline-block w-3 h-3 border-2 border-white border-t-transparent rounded-full" />
            Running...
          </>
        ) : '▶ Run Agents'}
      </button>
    </div>
  )
}
