import { createJob, getJob, listJobs, runPipeline } from '../services/agentPipeline.js'
import { eventStream } from '../utils/eventStream.js'
import { logger } from '../utils/logger.js'
import config from '../config/config.js'

export function postRunTask(req, res) {
  const { prompt } = req.body
  if (!prompt?.trim()) {
    return res.status(400).json({ error: 'prompt is required' })
  }

  const jobId = `job_${Date.now()}`
  createJob(jobId, prompt.trim())

  runPipeline(jobId, prompt.trim()).catch((err) => {
    logger.error('Pipeline error:', err.message)
    const job = getJob(jobId)
    if (job) job.status = 'failed'
    eventStream.broadcast({ type: 'error', jobId, message: err.message })
  })

  res.status(202).json({ jobId, status: 'queued' })
}

export function getStatus(req, res) {
  res.json({ jobs: listJobs(), connectedClients: eventStream.size })
}

export function getJobStatus(req, res) {
  const job = getJob(req.params.jobId)
  if (!job) return res.status(404).json({ error: 'Job not found' })
  res.json(job)
}

export function getHealth(req, res) {
  res.json({
    status: 'ok',
    jobs: listJobs().length,
    clients: eventStream.size,
    groqConfigured: !!config.groqApiKey,
  })
}
