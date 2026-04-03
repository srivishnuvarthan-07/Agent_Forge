import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'
import { config } from 'dotenv'

const __dirname = dirname(fileURLToPath(import.meta.url))
config({ path: resolve(__dirname, '../../../.env') })

export default {
  port: process.env.PORT || 3001,
  groqApiKey: process.env.GROQ_API_KEY,
  groqModel: 'llama-3.1-8b-instant',
}
