/**
 * Simple WebSocket broadcast manager.
 * Tracks connected clients and provides a broadcast helper.
 */
export class EventStream {
  constructor() {
    this.clients = new Set()
  }

  add(ws) {
    this.clients.add(ws)
    ws.on('close', () => this.clients.delete(ws))
    ws.on('error', () => this.clients.delete(ws))
  }

  broadcast(msg) {
    const text = JSON.stringify(msg)
    for (const ws of this.clients) {
      if (ws.readyState === 1) ws.send(text)
    }
  }

  get size() {
    return this.clients.size
  }
}

export const eventStream = new EventStream()
