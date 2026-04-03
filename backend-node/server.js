import express from 'express'
import cors from 'cors'
import { createServer } from 'http'
import { WebSocketServer } from 'ws'
import https from 'https'
import { config } from 'dotenv'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))
// Load .env from workspace root (one level up from backend-node/)
config({ path: resolve(__dirname, '../.env') })

const app = express()
app.use(cors())
app.use(express.json())

const httpServer = createServer(app)
const wss = new WebSocketServer({ server: httpServer })

// ── WebSocket clients ─────────────────────────────────────────────────────────
const clients = new Set()

wss.on('connection', (ws) => {
  clients.add(ws)
  ws.send(JSON.stringify({ type: 'connected', message: 'AgentForge backend connected' }))
  ws.on('close', () => clients.delete(ws))
  ws.on('error', () => clients.delete(ws))
})

function broadcast(msg) {
  const text = JSON.stringify(msg)
  for (const ws of clients) {
    if (ws.readyState === 1) ws.send(text)
  }
}

// ── Groq LLM call ─────────────────────────────────────────────────────────────
const GROQ_API_KEY = process.env.GROQ_API_KEY
const GROQ_MODEL = 'llama-3.1-8b-instant'

function callGroq(systemPrompt, userMessage) {
  return new Promise((resolve, reject) => {
    const body = JSON.stringify({
      model: GROQ_MODEL,
      messages: [
        { role: 'system', content: systemPrompt },
        { role: 'user', content: userMessage },
      ],
      max_tokens: 300,
      temperature: 0.7,
    })

    const options = {
      hostname: 'api.groq.com',
      path: '/openai/v1/chat/completions',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${GROQ_API_KEY}`,
        'Content-Length': Buffer.byteLength(body),
      },
    }

    const req = https.request(options, (res) => {
      let data = ''
      res.on('data', (chunk) => (data += chunk))
      res.on('end', () => {
        try {
          const parsed = JSON.parse(data)
          if (parsed.error) return reject(new Error(parsed.error.message))
          resolve(parsed.choices[0].message.content.trim())
        } catch (e) {
          reject(new Error('Failed to parse Groq response'))
        }
      })
    })

    req.on('error', reject)
    req.write(body)
    req.end()
  })
}

// ── Agent definitions ─────────────────────────────────────────────────────────
const PIPELINE = [
  {
    id: 'prompt',
    label: 'User Prompt',
    logMsg: (p) => `📥 Received task: "${p}"`,
    run: async (prompt) => `Task received: "${prompt}"`,
  },
  {
    id: 'planner',
    label: 'Planner Agent',
    logMsg: () => '🗂️  Planner breaking task into steps...',
    run: async (prompt) =>
      callGroq(
        'You are a task planner. Break the user task into 3-5 clear, numbered action steps. Be concise and specific to the task. No preamble.',
        prompt
      ),
  },
  {
    id: 'research',
    label: 'Research Agent',
    logMsg: () => '🔍 Research Agent gathering insights...',
    run: async (prompt, context) =>
      callGroq(
        'You are a research analyst. Given the task and plan, provide 3-4 key research findings, data points, or insights relevant to the topic. Be specific and factual. No preamble.',
        `Task: ${prompt}\n\nPlan:\n${context.planner}`
      ),
  },
  {
    id: 'execution',
    label: 'Execution Agent',
    logMsg: () => '⚙️  Execution Agent processing...',
    run: async (prompt, context) =>
      callGroq(
        'You are an execution specialist. Based on the task, plan, and research, describe what concrete actions were taken and what was produced. Be specific. No preamble.',
        `Task: ${prompt}\n\nPlan:\n${context.planner}\n\nResearch:\n${context.research}`
      ),
  },
  {
    id: 'summary',
    label: 'Summary Agent',
    logMsg: () => '📋 Summary Agent generating final report...',
    run: async (prompt, context) =>
      callGroq(
        'You are a report writer. Write a concise final summary (3-5 sentences) of what was accomplished for the given task, incorporating the plan, research, and execution results. Start with "Summary:".',
        `Task: ${prompt}\n\nPlan:\n${context.planner}\n\nResearch:\n${context.research}\n\nExecution:\n${context.execution}`
      ),
  },
]

// ── Pipeline runner ───────────────────────────────────────────────────────────
const jobs = new Map()

async function runPipeline(jobId, prompt) {
  const job = jobs.get(jobId)
  job.status = 'running'
  const context = {}

  broadcast({ type: 'job_started', jobId, prompt })

  for (const step of PIPELINE) {
    job.agentStatuses[step.id] = 'running'
    broadcast({
      type: 'agent_started',
      jobId,
      agentId: step.id,
      label: step.label,
      log: step.logMsg(prompt),
    })

    try {
      const output = await step.run(prompt, context)
      context[step.id] = output
      job.agentStatuses[step.id] = 'completed'
      job.outputs[step.id] = output

      broadcast({
        type: 'agent_completed',
        jobId,
        agentId: step.id,
        label: step.label,
        output,
        log: `✓ ${step.label} completed`,
      })
    } catch (err) {
      const errMsg = `Error in ${step.label}: ${err.message}`
      job.agentStatuses[step.id] = 'completed'
      job.outputs[step.id] = errMsg
      context[step.id] = errMsg
      broadcast({
        type: 'agent_completed',
        jobId,
        agentId: step.id,
        label: step.label,
        output: errMsg,
        log: `⚠ ${step.label} encountered an error`,
      })
    }

    // Small pause between agents for visual clarity
    await new Promise((r) => setTimeout(r, 400))
  }

  job.status = 'completed'
  job.result = job.outputs.summary
  job.completedAt = new Date().toISOString()

  broadcast({
    type: 'crew_finished',
    jobId,
    result: job.result,
    outputs: job.outputs,
    log: '✅ All agents completed. Report ready.',
  })
}

// ── REST Endpoints ────────────────────────────────────────────────────────────
app.post('/run-task', (req, res) => {
  const { prompt } = req.body
  if (!prompt || !prompt.trim()) {
    return res.status(400).json({ error: 'prompt is required' })
  }

  const jobId = `job_${Date.now()}`
  jobs.set(jobId, {
    jobId,
    prompt,
    status: 'queued',
    agentStatuses: {},
    outputs: {},
    result: null,
    createdAt: new Date().toISOString(),
    completedAt: null,
  })

  runPipeline(jobId, prompt.trim()).catch((err) => {
    const job = jobs.get(jobId)
    if (job) job.status = 'failed'
    broadcast({ type: 'error', jobId, message: err.message })
  })

  res.status(202).json({ jobId, status: 'queued' })
})

app.get('/status', (req, res) => {
  const all = [...jobs.values()].map((j) => ({
    jobId: j.jobId,
    prompt: j.prompt,
    status: j.status,
    agentStatuses: j.agentStatuses,
    createdAt: j.createdAt,
    completedAt: j.completedAt,
  }))
  res.json({ jobs: all, connectedClients: clients.size })
})

app.get('/status/:jobId', (req, res) => {
  const job = jobs.get(req.params.jobId)
  if (!job) return res.status(404).json({ error: 'Job not found' })
  res.json(job)
})

app.get('/health', (req, res) => {
  res.json({ status: 'ok', jobs: jobs.size, clients: clients.size, groqConfigured: !!GROQ_API_KEY })
})

// ── Start ─────────────────────────────────────────────────────────────────────
const PORT = process.env.PORT || 3001
httpServer.listen(PORT, () => {
  console.log(`AgentForge backend  →  http://localhost:${PORT}`)
  console.log(`WebSocket           →  ws://localhost:${PORT}`)
  console.log(`Groq API key        →  ${GROQ_API_KEY ? '✓ configured' : '✗ MISSING — set GROQ_API_KEY in .env'}`)
})
