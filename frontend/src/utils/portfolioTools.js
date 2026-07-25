export function targetWeightsFromPortfolio(portfolio) {
  const weights = {}
  ;(portfolio ?? []).forEach((item) => {
    const value = item.targetWeight ?? item.target_weight
    if (value != null) weights[item.ticker] = String(Number(value) * 100)
  })
  return weights
}
