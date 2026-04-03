import React from 'react'

const AGENT_META = {
  prompt:    { icon: '💬', color: 'text-gray-600',   bg: 'bg-gray-50',   border: 'border-gray-200' },
  planner:   { icon: '🗂️', color: 'text-indigo-600', bg: 'bg-indigo-50', border: 'border-indigo-200' },
  research:  { icon: '🔍', color: 'text-cyan-600',   bg: 'bg-cyan-50',   border: 'border-cyan-200' },
  execution: { icon: '⚙️', color: 'text-emerald-600',bg: 'bg-emerald-50',border: 'border-emerald-200' },
  summary:   { icon: '📋', color: 'text-amber-600',  bg: 'bg-amber-50',  border: 'border-amber-200' },
}

export default function ReportPanel({ report, onClose }) {
  if (!report) return null

  const { task, completedAt, agents } = report

  const handleDownload = () => {
    const lines = [
      '# AgentForge Task Report',
      `Task: ${task}`,
      `Completed: ${completedAt}`,
      '',
      '## Agent Outputs',
      '',
      ...Object.entries(agents).map(([id, out]) =>
        `### ${id.charAt(0).toUpperCase() + id.slice(1)}\n${out}\n`
      ),
    ]
    const blob = new Blob([lines.join('\n')], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `agentforge-report-${Date.now()}.md`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="absolute inset-y-0 right-0 w-80 bg-white border-l border-gray-200 shadow-xl z-20
                    flex flex-col animate-slide-in">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 bg-gray-50">
        <div>
          <p className="text-xs font-bold text-gray-900 uppercase tracking-widest">Task Report</p>
          <p className="text-[10px] text-gray-400 mt-0.5">{completedAt}</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleDownload}
            className="text-xs px-2 py-1 rounded border border-gray-300 text-gray-600
                       hover:bg-gray-100 transition"
            title="Download as Markdown"
          >
            ↓ .md
          </button>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-700 text-lg leading-none transition"
          >
            ×
          </button>
        </div>
      </div>

      {/* Task */}
      <div className="px-4 py-3 border-b border-gray-100">
        <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-widest mb-1">Task</p>
        <p className="text-sm text-gray-800 font-medium leading-snug">{task}</p>
      </div>

      {/* Agent outputs */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
        <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-widest">Agent Outputs</p>
        {Object.entries(agents).map(([id, output]) => {
          const meta = AGENT_META[id] || AGENT_META.summary
          return (
            <div key={id} className={`rounded-lg border p-3 ${meta.bg} ${meta.border}`}>
              <div className="flex items-center gap-1.5 mb-1.5">
                <span className="text-sm">{meta.icon}</span>
                <span className={`text-xs font-semibold ${meta.color} capitalize`}>{id}</span>
                <span className="ml-auto text-[10px] bg-green-100 text-green-700 px-1.5 py-0.5 rounded-full">
                  ✓ done
                </span>
              </div>
              <p className="text-xs text-gray-700 leading-relaxed">{output}</p>
            </div>
          )
        })}
      </div>

      {/* Footer */}
      <div className="px-4 py-3 border-t border-gray-100 bg-gray-50">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-green-400" />
          <span className="text-xs text-gray-500">All {Object.keys(agents).length} agents completed</span>
        </div>
      </div>
    </div>
  )
}
