/**
 * HerdDots.jsx — HERD 무리 점 애니메이션 컴포넌트
 *
 * score에 따라 군중의 흐름을 다르게 표현한다.
 * Flee=무리 이탈, Scatter=흩어짐, Calm=균형, Drift=쏠림, Rush=밀집.
 *
 * fill=true: 부모 컨테이너를 꽉 채우는 모드 (배너, 테이블 행에서 사용)
 * fill=false: 고정 width/height 모드 (기본값)
 */

import { useRef, useEffect } from 'react'

/** score 구간별 HERD 색상 반환 */
function getColor(score) {
  if (score >= 75) return '#EF4444'  // Rush  — 레드
  if (score >= 60) return '#F97316'  // Drift — 오렌지
  if (score >= 40) return '#71717A'  // Calm  — 회색
  if (score >= 15) return '#60A5FA'  // Scatter — 연파랑
  return '#3B82F6'                   // Flee  — 파랑
}

function getFlowProfile(score) {
  if (score >= 75) {
    return {
      anchorX: 0.82,
      anchorY: 0.5,
      spreadX: 0.12,
      spreadY: 0.32,
      pull: 0.00135,
      drift: 0.00042,
      jitter: 0.00008,
      maxV: 0.0056,
      alpha: 0.86,
      trail: 0.16,
    }
  }
  if (score >= 60) {
    return {
      anchorX: 0.66,
      anchorY: 0.5,
      spreadX: 0.24,
      spreadY: 0.42,
      pull: 0.00078,
      drift: 0.00022,
      jitter: 0.00012,
      maxV: 0.0042,
      alpha: 0.72,
      trail: 0.1,
    }
  }
  if (score >= 40) {
    return {
      anchorX: 0.5,
      anchorY: 0.5,
      spreadX: 0.34,
      spreadY: 0.48,
      pull: 0.0005,
      drift: 0,
      jitter: 0.00012,
      maxV: 0.0026,
      alpha: 0.56,
      trail: 0,
    }
  }
  if (score >= 15) {
    return {
      anchorX: 0.36,
      anchorY: 0.5,
      spreadX: 0.48,
      spreadY: 0.62,
      pull: 0.00042,
      drift: -0.00016,
      jitter: 0.00028,
      maxV: 0.0038,
      alpha: 0.62,
      trail: 0.04,
    }
  }
  return {
    anchorX: 0.18,
    anchorY: 0.5,
    spreadX: 0.62,
    spreadY: 0.74,
    pull: 0.00035,
    drift: -0.00036,
    jitter: 0.00038,
    maxV: 0.0048,
    alpha: 0.68,
    trail: 0.1,
  }
}

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
}) {
  const canvasRef = useRef(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx     = canvas.getContext('2d')
    const dpr     = window.devicePixelRatio || 1
    const color   = getColor(score)
    const profile = getFlowProfile(score)
    const cluster = score / 100          // 0(Flee) → 1(Rush)

    let dots = []
    let rafId
    let tick = 0

    /* 점 배열 초기화 */
    function initDots() {
      return Array.from({ length: dotCount }, () => ({
        x:  Math.max(0.02, Math.min(0.98, profile.anchorX + (Math.random() - 0.5) * profile.spreadX)),
        y:  Math.max(0.08, Math.min(0.92, profile.anchorY + (Math.random() - 0.5) * profile.spreadY)),
        vx: (Math.random() - 0.5) * 0.0025,
        vy: (Math.random() - 0.5) * 0.0025,
        phase: Math.random() * Math.PI * 2,
        orbit: 0.4 + Math.random() * 0.8,
        /* 물리 픽셀 기준 반지름 */
        r:  (1.1 + Math.random() * (score >= 75 ? 2.6 : 2)) * dpr,
      }))
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
      tick += 1
      const W = canvas.width
      const H = canvas.height
      ctx.clearRect(0, 0, W, H)

      dots.forEach(d => {
        const waveX = Math.sin(tick * 0.012 + d.phase) * 0.018 * d.orbit
        const waveY = Math.cos(tick * 0.01 + d.phase) * 0.028 * d.orbit
        const targetX = profile.anchorX + waveX
        const targetY = profile.anchorY + waveY
        const noiseX = (Math.random() - 0.5) * profile.jitter
        const noiseY = (Math.random() - 0.5) * profile.jitter

        d.prevX = d.x
        d.prevY = d.y

        /* Flee는 바깥으로 이탈, Rush는 한쪽으로 밀집되는 흐름을 더한다. */
        d.vx += (targetX - d.x) * profile.pull + profile.drift + noiseX
        d.vy += (targetY - d.y) * profile.pull * 0.72 + noiseY

        d.x += d.vx
        d.y += d.vy

        /* 경계 처리: Flee는 화면 가장자리에서 다시 흩어지고, Rush는 밀집권 안으로 되돌아온다. */
        if (d.x < 0.01) {
          d.x = 0.01
          d.vx = Math.abs(d.vx) * (score < 40 ? 0.25 : 0.55)
        }
        if (d.x > 0.99) {
          d.x = 0.99
          d.vx = -Math.abs(d.vx) * (score >= 60 ? 0.35 : 0.55)
        }
        if (d.y < 0.04 || d.y > 0.96) d.vy *= -0.65

        /* 최대 속도 제한 */
        const spd = Math.hypot(d.vx, d.vy)
        if (spd > profile.maxV) {
          d.vx = (d.vx / spd) * profile.maxV
          d.vy = (d.vy / spd) * profile.maxV
        }

        if (profile.trail > 0 && d.prevX != null) {
          ctx.beginPath()
          ctx.moveTo(d.prevX * W, d.prevY * H)
          ctx.lineTo(d.x * W, d.y * H)
          ctx.strokeStyle = color
          ctx.globalAlpha = profile.trail
          ctx.lineWidth = Math.max(1, d.r * 0.45)
          ctx.stroke()
          ctx.globalAlpha = 1
        }

        ctx.beginPath()
        ctx.arc(d.x * W, d.y * H, d.r, 0, Math.PI * 2)
        ctx.fillStyle   = color
        ctx.globalAlpha = profile.alpha + cluster * 0.08
        ctx.fill()
        ctx.globalAlpha = 1
      })

      rafId = requestAnimationFrame(draw)
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
  }, [score, width, height, dotCount, fill])

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
