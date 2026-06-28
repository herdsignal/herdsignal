/**
 * HerdDots.jsx — HERD 무리 점 애니메이션 컴포넌트
 *
 * score에 따라 점들이 오른쪽(Rush=몰림) 또는 왼쪽(Flee=흩어짐)으로 이동.
 * 래퍼런스: wireframes/wireframe-home-v4.html createHerd() 함수 기반.
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
    const cluster = score / 100          // 0(Flee) → 1(Rush)
    const pull    = cluster * 0.0005     // 중심 인력 계수
    const cx      = 0.12 + cluster * 0.68  // 중심 X
    const maxV    = 0.0025 + cluster * 0.002  // 최대 속도

    let dots = []
    let rafId

    /* 점 배열 초기화 */
    function initDots() {
      const initCx = 0.12 + cluster * 0.68
      const initSp = 0.42 - cluster * 0.30
      return Array.from({ length: dotCount }, () => ({
        x:  Math.max(0.02, Math.min(0.98, initCx + (Math.random() - 0.5) * initSp * 2)),
        y:  Math.max(0.08, Math.min(0.92, 0.5   + (Math.random() - 0.5) * 0.7)),
        vx: (Math.random() - 0.5) * 0.0025,
        vy: (Math.random() - 0.5) * 0.0025,
        /* 물리 픽셀 기준 반지름 */
        r:  (1.2 + Math.random() * 2) * dpr,
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
      const W = canvas.width
      const H = canvas.height
      ctx.clearRect(0, 0, W, H)

      dots.forEach(d => {
        /* 중심 인력 적용 */
        d.vx += (cx  - d.x) * pull
        d.vy += (0.5 - d.y) * pull * 0.4  // Y축 인력은 약하게

        d.x += d.vx
        d.y += d.vy

        /* 경계 반사 */
        if (d.x < 0.01 || d.x > 0.99) d.vx *= -1
        if (d.y < 0.04 || d.y > 0.96) d.vy *= -1

        /* 최대 속도 제한 */
        const spd = Math.hypot(d.vx, d.vy)
        if (spd > maxV) {
          d.vx = (d.vx / spd) * maxV
          d.vy = (d.vy / spd) * maxV
        }

        ctx.beginPath()
        ctx.arc(d.x * W, d.y * H, d.r, 0, Math.PI * 2)
        ctx.fillStyle   = color
        /* score 높을수록 불투명하게 */
        ctx.globalAlpha = 0.5 + cluster * 0.35
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
