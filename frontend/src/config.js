// Backend endpoints — swap these if you change ports
export const BACKENDS = {
  quick: {
    http: 'http://localhost:3001',
    ws:   'ws://localhost:3001',      // node-backend: WS at root path
  },
  canvas: {
    http: 'http://localhost:8000',
    ws:   'ws://localhost:8000/ws',   // crewai-backend: WS at /ws
  },
}
