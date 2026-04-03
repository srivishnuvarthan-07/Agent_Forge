import React, { useRef, useState, useCallback } from 'react'
import AgentNode from './AgentNode'

const NODE_W = 160
const NODE_H = 90

export default function Canvas({ nodes, edges }) {
  const svgRef = useRef(null)
  const [offset, setOffset] = useState({ x: 0, y: 0 })
  const [scale, setScale] = useState(1)
  const dragging = useRef(false)
  const lastPos = useRef({ x: 0, y: 0 })

  // Pan
  const onMouseDown = useCallback(e => {
    if (e.target.closest('.agent-node')) return
    dragging.current = true
    lastPos.current = { x: e.clientX, y: e.clientY }
  }, [])

  const onMouseMove = useCallback(e => {
    if (!dragging.current) return
    const dx = e.clientX - lastPos.current.x
    const dy = e.clientY - lastPos.current.y
    lastPos.current = { x: e.clientX, y: e.clientY }
    setOffset(o => ({ x: o.x + dx, y: o.y + dy }))
  }, [])

  const onMouseUp = useCallback(() => { dragging.current = false }, [])

  // Zoom
  const onWheel = useCallback(e => {
    e.preventDefault()
    setScale(s => Math.min(2, Math.max(0.3, s - e.deltaY * 0.001)))
  }, [])

  // Edge midpoints for arrows
  const nodeMap = Object.fromEntries(nodes.map(n => [n.id, n]))

  return (
    <div
      className="flex-1 relative overflow-hidden bg-white cursor-grab active:cursor-grabbing"
      onMouseDown={onMouseDown}
      onMouseMove={onMouseMove}
      onMouseUp={onMouseUp}
      onMouseLeave={onMouseUp}
      onWheel={onWheel}
      style={{ backgroundImage: 'radial-gradient(circle, #d1d5db 1px, transparent 1px)', backgroundSize: '28px 28px' }}
    >
      {/* Zoom hint */}
      <div className="absolute top-3 right-3 text-xs text-gray-400 bg-white/80 px-2 py-1 rounded border border-gray-200 z-10">
        Scroll to zoom · Drag to pan · {Math.round(scale * 100)}%
      </div>

      {/* SVG edges */}
      <svg
        className="absolute inset-0 w-full h-full pointer-events-none"
        style={{ zIndex: 0 }}
      >
        <g transform={`translate(${offset.x},${offset.y}) scale(${scale})`}>
          <defs>
            <marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
              <path d="M0,0 L0,6 L8,3 z" fill="#9ca3af" />
            </marker>
          </defs>
          {edges.map(e => {
            const from = nodeMap[e.from]
            const to   = nodeMap[e.to]
            if (!from || !to) return null
            const x1 = from.x + NODE_W
            const y1 = from.y + NODE_H / 2
            const x2 = to.x
            const y2 = to.y + NODE_H / 2
            const mx = (x1 + x2) / 2
            return (
              <path
                key={`${e.from}-${e.to}`}
                d={`M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`}
                fill="none"
                stroke="#9ca3af"
                strokeWidth="1.5"
                markerEnd="url(#arrow)"
              />
            )
          })}
        </g>
      </svg>

      {/* Nodes */}
      <div
        className="absolute inset-0"
        style={{ transform: `translate(${offset.x}px,${offset.y}px) scale(${scale})`, transformOrigin: '0 0', zIndex: 1 }}
      >
        {nodes.map(node => (
          <AgentNode key={node.id} node={node} width={NODE_W} height={NODE_H} />
        ))}
      </div>
    </div>
  )
}
