import express from 'express'
import cors from 'cors'
import { createServer } from 'http'
import { WebSocketServer } from 'ws'
import config from './config/config.js'
import { eventStream } from './utils/eventStream.js'
import { logger } from './utils/logger.js'
import routes from './routes/runTask.js'

const app = express()
app.use(cors())
app.use(express.json())
app.use(routes)

const httpServer = createServer(app)
const wss = new WebSocketServer({ server: httpServer })

wss.on('connection', (ws) => {
  eventStream.add(ws)
  ws.send(JSON.stringify({ type: 'connected', message: 'AgentForge backend connected' }))
})

httpServer.listen(config.port, () => {
  logger.info(`AgentForge backend  →  http://localhost:${config.port}`)
  logger.info(`WebSocket           →  ws://localhost:${config.port}`)
  logger.info(`Groq API key        →  ${config.groqApiKey ? '✓ configured' : '✗ MISSING — set GROQ_API_KEY in .env'}`)
})
