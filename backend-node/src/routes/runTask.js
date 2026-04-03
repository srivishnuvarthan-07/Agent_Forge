import { Router } from 'express'
import { postRunTask, getStatus, getJobStatus, getHealth } from '../controllers/agentController.js'

const router = Router()

router.post('/run-task',        postRunTask)
router.get('/status',           getStatus)
router.get('/status/:jobId',    getJobStatus)
router.get('/health',           getHealth)

export default router
