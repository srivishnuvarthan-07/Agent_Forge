import https from 'https'
import config from '../config/config.js'

/**
 * Makes a single chat completion call to the Groq API.
 */
export function callGroq(systemPrompt, userMessage) {
  return new Promise((resolve, reject) => {
    const body = JSON.stringify({
      model: config.groqModel,
      messages: [
        { role: 'system', content: systemPrompt },
        { role: 'user',   content: userMessage },
      ],
      max_tokens: 300,
      temperature: 0.7,
    })

    const req = https.request(
      {
        hostname: 'api.groq.com',
        path: '/openai/v1/chat/completions',
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${config.groqApiKey}`,
          'Content-Length': Buffer.byteLength(body),
        },
      },
      (res) => {
        let data = ''
        res.on('data', (chunk) => (data += chunk))
        res.on('end', () => {
          try {
            const parsed = JSON.parse(data)
            if (parsed.error) return reject(new Error(parsed.error.message))
            resolve(parsed.choices[0].message.content.trim())
          } catch {
            reject(new Error('Failed to parse Groq response'))
          }
        })
      }
    )

    req.on('error', reject)
    req.write(body)
    req.end()
  })
}
