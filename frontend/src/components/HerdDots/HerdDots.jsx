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
import { HERD_STAGE_THRESHOLDS } from '../../utils/herdStage'

/** score 구간별 HERD 색상 반환 */
function getColor(score) {
  if (score >= HERD_STAGE_THRESHOLDS.rush) return '#EF4444'  // Rush  — 레드
  if (score >= HERD_STAGE_THRESHOLDS.drift) return '#F97316' // Drift — 오렌지
  if (score > HERD_STAGE_THRESHOLDS.scatter) return '#A3AAB8' // Calm  — 회색
  if (score > HERD_STAGE_THRESHOLDS.flee) return '#60A5FA'    // Scatter — 연파랑
  return '#3B82F6'                   // Flee  — 파랑
}

function getFlowProfile(score) {
  if (score >= HERD_STAGE_THRESHOLDS.rush) {
    return {
      mode: 'cluster',
      anchorX: 0.78,
      anchorY: 0.5,
      spreadX: 0.08,
      spreadY: 0.16,
      pull: 0.0011,
      jitter: 0.00008,
      maxV: 0.0038,
      alpha: 0.86,
      trail: 0.08,
    }
  }
  if (score >= HERD_STAGE_THRESHOLDS.drift) {
    return {
      mode: 'drift',
      anchorX: 0.66,
      anchorY: 0.5,
      spreadX: 0.22,
      spreadY: 0.34,
      pull: 0.00072,
      jitter: 0.00012,
      maxV: 0.0032,
      alpha: 0.72,
      trail: 0.04,
    }
  }
  if (score > HERD_STAGE_THRESHOLDS.scatter) {
    return {
      mode: 'calm',
      anchorX: 0.5,
      anchorY: 0.5,
      spreadX: 0.34,
      spreadY: 0.48,
      pull: 0.0005,
      jitter: 0.00012,
      maxV: 0.0026,
      alpha: 0.56,
      trail: 0,
    }
  }
  if (score > HERD_STAGE_THRESHOLDS.flee) {
    return {
      mode: 'scatter',
      anchorX: 0.36,
      anchorY: 0.5,
      spreadX: 0.18,
      spreadY: 0.22,
      pull: 0.0005,
      jitter: 0.00016,
      maxV: 0.0029,
      alpha: 0.66,
      trail: 0,
    }
  }
  return {
    mode: 'flee',
    anchorX: 0.5,
    anchorY: 0.5,
    spreadX: 0.92,
    spreadY: 0.82,
    pull: 0.00012,
    jitter: 0.00034,
    maxV: 0.003,
    alpha: 0.58,
    trail: 0,
  }
}

const SCATTER_GROUPS = [
  { x: 0.2, y: 0.32 },
  { x: 0.38, y: 0.62 },
  { x: 0.58, y: 0.42 },
]

function randomTarget(profile) {
  if (profile.mode === 'flee') {
    const edgeBias = Math.random() < 0.35
    return {
      tx: edgeBias
        ? (Math.random() < 0.5 ? 0.05 + Math.random() * 0.18 : 0.77 + Math.random() * 0.18)
        : 0.14 + Math.random() * 0.72,
      ty: 0.08 + Math.random() * 0.84,
    }
  }

  if (profile.mode === 'scatter') {
    const group = SCATTER_GROUPS[Math.floor(Math.random() * SCATTER_GROUPS.length)]
    return {
      tx: Math.max(0.06, Math.min(0.92, group.x + (Math.random() - 0.5) * 0.2)),
      ty: Math.max(0.1, Math.min(0.9, group.y + (Math.random() - 0.5) * 0.28)),
    }
  }

  return {
    tx: Math.max(0.04, Math.min(0.96, profile.anchorX + (Math.random() - 0.5) * profile.spreadX)),
    ty: Math.max(0.08, Math.min(0.92, profile.anchorY + (Math.random() - 0.5) * profile.spreadY)),
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
      return Array.from({ length: dotCount }, () => {
        const target = randomTarget(profile)
        return {
          x:  target.tx + (Math.random() - 0.5) * profile.spreadX * 0.2,
          y:  target.ty + (Math.random() - 0.5) * profile.spreadY * 0.2,
          tx: target.tx,
          ty: target.ty,
          vx: (Math.random() - 0.5) * 0.0018,
          vy: (Math.random() - 0.5) * 0.0018,
          phase: Math.random() * Math.PI * 2,
          orbit: profile.mode === 'flee'
            ? 0.9 + Math.random() * 1.2
            : profile.mode === 'cluster'
              ? 0.35 + Math.random() * 0.45
              : 0.55 + Math.random() * 0.9,
          /* 물리 픽셀 기준 반지름 */
          r:  (
            profile.mode === 'flee'
              ? 0.9 + Math.random() * 1.5
              : 1.1 + Math.random() * (score >= HERD_STAGE_THRESHOLDS.rush ? 2.7 : 2)
          ) * dpr,
        }
      })
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
        const waveX = Math.sin(tick * 0.011 + d.phase) * 0.014 * d.orbit
        const waveY = Math.cos(tick * 0.01 + d.phase) * 0.022 * d.orbit
        const targetX = d.tx + waveX
        const targetY = d.ty + waveY
        const noiseX = (Math.random() - 0.5) * profile.jitter
        const noiseY = (Math.random() - 0.5) * profile.jitter

        d.prevX = d.x
        d.prevY = d.y

        /* Flee는 화면 전체에 분산되고, Rush는 좁은 군집으로 수렴한다. */
        d.vx += (targetX - d.x) * profile.pull + noiseX
        d.vy += (targetY - d.y) * profile.pull * 0.72 + noiseY

        d.x += d.vx
        d.y += d.vy

        /* 경계 처리: 가장자리에 고정되지 않도록 부드럽게 되돌린다. */
        if (d.x < 0.01) {
          d.x = 0.01
          d.vx = Math.abs(d.vx) * 0.6
        }
        if (d.x > 0.99) {
          d.x = 0.99
          d.vx = -Math.abs(d.vx) * 0.6
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
