import { PIPELINE } from '../agents/index.js'
import { eventStream } from '../utils/eventStream.js'
import { logger } from '../utils/logger.js'

const jobs = new Map()

export function createJob(jobId, prompt) {
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
  return jobs.get(jobId)
}

export function getJob(jobId) {
  return jobs.get(jobId) ?? null
}

export function listJobs() {
  return [...jobs.values()].map(({ jobId, prompt, status, agentStatuses, createdAt, completedAt }) => ({
    jobId, prompt, status, agentStatuses, createdAt, completedAt,
  }))
}

export async function runPipeline(jobId, prompt) {
  const job = jobs.get(jobId)
  job.status = 'running'
  const context = {}

  eventStream.broadcast({ type: 'job_started', jobId, prompt })

  for (const step of PIPELINE) {
    job.agentStatuses[step.id] = 'running'
    eventStream.broadcast({
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
      eventStream.broadcast({
        type: 'agent_completed',
        jobId,
        agentId: step.id,
        label: step.label,
        output,
        log: `✓ ${step.label} completed`,
      })
    } catch (err) {
      logger.error(`Agent ${step.id} failed:`, err.message)
      const errMsg = `Error in ${step.label}: ${err.message}`
      job.agentStatuses[step.id] = 'completed'
      job.outputs[step.id] = errMsg
      context[step.id] = errMsg
      eventStream.broadcast({
        type: 'agent_completed',
        jobId,
        agentId: step.id,
        label: step.label,
        output: errMsg,
        log: `⚠ ${step.label} encountered an error`,
      })
    }

    await new Promise((r) => setTimeout(r, 400))
  }

  job.status = 'completed'
  job.result = job.outputs.summary
  job.completedAt = new Date().toISOString()

  eventStream.broadcast({
    type: 'crew_finished',
    jobId,
    result: job.result,
    outputs: job.outputs,
    log: '✅ All agents completed. Report ready.',
  })
}
