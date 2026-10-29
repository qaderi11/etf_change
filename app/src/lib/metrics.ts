import type { Meta, NavPoint } from './types'

export type Level = 'good' | 'warn' | 'bad'

export interface Trailing {
  weeks: number
  periodReturn: number
  cagr: number
  vol: number
  mdd: number
  startNav: number
  endNav: number
}

export function trailingMetrics(nav: NavPoint[], weeks = 52): Trailing | null {
  if (nav.length < weeks + 1) return null
  const slice = nav.slice(-(weeks + 1))
  const startNav = slice[0].nav
  const endNav = slice[slice.length - 1].nav
  const periodReturn = endNav / startNav - 1
  const rets: number[] = []
  let peak = -Infinity
  let mdd = 0
  for (let i = 0; i < slice.length; i += 1) {
    if (i > 0) rets.push(slice[i].nav / slice[i - 1].nav - 1)
    peak = Math.max(peak, slice[i].nav)
    mdd = Math.min(mdd, slice[i].nav / peak - 1)
  }
  const mean = rets.reduce((a, b) => a + b, 0) / rets.length
  const variance = rets.reduce((a, b) => a + (b - mean) ** 2, 0) / Math.max(1, rets.length - 1)
  return {
    weeks,
    periodReturn,
    cagr: Math.pow(endNav / startNav, 52 / weeks) - 1,
    vol: Math.sqrt(variance) * Math.sqrt(52),
    mdd,
    startNav,
    endNav,
  }
}

export interface Verdict {
  key: string
  label: string
  level: Level
  actual: string
  expected: string
  detail: string
}

const levelRank: Record<Level, number> = { good: 0, warn: 1, bad: 2 }

export function evaluate(t: Trailing, e: Meta['expected']): {
  overall: Level
  items: Verdict[]
  summary: string
} {
  const items: Verdict[] = []

  let cagrLevel: Level = 'good'
  let cagrDetail = '与长期水平接近'
  if (t.cagr < 0) {
    cagrLevel = 'bad'
    cagrDetail = '近一年为负收益，需检查是否遇到策略逆风期'
  } else if (t.cagr < e.cagr * 0.75) {
    cagrLevel = 'warn'
    cagrDetail = '低于长期水平，处于逆风期'
  } else if (t.cagr < e.cagr * 0.95) {
    cagrDetail = '略低于长期水平，仍在正常波动范围内'
  } else if (t.cagr > e.cagr * 1.8) {
    cagrDetail = '明显好于长期水平，注意均值回归'
  }
  items.push({
    key: 'cagr',
    label: '近 52 周年化',
    level: cagrLevel,
    actual: `${(t.cagr * 100).toFixed(1)}%`,
    expected: `${(e.cagr * 100).toFixed(1)}%`,
    detail: cagrDetail,
  })

  let volLevel: Level = 'good'
  let volDetail = '波动在历史范围内'
  if (t.vol > e.vol * 1.6) {
    volLevel = 'bad'
    volDetail = '波动显著高于历史，仓位或市场结构可能已变化'
  } else if (t.vol > e.vol * 1.3) {
    volLevel = 'warn'
    volDetail = '波动偏高，回撤风险上升'
  } else if (t.vol < e.vol * 0.6) {
    volDetail = '波动偏低，通常意味着仓位较轻'
  }
  items.push({
    key: 'vol',
    label: '近 52 周波动',
    level: volLevel,
    actual: `${(t.vol * 100).toFixed(1)}%`,
    expected: `${(e.vol * 100).toFixed(1)}%`,
    detail: volDetail,
  })

  let mddLevel: Level = 'good'
  let mddDetail = '回撤未超出历史区间'
  if (t.mdd < e.mdd * 1.5) {
    mddLevel = 'bad'
    mddDetail = '回撤已超过历史最大回撤的 1.5 倍，属于意外情况'
  } else if (t.mdd < e.mdd * 1.15) {
    mddLevel = 'warn'
    mddDetail = '回撤接近历史极值，需要关注'
  }
  items.push({
    key: 'mdd',
    label: '近 52 周最大回撤',
    level: mddLevel,
    actual: `${(t.mdd * 100).toFixed(1)}%`,
    expected: `${(e.mdd * 100).toFixed(1)}%`,
    detail: mddDetail,
  })

  const overall = items.reduce<Level>(
    (acc, it) => (levelRank[it.level] > levelRank[acc] ? it.level : acc),
    'good',
  )

  const summary =
    overall === 'bad'
      ? '出现超出历史范围的情况，建议暂停加仓并复查数据与规则。'
      : overall === 'warn'
        ? '有一项指标偏离历史区间，属于正常波动范围的上沿，继续观察。'
        : '各项指标都在历史区间内，策略按预期运行。'

  return { overall, items, summary }
}

export function drawdownSeries(nav: NavPoint[]): { date: string; dd: number }[] {
  let peak = -Infinity
  return nav.map((p) => {
    peak = Math.max(peak, p.nav)
    return { date: p.date, dd: p.nav / peak - 1 }
  })
}

export function lastUpdated(latest: { asof: string; generated_at: string }): {
  text: string
  stale: boolean
} {
  const asof = new Date(`${latest.asof}T15:00:00+08:00`).getTime()
  const days = Math.floor((Date.now() - asof) / 86400000)
  return { text: latest.asof, stale: days > 10 }
}
