import { callGroq } from '../services/groqClient.js'

/**
 * Agent pipeline definition.
 * Each step receives (prompt, context) and returns a string output.
 */
export const PIPELINE = [
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
    run: async (prompt, ctx) =>
      callGroq(
        'You are a research analyst. Given the task and plan, provide 3-4 key research findings, data points, or insights relevant to the topic. Be specific and factual. No preamble.',
        `Task: ${prompt}\n\nPlan:\n${ctx.planner}`
      ),
  },
  {
    id: 'execution',
    label: 'Execution Agent',
    logMsg: () => '⚙️  Execution Agent processing...',
    run: async (prompt, ctx) =>
      callGroq(
        'You are an execution specialist. Based on the task, plan, and research, describe what concrete actions were taken and what was produced. Be specific. No preamble.',
        `Task: ${prompt}\n\nPlan:\n${ctx.planner}\n\nResearch:\n${ctx.research}`
      ),
  },
  {
    id: 'summary',
    label: 'Summary Agent',
    logMsg: () => '📋 Summary Agent generating final report...',
    run: async (prompt, ctx) =>
      callGroq(
        'You are a report writer. Write a concise final summary (3-5 sentences) of what was accomplished for the given task, incorporating the plan, research, and execution results. Start with "Summary:".',
        `Task: ${prompt}\n\nPlan:\n${ctx.planner}\n\nResearch:\n${ctx.research}\n\nExecution:\n${ctx.execution}`
      ),
  },
]
