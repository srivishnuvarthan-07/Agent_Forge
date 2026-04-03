import React, { useState, useRef, useEffect, useCallback } from 'react'
import Sidebar from './components/Sidebar'
import TopBar from './components/TopBar'
import Canvas from './components/Canvas'
import Terminal from './components/Terminal'
import ReportPanel from './components/ReportPanel'
import { BACKENDS } from './config'

const QUICK_NODES = [
  { id: 'prompt',    label: 'User Prompt',  icon: '💬', status: 'idle', output: '', x: 80,  y: 180 },
  { id: 'planner',   label: 'Planner',      icon: '🗂️', status: 'idle', output: '', x: 280, y: 180 },
  { id: 'research',  label: 'Research',     icon: '🔍', status: 'idle', output: '', x: 480, y: 180 },
  { id: 'execution', label: 'Execution',    icon: '⚙️', status: 'idle', output: '', x: 680, y: 180 },
  { id: 'summary',   label: 'Summary',      icon: '📋', status: 'idle', output: '', x: 880, y: 180 },
]

const CANVAS_NODES = [
  { id: 'ceo',        label: 'CEO Agent',       icon: '👔', status: 'idle', output: '', x: 400, y: 80  },
  { id: 'researcher', label: 'Researcher Agent', icon: '🔍', status: 'idle', output: '', x: 160, y: 280 },
  { id: 'analyst',    label: 'Analyst Agent',    icon: '📊', status: 'idle', output: '', x: 400, y: 280 },
  { id: 'writer',     label: 'Writer Agent',     icon: '✍️', status: 'idle', output: '', x: 640, y: 280 },
]

const QUICK_EDGES = [
  { from: 'prompt',    to: 'planner'   },
  { from: 'planner',   to: 'research'  },
  { from: 'research',  to: 'execution' },
  { from: 'execution', to: 'summary'   },
]

const CANVAS_EDGES = [
  { from: 'ceo', to: 'researcher' },
  { from: 'ceo', to: 'analyst'    },
  { from: 'ceo', to: 'writer'     },
]

