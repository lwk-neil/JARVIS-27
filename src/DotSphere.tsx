import { useEffect, useRef } from 'react'

type DotSphereProps = {
  className?: string
  density?: number
}

export function DotSphere({ className = '', density = 1900 }: DotSphereProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    const context = canvas?.getContext('2d')
    if (!canvas || !context) return

    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)')
    let width = 0
    let height = 0
    let frame = 0
    let animationFrame = 0
    let dpr = 1

    const resize = () => {
      const rect = canvas.getBoundingClientRect()
      width = rect.width
      height = rect.height
      dpr = Math.min(window.devicePixelRatio || 1, 2)
      canvas.width = Math.round(width * dpr)
      canvas.height = Math.round(height * dpr)
      context.setTransform(dpr, 0, 0, dpr, 0, 0)
    }

    const render = () => {
      context.clearRect(0, 0, width, height)
      const cx = width * 0.5
      const cy = height * 0.5
      const radius = Math.min(width, height) * 0.385
      const count = Math.max(700, Math.round(density * Math.min(1, width / 420)))
      const rotation = frame * 0.0019
      const pulse = 1 + Math.sin(frame * 0.027) * 0.012
      const phi = Math.PI * (3 - Math.sqrt(5))

      for (let i = 0; i < count; i += 1) {
        const y = 1 - (i / (count - 1)) * 2
        const ring = Math.sqrt(1 - y * y)
        const theta = phi * i + rotation
        const x = Math.cos(theta) * ring
        const z = Math.sin(theta) * ring
        const light = Math.max(0, (z + x * 0.2 + 0.22) / 1.22)
        const wave = Math.sin(theta * 2.4 + y * 8 - frame * 0.016) * 1.8
        const depth = 0.62 + Math.max(0, z) * 0.38
        const px = cx + x * (radius * pulse + wave)
        const py = cy + y * (radius * pulse + wave)
        const blend = Math.min(1, Math.max(0, x * 0.5 + 0.5))
        const red = Math.round(231 + blend * 24)
        const green = Math.round(48 + blend * 93)
        const blue = Math.round(144 - blend * 120)
        const alpha = Math.min(1, (0.25 + light * 0.8) * depth)
        const dotRadius = (0.8 + light * 0.5) * (width < 380 ? 0.82 : 1)

        context.beginPath()
        context.fillStyle = `rgba(${red}, ${green}, ${blue}, ${alpha})`
        context.arc(px, py, dotRadius, 0, Math.PI * 2)
        context.fill()
      }

      frame += 1
      if (!reducedMotion.matches) {
        animationFrame = window.requestAnimationFrame(render)
      }
    }

    resize()
    render()
    const observer = new ResizeObserver(() => {
      resize()
      window.cancelAnimationFrame(animationFrame)
      animationFrame = window.requestAnimationFrame(render)
    })
    observer.observe(canvas)
    const onMotionChange = () => {
      window.cancelAnimationFrame(animationFrame)
      if (!reducedMotion.matches) animationFrame = window.requestAnimationFrame(render)
      else render()
    }
    reducedMotion.addEventListener('change', onMotionChange)

    return () => {
      window.cancelAnimationFrame(animationFrame)
      observer.disconnect()
      reducedMotion.removeEventListener('change', onMotionChange)
    }
  }, [density])

  return (
    <canvas
      ref={canvasRef}
      className={`dot-sphere ${className}`}
      aria-hidden="true"
    />
  )
}
