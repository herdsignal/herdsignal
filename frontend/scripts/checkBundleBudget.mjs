import { readdir, stat } from 'node:fs/promises'
import { resolve } from 'node:path'

const assetDirectory = resolve('dist/assets')

const budgets = [
  { label: 'entry JavaScript', pattern: /^index-.*\.js$/, maxKb: 260 },
  { label: 'StockDetail JavaScript', pattern: /^StockDetail-.*\.js$/, maxKb: 50 },
  { label: 'Portfolio JavaScript', pattern: /^Portfolio-.*\.js$/, maxKb: 35 },
  { label: 'Search JavaScript', pattern: /^Search-.*\.js$/, maxKb: 20 },
  { label: 'Watchlist JavaScript', pattern: /^Watchlist-.*\.js$/, maxKb: 15 },
  { label: 'MarketHome JavaScript', pattern: /^MarketHome-.*\.js$/, maxKb: 10 },
]

const files = await readdir(assetDirectory)
const results = []

for (const budget of budgets) {
  const matches = files.filter((file) => budget.pattern.test(file))
  if (matches.length !== 1) {
    throw new Error(`${budget.label}: expected one build asset, found ${matches.length}`)
  }
  const file = matches[0]
  const bytes = (await stat(resolve(assetDirectory, file))).size
  const sizeKb = bytes / 1024
  results.push({ ...budget, file, sizeKb })
}

const oversizedJavaScript = await Promise.all(
  files
    .filter((file) => file.endsWith('.js'))
    .map(async (file) => ({
      file,
      sizeKb: (await stat(resolve(assetDirectory, file))).size / 1024,
    })),
)
const maxJavaScript = oversizedJavaScript.reduce(
  (largest, item) => item.sizeKb > largest.sizeKb ? item : largest,
  { file: 'none', sizeKb: 0 },
)

const failures = results.filter((result) => result.sizeKb > result.maxKb)
if (maxJavaScript.sizeKb > 400) {
  failures.push({
    label: 'largest JavaScript asset',
    file: maxJavaScript.file,
    sizeKb: maxJavaScript.sizeKb,
    maxKb: 400,
  })
}

results.forEach((result) => {
  console.log(
    `${result.label}: ${result.sizeKb.toFixed(1)} KB / ${result.maxKb} KB (${result.file})`,
  )
})
console.log(`largest JavaScript asset: ${maxJavaScript.sizeKb.toFixed(1)} KB (${maxJavaScript.file})`)

if (failures.length > 0) {
  failures.forEach((failure) => {
    console.error(
      `Bundle budget exceeded: ${failure.label} is ${failure.sizeKb.toFixed(1)} KB, limit ${failure.maxKb} KB`,
    )
  })
  process.exitCode = 1
}
