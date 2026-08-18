import { useEffect, useRef } from 'react'
import type { AudioSegment } from '../../services/modalityAnnotation'

type Props = {
  url: string
  currentMs: number
  durationMs: number
  segments: AudioSegment[]
  onSeek: (ms: number) => void
}

export default function AudioWaveform({ url, currentMs, durationMs, segments, onSeek }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const peaksRef = useRef<Float32Array | null>(null)

  useEffect(() => {
    if (!url) return
    let cancelled = false
    const ac = new AudioContext()
    fetch(url)
      .then(r => r.arrayBuffer())
      .then(buf => ac.decodeAudioData(buf))
      .then(audio => {
        if (cancelled) return
        const ch = audio.getChannelData(0)
        const buckets = 480
        const peaks = new Float32Array(buckets)
        const step = Math.max(1, Math.floor(ch.length / buckets))
        for (let i = 0; i < buckets; i++) {
          let m = 0
          const start = i * step
          for (let j = 0; j < step && start + j < ch.length; j++) {
            m = Math.max(m, Math.abs(ch[start + j]))
          }
          peaks[i] = m
        }
        peaksRef.current = peaks
        draw()
      })
      .catch(() => {
        peaksRef.current = null
        draw()
      })
      .finally(() => {
        void ac.close()
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url])

  useEffect(() => {
    draw()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentMs, durationMs, segments])

  function draw() {
    const canvas = canvasRef.current
    if (!canvas) return
    const dpr = window.devicePixelRatio || 1
    const w = canvas.clientWidth
    const h = canvas.clientHeight
    canvas.width = Math.max(1, Math.floor(w * dpr))
    canvas.height = Math.max(1, Math.floor(h * dpr))
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    ctx.clearRect(0, 0, w, h)
    ctx.fillStyle = '#0a0a0f'
    ctx.fillRect(0, 0, w, h)

    if (durationMs > 0) {
      for (const s of segments) {
        const left = (s.start_ms / durationMs) * w
        const width = Math.max(2, ((s.end_ms - s.start_ms) / durationMs) * w)
        ctx.fillStyle = 'rgba(16, 185, 129, 0.22)'
        ctx.fillRect(left, 0, width, h)
      }
    }

    const peaks = peaksRef.current
    const mid = h / 2
    ctx.strokeStyle = '#10b981'
    ctx.lineWidth = 1
    ctx.beginPath()
    if (peaks && peaks.length) {
      for (let i = 0; i < peaks.length; i++) {
        const x = (i / peaks.length) * w
        const amp = peaks[i] * (h * 0.42)
        ctx.moveTo(x, mid - amp)
        ctx.lineTo(x, mid + amp)
      }
    } else {
      ctx.moveTo(0, mid)
      ctx.lineTo(w, mid)
    }
    ctx.stroke()

    if (durationMs > 0) {
      const x = (currentMs / durationMs) * w
      ctx.strokeStyle = '#fff'
      ctx.lineWidth = 1.5
      ctx.beginPath()
      ctx.moveTo(x, 0)
      ctx.lineTo(x, h)
      ctx.stroke()
    }
  }

  return (
    <canvas
      ref={canvasRef}
      className="w-full h-24 rounded-lg border border-[#1e1e2e] cursor-pointer bg-[#0a0a0f]"
      onClick={e => {
        if (durationMs <= 0) return
        const rect = e.currentTarget.getBoundingClientRect()
        const u = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width))
        onSeek(u * durationMs)
      }}
    />
  )
}
