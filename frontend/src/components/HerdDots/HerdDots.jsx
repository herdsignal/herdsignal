/**
 * HerdDots.jsx — HERD 무리 점 애니메이션 컴포넌트
 *
 * score에 따라 점들이 오른쪽(Rush=몰림) 또는 왼쪽(Flee=흩어짐)으로 이동.
 * 래퍼런스: wireframes/wireframe-home-v4.html createHerd() 함수 기반.
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

/**
 * @param {number} score     HERD 점수 (0~100)
 * @param {number} width     캔버스 CSS 너비 (px)
 * @param {number} height    캔버스 CSS 높이 (px)
 * @param {number} dotCount  점 개수
 */
export default function HerdDots({
  score    = 50,
  width    = 200,
  height   = 100,
  dotCount = 20,
}) {
  const canvasRef = useRef(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    const dpr = window.devicePixelRatio || 1

    /* 레티나 디스플레이 대응: 물리 픽셀 = CSS 픽셀 × dpr */
    canvas.width  = width  * dpr
    canvas.height = height * dpr

    const color   = getColor(score)
    /* cluster: 0(Flee) → 1(Rush) — 점 집결 강도 */
    const cluster = score / 100

    /* 중심 X 좌표 비율 (0~1):  낮은 score → 왼쪽, 높은 score → 오른쪽 */
    const initCx = 0.12 + cluster * 0.68
    /* 초기 퍼짐 반경: 높은 score → 좁게 뭉침, 낮은 score → 넓게 흩어짐 */
    const initSp = 0.42 - cluster * 0.30

    /* 점 초기 위치·속도·크기 설정 */
    const dots = Array.from({ length: dotCount }, () => ({
      x:  Math.max(0.02, Math.min(0.98, initCx + (Math.random() - 0.5) * initSp * 2)),
      y:  Math.max(0.08, Math.min(0.92, 0.5   + (Math.random() - 0.5) * 0.7)),
      vx: (Math.random() - 0.5) * 0.0025,
      vy: (Math.random() - 0.5) * 0.0025,
      /* 물리 픽셀 기준 반지름 */
      r:  (1.2 + Math.random() * 2) * dpr,
    }))

    /* 매 프레임 공통 상수 */
    const pull = cluster * 0.0005          // 중심 인력 계수
    const cx   = 0.12 + cluster * 0.68    // 중심 X (draw 루프 내 재계산 안 해도 됨)
    const maxV = 0.0025 + cluster * 0.002  // 최대 속도

    let rafId

    function draw() {
      const W = canvas.width
      const H = canvas.height
      ctx.clearRect(0, 0, W, H)

      dots.forEach(d => {
        /* 중심으로 끌어당기는 힘 적용 */
        d.vx += (cx  - d.x) * pull
        d.vy += (0.5 - d.y) * pull * 0.4  // Y축 인력은 약하게

        d.x += d.vx
        d.y += d.vy

        /* 경계 도달 시 반사 */
        if (d.x < 0.01 || d.x > 0.99) d.vx *= -1
        if (d.y < 0.04 || d.y > 0.96) d.vy *= -1

        /* 최대 속도 제한 */
        const spd = Math.hypot(d.vx, d.vy)
        if (spd > maxV) {
          d.vx = (d.vx / spd) * maxV
          d.vy = (d.vy / spd) * maxV
        }

        /* 점 렌더링 */
        ctx.beginPath()
        ctx.arc(d.x * W, d.y * H, d.r, 0, Math.PI * 2)
        ctx.fillStyle    = color
        /* score 높을수록 불투명하게 */
        ctx.globalAlpha  = 0.5 + cluster * 0.35
        ctx.fill()
        ctx.globalAlpha  = 1
      })

      rafId = requestAnimationFrame(draw)
    }

    draw()

    /* 언마운트 또는 props 변경 시 애니메이션 정리 */
    return () => cancelAnimationFrame(rafId)
  }, [score, width, height, dotCount])

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