export default function App() {
  const [mode, setMode] = useState('quick') // 'quick' | 'canvas'
  const INITIAL_NODES = mode === 'quick' ? QUICK_NODES : CANVAS_NODES
  const EDGES = mode === 'quick' ? QUICK_EDGES : CANVAS_EDGES
  const [nodes, setNodes] = useState(QUICK_NODES)
  const [logs, setLogs] = useState(['AgentForge ready. Enter a task and click Run Agents.'])
  const [running, setRunning] = useState(false)
  const [activeAgent, setActiveAgent] = useState(null)
  const [report, setReport] = useState(null)
  const wsRef = useRef(null)
  const taskRef = useRef('')
  const fullOutputs = useRef({})

  const backend = BACKENDS[mode]
  const addLog = useCallback((msg) => setLogs(prev => [...prev, msg]), [])

  // Reconnect WebSocket whenever mode changes
  useEffect(() => {
    let ws
    let reconnectTimer

    function connect() {
      ws = new WebSocket(backend.ws)
      wsRef.current = ws

      ws.onopen = () => addLog(`🔌 Connected to AgentForge [${mode === 'quick' ? 'Quick Mode' : 'Canvas Mode'}]`)

      ws.onmessage = (e) => {
        const msg = JSON.parse(e.data)
        // normalise agent id — live mode uses agent_id, quick mode uses agentId
        const agentId = msg.agentId || msg.agent_id
        if (msg.type === 'connected') {
          // handshake — no-op
        } else if (msg.type === 'job_started') {
          addLog(`▶ Pipeline started`)
        } else if (msg.type === 'agent_started') {
          setActiveAgent(agentId)
          setNodes(prev => prev.map(n => n.id === agentId ? { ...n, status: 'running' } : n))
          addLog(msg.log || `⚡ ${msg.label || agentId} running...`)
        } else if (msg.type === 'agent_completed') {
          const output = msg.output || ''
          fullOutputs.current[agentId] = output
          setNodes(prev => prev.map(n =>
            n.id === agentId ? { ...n, status: 'completed', output } : n
          ))
          setActiveAgent(null)
          addLog(msg.log || `✓ ${msg.label || agentId} done`)
        } else if (msg.type === 'crew_finished') {
          addLog(msg.log || '✅ All agents done')
          setRunning(false)
          setActiveAgent(null)
          const outputs = msg.outputs || fullOutputs.current
          setReport({ task: taskRef.current, completedAt: new Date().toLocaleString(), agents: outputs })
        } else if (msg.type === 'error') {
          addLog(`❌ Error: ${msg.message}`)
          setRunning(false)
        }
      }

      ws.onerror = () => addLog(`⚠ WebSocket error — is the ${mode === 'quick' ? 'node-backend' : 'crewai-backend'} running?`)
      ws.onclose = () => {
        addLog('🔌 Disconnected. Retrying in 3s...')
        reconnectTimer = setTimeout(connect, 3000)
      }
    }

    connect()
    return () => { clearTimeout(reconnectTimer); ws?.close() }
  }, [mode, backend.ws, addLog])

  const reset = useCallback(() => {
    const resetNodes = mode === 'quick' ? QUICK_NODES : CANVAS_NODES
    setNodes(resetNodes)
    setLogs(['Canvas cleared. Ready for new task.'])
    setActiveAgent(null)
    setReport(null)
    fullOutputs.current = {}
  }, [mode])

  const switchMode = useCallback((newMode) => {
    if (newMode === mode) return
    setMode(newMode)
    const newNodes = newMode === 'quick' ? QUICK_NODES : CANVAS_NODES
    setNodes(newNodes)
    setLogs([`Switched to ${newMode === 'quick' ? '⚡ Quick Mode (Node.js · Groq)' : '🧠 Canvas Mode (CrewAI · Groq)'}`])
    setActiveAgent(null)
    setReport(null)
    fullOutputs.current = {}
  }, [mode])

  const runAgents = useCallback(async (task) => {
    if (running || !task.trim()) return
    setRunning(true)
    setNodes(mode === 'quick' ? QUICK_NODES : CANVAS_NODES)
    setReport(null)
    fullOutputs.current = {}
    taskRef.current = task
    setLogs([`▶ Submitting task: "${task}" [${mode === 'quick' ? 'Quick Mode' : 'Canvas Mode'}]`])

    const endpoint = mode === 'quick'
      ? `${backend.http}/run-task`
      : `${backend.http}/api/crews/execute`

    // Canvas Mode: send a real CrewAI crew — CEO orchestrates researcher + analyst + writer
    const canvasNodes = [
      { id: 'ceo',        label: 'CEO Agent',        authority_level: 'executive', task_description: task },
      { id: 'researcher', label: 'Researcher Agent',  authority_level: 'standard',  task_description: task },
      { id: 'analyst',    label: 'Analyst Agent',     authority_level: 'junior',    task_description: task },
      { id: 'writer',     label: 'Writer Agent',      authority_level: 'standard',  task_description: task },
    ]
    const canvasEdges = [
      { source: 'ceo', target: 'researcher' },
      { source: 'ceo', target: 'analyst' },
      { source: 'ceo', target: 'writer' },
    ]

    const body = mode === 'quick'
      ? { prompt: task }
      : { nodes: canvasNodes, edges: canvasEdges, mode: 'live', crew_id: `job_${Date.now()}` }

    try {
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      addLog(`📋 Job queued: ${data.jobId || data.job_id}`)
    } catch (err) {
      addLog(`❌ Failed to reach backend: ${err.message}`)
      addLog(`Make sure the ${mode === 'quick' ? 'node-backend (port 3001)' : 'crewai-backend (port 8000)'} is running`)
      setRunning(false)
    }
  }, [running, mode, backend.http, addLog])

  return (
    <div className="flex flex-col h-screen w-screen bg-white font-mono select-none">
      <TopBar onRun={runAgents} running={running} mode={mode} onSwitchMode={switchMode} />
      <div className="flex flex-1 overflow-hidden relative">
        <Sidebar activeAgent={activeAgent} nodes={nodes} onClear={reset} />
        <Canvas nodes={nodes} edges={mode === 'quick' ? QUICK_EDGES : CANVAS_EDGES} />
        <ReportPanel report={report} onClose={() => setReport(null)} />
      </div>
      <Terminal logs={logs} />
    </div>
  )
}
