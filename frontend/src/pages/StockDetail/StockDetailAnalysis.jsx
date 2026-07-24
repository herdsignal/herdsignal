import styles from './StockDetail.module.css'
import {
  INDICATORS,
  epsMultiplierDesc,
  evidenceTone,
  formatIndicator,
  formatMultiplier,
  normalizeBar,
  sectorMultiplierDesc,
} from './stockDetailModel'
import {
  fmtAnnualActions,
  fmtReliabilityPct,
  fmtReliabilityPlainPct,
  fmtReliabilityScore,
  reliabilityTone,
  sampleQualityLabel,
  signalEdgeLabel,
} from './stockReliabilityModel'

function EvidenceCard({ scoreDate, evidence }) {
  return (
    <div className={styles.card}>
      <div className={styles.cardHeader}>
        <div>
          <div className={styles.cardTitle}>신호 근거</div>
          <div className={styles.cardMeta}>현재 HERD 판단을 움직인 데이터</div>
        </div>
        <div className={styles.cardMeta}>{scoreDate} 기준</div>
      </div>
      <div className={styles.cardBodySmall}>
        <div className={styles.evidenceGrid}>
          {evidence.map((item) => (
            <div key={`${item.label}-${item.caption}`} className={styles.evidenceItem}>
              <span>{item.label}</span>
              <strong style={{ color: evidenceTone(item.type) }}>{item.value}</strong>
              <em>{item.caption}</em>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function IndicatorCard({ herdData, color }) {
  return (
    <div className={styles.card}>
      <div className={styles.cardHeader}>
        <div className={styles.cardTitle}>지표 분해</div>
        <div className={styles.cardMeta}>{herdData.scoreDate} 기준</div>
      </div>
      <div className={styles.cardBody}>
        {INDICATORS.map((indicator) => {
          const raw = herdData[indicator.key] ?? null
          const hasValue = raw != null
          const percentage = hasValue
            ? normalizeBar(raw, indicator.min, indicator.max)
            : 0
          const display = hasValue
            ? formatIndicator(raw, indicator.unit, indicator.signed)
            : '—'
          return (
            <div key={indicator.key} className={styles.indicatorRow}>
              <div className={styles.indicatorLabel}>{indicator.label}</div>
              <div className={styles.indicatorWeight}>{indicator.weight}%</div>
              <div className={styles.indicatorTrack}>
                {hasValue && (
                  <div
                    className={styles.indicatorFill}
                    style={{ width: `${percentage}%`, background: color }}
                  />
                )}
              </div>
              <div className={styles.indicatorValue}>{display}</div>
            </div>
          )
        })}
        <div className={styles.adjustmentBox}>
          <div className={styles.adjustmentRow}>
            <span>EPS 보정</span>
            <strong>
              {formatMultiplier(herdData.epsMultiplier)}
              <em>{epsMultiplierDesc(herdData.epsMultiplier)}</em>
            </strong>
          </div>
          <div className={styles.adjustmentRow}>
            <span>섹터 강도 보정</span>
            <strong>
              {formatMultiplier(herdData.sectorMultiplier)}
              <em>{sectorMultiplierDesc(herdData.sectorMultiplier)}</em>
            </strong>
          </div>
        </div>
      </div>
    </div>
  )
}

function ReliabilityCard({
  reliability,
  loading,
  currentReliability,
  evidence,
}) {
  return (
    <div className={styles.card}>
      <div className={styles.cardHeader}>
        <div>
          <div className={styles.cardTitle}>신호 검증</div>
          <div className={styles.cardMeta}>최근 3년 HERD 히스토리</div>
        </div>
        {reliability && (
          <div
            className={styles.reliabilityBadge}
            style={{
              color: reliabilityTone(reliability.reliabilityGrade),
              borderColor: reliabilityTone(reliability.reliabilityGrade),
            }}
          >
            {reliability.reliabilityLabel}
          </div>
        )}
      </div>
      <div className={styles.cardBodySmall}>
        {loading ? (
          <div className={styles.chartEmpty}>로딩 중…</div>
        ) : reliability ? (
          <>
            {currentReliability && (
              <div className={styles.currentReliability}>
                <div>
                  <span>{currentReliability.label}</span>
                  <strong>
                    {currentReliability.scoreValue
                      ? fmtReliabilityScore(currentReliability.value)
                      : fmtReliabilityPlainPct(currentReliability.value)}
                  </strong>
                </div>
                <em>
                  {currentReliability.caption}
                  {currentReliability.sample != null ? ` · ${currentReliability.sample}회` : ''}
                </em>
              </div>
            )}
            <div className={styles.reliabilityGrid}>
              <div className={styles.reliabilityItem}>
                <span>모델 적합도</span>
                <strong>{fmtReliabilityScore(reliability.fitScore)}</strong>
                <em>{reliability.reliabilityLabel}</em>
              </div>
              <div className={styles.reliabilityItem}>
                <span>표본 품질</span>
                <strong>{sampleQualityLabel(reliability.sampleQuality)}</strong>
                <em>{reliability.totalSignalSamples ?? 0}회</em>
              </div>
              <div className={styles.reliabilityItem}>
                <span>Flee 적중률</span>
                <strong>{fmtReliabilityPlainPct(reliability.fleeHitRate)}</strong>
                <em>{signalEdgeLabel(reliability.buySignalEdge)}</em>
              </div>
              <div className={styles.reliabilityItem}>
                <span>Rush 적중률</span>
                <strong>{fmtReliabilityPlainPct(reliability.rushHitRate)}</strong>
                <em>{signalEdgeLabel(reliability.sellSignalEdge)}</em>
              </div>
              <div className={styles.reliabilityItem}>
                <span>MDD 개선</span>
                <strong>{fmtReliabilityPct(reliability.mddImprovement, '%p')}</strong>
                <em>낙폭 관리</em>
              </div>
              <div className={styles.reliabilityItem}>
                <span>수익률 보존</span>
                <strong>{fmtReliabilityPlainPct(reliability.returnPreservation)}</strong>
                <em>Buy &amp; Hold 대비</em>
              </div>
              <div className={styles.reliabilityItem}>
                <span>연 행동 수</span>
                <strong>{fmtAnnualActions(reliability.annualActions)}</strong>
                <em>과매매 체크</em>
              </div>
            </div>
            {evidence.length > 0 && (
              <div className={styles.reliabilityEvidenceGrid}>
                {evidence.map((item) => (
                  <div
                    key={item.label}
                    className={`${styles.reliabilityEvidenceItem} ${styles[`reliabilityEvidence_${item.tone}`] || ''}`}
                  >
                    <span>{item.label}</span>
                    <strong>{item.value}</strong>
                    <em>{item.caption}</em>
                  </div>
                ))}
              </div>
            )}
            <div className={styles.reliabilitySummary}>
              {reliability.reliabilityVerdict ?? reliability.summary}
            </div>
          </>
        ) : (
          <div className={styles.chartEmpty}>신뢰도 데이터를 계산할 수 없습니다.</div>
        )}
      </div>
    </div>
  )
}

export default function StockDetailAnalysis({
  herdData,
  color,
  signalEvidence,
  reliability,
  reliabilityLoading,
  currentReliability,
  reliabilityEvidence,
}) {
  return (
    <details className={styles.detailDisclosure}>
      <summary>
        <div><span>상세 분석</span><strong>신호 근거·지표 분해·검증 결과</strong></div>
        <em>펼쳐보기</em>
      </summary>
      <div className={styles.detailDisclosureBody}>
        <EvidenceCard scoreDate={herdData.scoreDate} evidence={signalEvidence} />
        <IndicatorCard herdData={herdData} color={color} />
        <ReliabilityCard
          reliability={reliability}
          loading={reliabilityLoading}
          currentReliability={currentReliability}
          evidence={reliabilityEvidence}
        />
      </div>
    </details>
  )
}
