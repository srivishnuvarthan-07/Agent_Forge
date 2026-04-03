import React, { useState, useRef, useEffect, useCallback } from 'react'
import Sidebar from './components/Sidebar'
import TopBar from './components/TopBar'
import Canvas from './components/Canvas'
import Terminal from './components/Terminal'
import ReportPanel from './components/ReportPanel'

const INITIAL_NODES = [
  { id: 'prompt',    label: 'User Prompt',  icon: '💬', status: 'idle', output: '', x: 80,  y: 180 },
  { id: 'planner',   label: 'Planner',      icon: '🗂️', status: 'idle', output: '', x: 280, y: 180 },
  { id: 'research',  label: 'Research',     icon: '🔍', status: 'idle', output: '', x: 480, y: 180 },
  { id: 'execution', label: 'Execution',    icon: '⚙️', status: 'idle', output: '', x: 680, y: 180 },
  { id: 'summary',   label: 'Summary',      icon: '📋', status: 'idle', output: '', x: 880, y: 180 },
]

const EDGES = [
  { from: 'prompt',    to: 'planner'   },
  { from: 'planner',   to: 'research'  },
  { from: 'research',  to: 'execution' },
  { from: 'execution', to: 'summary'   },
]

const API = 'http://localhost:3001'
const WS_URL = 'ws://localhost:3001'

export default function App() {
  const [nodes, setNodes] = useState(INITIAL_NODES)
  const [logs, setLogs] = useState(['AgentForge ready. Enter a task and click Run Agents.'])
  const [running, setRunning] = useState(false)
  const [activeAgent, setActiveAgent] = useState(null)
  const [report, setReport] = useState(null)
  const wsRef = useRef(null)
  const taskRef = useRef('')
  const fullOutputs = useRef({})

  const addLog = useCallback((msg) => setLogs(prev => [...prev, msg]), [])

  useEffect(() => {
    let ws
    let reconnectTimer

    function connect() {
      ws = new WebSocket(WS_URL)
      wsRef.current = ws

      ws.onopen = () => addLog('🔌 Connected to AgentForge backend')

      ws.onmessage = (e) => {
        const msg = JSON.parse(e.data)
        if (msg.type === 'connected') {
          // handshake
        } else if (msg.type === 'job_started') {
          addLog(`▶ Pipeline started for: "${msg.prompt}"`)
        } else if (msg.type === 'agent_started') {
          setActiveAgent(msg.agentId)
          setNodes(prev => prev.map(n => n.id === msg.agentId ? { ...n, status: 'running' } : n))
          addLog(msg.log || `⚡ ${msg.label} running...`)
        } else if (msg.type === 'agent_completed') {
          fullOutputs.current[msg.agentId] = msg.output
          setNodes(prev => prev.map(n =>
            n.id === msg.agentId ? { ...n, status: 'completed', output: msg.output } : n
          ))
          setActiveAgent(null)
          addLog(msg.log || `✓ ${msg.label} done`)
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

      ws.onerror = () => addLog('⚠ WebSocket error — is the backend running on port 3001?')
      ws.onclose = () => {
        addLog('🔌 Disconnected. Retrying in 3s...')
        reconnectTimer = setTimeout(connect, 3000)
      }
    }

    connect()
    return () => { clearTimeout(reconnectTimer); ws?.close() }
  }, [addLog])

  const reset = useCallback(() => {
    setNodes(INITIAL_NODES)
    setLogs(['Canvas cleared. Ready for new task.'])
    setActiveAgent(null)
    setReport(null)
    fullOutputs.current = {}
  }, [])

  const runAgents = useCallback(async (task) => {
    if (running || !task.trim()) return
    setRunning(true)
    setNodes(INITIAL_NODES)
    setReport(null)
    fullOutputs.current = {}
    taskRef.current = task
    setLogs([`▶ Submitting task: "${task}"`])

    try {
      const res = await fetch(`${API}/run-task`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: task }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      addLog(`📋 Job queued: ${data.jobId}`)
    } catch (err) {
      addLog(`❌ Failed to reach backend: ${err.message}`)
      addLog('Make sure the backend is running: cd backend-node && npm start')
      setRunning(false)
    }
  }, [running, addLog])

  return (
    <div className="flex flex-col h-screen w-screen bg-white font-mono select-none">
      <TopBar onRun={runAgents} running={running} />
      <div className="flex flex-1 overflow-hidden relative">
        <Sidebar activeAgent={activeAgent} nodes={nodes} onClear={reset} />
        <Canvas nodes={nodes} edges={EDGES} />
        <ReportPanel report={report} onClose={() => setReport(null)} />
      </div>
      <Terminal logs={logs} />
    </div>
  )
}