import { HERD_STAGE_THRESHOLDS } from '../../utils/herdStage'

export function herdDotColor(score) {
  if (score >= HERD_STAGE_THRESHOLDS.rush) return '#EF4444'
  if (score >= HERD_STAGE_THRESHOLDS.drift) return '#F97316'
  if (score > HERD_STAGE_THRESHOLDS.scatter) return '#A3AAB8'
  if (score > HERD_STAGE_THRESHOLDS.flee) return '#60A5FA'
  return '#3B82F6'
}

export function herdFlowProfile(score) {
  if (score >= HERD_STAGE_THRESHOLDS.rush) {
    return {
      mode: 'cluster', anchorX: 0.78, anchorY: 0.5,
      spreadX: 0.08, spreadY: 0.16, pull: 0.0011,
      jitter: 0.00008, maxV: 0.0038, alpha: 0.86, trail: 0.08,
    }
  }
  if (score >= HERD_STAGE_THRESHOLDS.drift) {
    return {
      mode: 'drift', anchorX: 0.66, anchorY: 0.5,
      spreadX: 0.22, spreadY: 0.34, pull: 0.00072,
      jitter: 0.00012, maxV: 0.0032, alpha: 0.72, trail: 0.04,
    }
  }
  if (score > HERD_STAGE_THRESHOLDS.scatter) {
    return {
      mode: 'calm', anchorX: 0.5, anchorY: 0.5,
      spreadX: 0.34, spreadY: 0.48, pull: 0.0005,
      jitter: 0.00012, maxV: 0.0026, alpha: 0.56, trail: 0,
    }
  }
  if (score > HERD_STAGE_THRESHOLDS.flee) {
    return {
      mode: 'scatter', anchorX: 0.36, anchorY: 0.5,
      spreadX: 0.18, spreadY: 0.22, pull: 0.0005,
      jitter: 0.00016, maxV: 0.0029, alpha: 0.66, trail: 0,
    }
  }
  return {
    mode: 'flee', anchorX: 0.5, anchorY: 0.5,
    spreadX: 0.92, spreadY: 0.82, pull: 0.00012,
    jitter: 0.00034, maxV: 0.003, alpha: 0.58, trail: 0,
  }
}

const SCATTER_GROUPS = [
  { x: 0.2, y: 0.32 },
  { x: 0.38, y: 0.62 },
  { x: 0.58, y: 0.42 },
]

export function randomHerdTarget(profile, random = Math.random) {
  if (profile.mode === 'flee') {
    const edgeBias = random() < 0.35
    return {
      tx: edgeBias
        ? (random() < 0.5 ? 0.05 + random() * 0.18 : 0.77 + random() * 0.18)
        : 0.14 + random() * 0.72,
      ty: 0.08 + random() * 0.84,
    }
  }
  if (profile.mode === 'scatter') {
    const group = SCATTER_GROUPS[Math.floor(random() * SCATTER_GROUPS.length)]
    return {
      tx: Math.max(0.06, Math.min(0.92, group.x + (random() - 0.5) * 0.2)),
      ty: Math.max(0.1, Math.min(0.9, group.y + (random() - 0.5) * 0.28)),
    }
  }
  return {
    tx: Math.max(0.04, Math.min(0.96, profile.anchorX + (random() - 0.5) * profile.spreadX)),
    ty: Math.max(0.08, Math.min(0.92, profile.anchorY + (random() - 0.5) * profile.spreadY)),
  }
}

export function createHerdDots({
  dotCount,
  profile,
  score,
  dpr,
  activeRatio,
  random = Math.random,
}) {
  return Array.from({ length: dotCount }, (_, index) => {
    const target = randomHerdTarget(profile, random)
    return {
      x: target.tx + (random() - 0.5) * profile.spreadX * 0.2,
      y: target.ty + (random() - 0.5) * profile.spreadY * 0.2,
      tx: target.tx,
      ty: target.ty,
      vx: (random() - 0.5) * 0.0018,
      vy: (random() - 0.5) * 0.0018,
      phase: random() * Math.PI * 2,
      orbit: profile.mode === 'flee'
        ? 0.9 + random() * 1.2
        : profile.mode === 'cluster'
          ? 0.35 + random() * 0.45
          : 0.55 + random() * 0.9,
      active: index < Math.round(dotCount * activeRatio),
      r: (
        profile.mode === 'flee'
          ? 0.9 + random() * 1.5
          : 1.1 + random() * (score >= HERD_STAGE_THRESHOLDS.rush ? 2.7 : 2)
      ) * dpr,
    }
  })
}

export function advanceHerdDot(dot, {
  profile,
  tick,
  enhanced,
  direction,
  random = Math.random,
}) {
  const targetX = dot.tx + Math.sin(tick * 0.011 + dot.phase) * 0.014 * dot.orbit
  const targetY = dot.ty + Math.cos(tick * 0.01 + dot.phase) * 0.022 * dot.orbit
  dot.prevX = dot.x
  dot.prevY = dot.y
  dot.vx += (targetX - dot.x) * profile.pull + (random() - 0.5) * profile.jitter
  dot.vy += (targetY - dot.y) * profile.pull * 0.72 + (random() - 0.5) * profile.jitter
  if (enhanced) dot.vx += direction * 0.000035

  dot.x += dot.vx
  dot.y += dot.vy
  if (dot.x < 0.01) {
    dot.x = 0.01
    dot.vx = Math.abs(dot.vx) * 0.6
  }
  if (dot.x > 0.99) {
    dot.x = 0.99
    dot.vx = -Math.abs(dot.vx) * 0.6
  }
  if (dot.y < 0.04 || dot.y > 0.96) dot.vy *= -0.65

  const speed = Math.hypot(dot.vx, dot.vy)
  if (speed > profile.maxV) {
    dot.vx = (dot.vx / speed) * profile.maxV
    dot.vy = (dot.vy / speed) * profile.maxV
  }
  return dot
}
