/**
 * HerdDots.jsx — HERD 군중 점 애니메이션 컴포넌트
 *
 * score에 따라 군중의 분포와 밀도를 다르게 표현한다.
 * Flee=군중 이탈, Scatter=군중 흩어짐, Calm=군중 균형, Drift=군중 쏠림, Rush=군중 밀집.
 *
 * fill=true: 부모 컨테이너를 꽉 채우는 모드 (배너, 테이블 행에서 사용)
 * fill=false: 고정 width/height 모드 (기본값)
 */

import { useRef, useEffect } from 'react'
import {
  advanceHerdDot,
  createHerdDots,
  herdDotColor,
  herdFlowProfile,
} from './herdDotsModel'

/**
 * @param {number}  score     HERD 점수 (0~100)
 * @param {number}  width     캔버스 CSS 너비 (fill=false일 때 사용)
 * @param {number}  height    캔버스 CSS 높이 (fill=false일 때 사용)
 * @param {number}  dotCount  점 개수
 * @param {boolean} fill      true: 부모 컨테이너 채움 / false: 고정 크기
 */
export default function HerdDots({
  score    = 50,
  width    = 200,
  height   = 100,
  dotCount = 20,
  fill     = false,
  enhanced = false,
  momentum = 0,
  actionRatio = 0,
}) {
  const canvasRef = useRef(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx     = canvas.getContext('2d')
    if (!ctx) return
    const dpr     = window.devicePixelRatio || 1
    const color   = herdDotColor(score)
    const profile = herdFlowProfile(score)
    const cluster = score / 100          // 0(Flee) → 1(Rush)
    const direction = Math.max(-20, Math.min(20, momentum)) / 20
    const activeRatio = Math.max(0, Math.min(1, actionRatio))
    const reduceMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

    let dots = []
    let rafId
    let tick = 0

    /* 점 배열 초기화 */
    function initDots() {
      return createHerdDots({ dotCount, profile, score, dpr, activeRatio })
    }

    /* 캔버스 물리 픽셀 크기 설정 (fill 모드 vs 고정 모드) */
    function resize() {
      if (fill) {
        /* fill 모드: 부모 CSS 크기를 실제 픽셀로 변환 */
        canvas.width  = (canvas.offsetWidth  || 1) * dpr
        canvas.height = (canvas.offsetHeight || 1) * dpr
      } else {
        /* 고정 모드: props width/height 그대로 사용 */
        canvas.width  = width  * dpr
        canvas.height = height * dpr
      }
    }

    /* 애니메이션 루프 */
    function draw() {
      tick += reduceMotion ? 0 : 1
      const W = canvas.width
      const H = canvas.height
      ctx.clearRect(0, 0, W, H)

      dots.forEach(d => {
        advanceHerdDot(d, { profile, tick, enhanced, direction })

        const trailAlpha = enhanced
          ? Math.max(profile.trail, Math.abs(direction) * 0.13)
          : profile.trail
        if (trailAlpha > 0 && d.prevX != null) {
          ctx.beginPath()
          ctx.moveTo(d.prevX * W, d.prevY * H)
          ctx.lineTo(d.x * W, d.y * H)
          ctx.strokeStyle = color
          ctx.globalAlpha = trailAlpha
          ctx.lineWidth = Math.max(1, d.r * 0.45)
          ctx.stroke()
          ctx.globalAlpha = 1
        }

        if (enhanced && d.active) {
          const pulse = 1 + Math.sin(tick * 0.045 + d.phase) * 0.18
          ctx.beginPath()
          ctx.arc(d.x * W, d.y * H, d.r * 2.8 * pulse, 0, Math.PI * 2)
          ctx.strokeStyle = color
          ctx.lineWidth = Math.max(1, d.r * 0.3)
          ctx.globalAlpha = 0.18
          ctx.stroke()
        }

        ctx.beginPath()
        ctx.arc(d.x * W, d.y * H, d.r * (d.active ? 1.12 : 1), 0, Math.PI * 2)
        ctx.fillStyle   = color
        ctx.globalAlpha = profile.alpha + cluster * 0.08
        ctx.fill()
        ctx.globalAlpha = 1
      })

      if (!reduceMotion) rafId = requestAnimationFrame(draw)
    }

    /* 초기 설정 및 시작 */
    resize()
    dots = initDots()
    draw()

    /* fill 모드: 컨테이너 리사이즈 감지 */
    let ro
    if (fill) {
      ro = new ResizeObserver(() => {
        resize()
        dots = initDots()
      })
      ro.observe(canvas)
    }

    /* 언마운트 또는 props 변경 시 정리 */
    return () => {
      cancelAnimationFrame(rafId)
      if (ro) ro.disconnect()
    }
  }, [score, width, height, dotCount, fill, enhanced, momentum, actionRatio])

  /* fill 모드: position:absolute로 부모를 꽉 채움 */
  if (fill) {
    return (
      <canvas
        ref={canvasRef}
        style={{
          position: 'absolute',
          inset:    0,
          width:    '100%',
          height:   '100%',
          display:  'block',
        }}
      />
    )
  }

  /* 고정 모드 */
  return (
    <canvas
      ref={canvasRef}
      style={{
        width,
        height,
        display:      'block',
        borderRadius: 6,
      }}
    />
  )
}
