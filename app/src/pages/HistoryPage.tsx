import { useState } from 'react'
import { DrawdownChart } from '../components/DrawdownChart'
import { NavChart } from '../components/NavChart'
import { StatCard } from '../components/StatCard'
import { YearlyBars } from '../components/YearlyBars'
import { cnDate, pct } from '../lib/format'
import { drawdownSeries, evaluate, trailingMetrics } from '../lib/metrics'
import type { Meta, NavPoint, SignalRow } from '../lib/types'

const levelText = { good: '正常', warn: '关注', bad: '异常' } as const

const RANGES = [
  { label: '1年', weeks: 52, step: 3 },
  { label: '3年', weeks: 156, step: 6 },
  { label: '5年', weeks: 260, step: 12 },
  { label: '全部', weeks: 0, step: 0 },
]

export function HistoryPage({
  nav,
  meta,
  history,
}: {
  nav: NavPoint[]
  meta: Meta
  history: SignalRow[]
}) {
  const [rangeIdx, setRangeIdx] = useState(3)
  const trailing = trailingMetrics(nav, 52)
  const verdict = trailing ? evaluate(trailing, meta.expected) : null
  const recent = [...history].slice(-14).reverse()

  const range = RANGES[rangeIdx]
  const view = range.weeks ? nav.slice(-(range.weeks + 1)) : nav
  const base = view.length ? view[0].nav : 1
  const spBase = view[0]?.sp500
  const hsBase = view[0]?.hs300
  const chartData = view.map((p) => ({
    date: p.date,
    ret: p.nav / base - 1,
    sp500: spBase && p.sp500 != null ? p.sp500 / spBase - 1 : null,
    hs300: hsBase && p.hs300 != null ? p.hs300 / hsBase - 1 : null,
  }))
  const viewReturn = view.length > 1 ? view[view.length - 1].nav / base - 1 : 0
  const ddView = drawdownSeries(view)
  const viewMdd = ddView.reduce((m, d) => Math.min(m, d.dd), 0)

  return (
    <>
      <section className={`verdict ${verdict?.overall ?? 'good'}`}>
        <div className="verdict-head">
          <span className="eyebrow">近 52 周表现评估</span>
          <span className="dot-status" />
        </div>
        <h2>{verdict ? levelText[verdict.overall] : '数据不足'}</h2>
        <p>{verdict?.summary ?? '净值序列不足 53 周，无法评估。'}</p>
      </section>

      {verdict && (
        <section className="stats">
          {verdict.items.map((it) => (
            <StatCard
              key={it.key}
              label={it.label}
              value={it.actual}
              sub={`长期 ${it.expected} · ${it.detail}`}
              level={it.level}
            />
          ))}
        </section>
      )}

      <section className="card">
        <div className="card-head">
          <h2>累计收益</h2>
          <span className="hint">
            {range.weeks ? `近 ${range.label}` : '2015 至今'} {pct(viewReturn, 1)}
          </span>
        </div>
        <div className="range-tabs">
          {RANGES.map((r, i) => (
            <button
              key={r.label}
              type="button"
              className={i === rangeIdx ? 'on' : ''}
              onClick={() => setRangeIdx(i)}
            >
              {r.label}
            </button>
          ))}
        </div>
        <NavChart data={chartData} stepMonths={range.step} />
        <p className="hint">对比基准：标普500 ETF（513500）、沪深300 ETF（510300）前复权价格；区间起点均归零。</p>
      </section>

      <section className="card">
        <div className="card-head">
          <h2>回撤</h2>
          <span className="hint">区间最大 {pct(viewMdd, 1)}</span>
        </div>
        <DrawdownChart data={ddView} stepMonths={range.step} />
      </section>

      <section className="card">
        <h2>分年度收益</h2>
        <YearlyBars data={meta.yearly} />
      </section>

      <section className="card">
        <h2>最近的信号</h2>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>日期</th>
                <th>持有</th>
                <th className="r">股票</th>
                <th className="r">闸门</th>
              </tr>
            </thead>
            <tbody>
              {recent.map((r) => {
                const eq = Object.entries(r.weights)
                  .filter(([c]) => !['511010', '518880'].includes(c))
                  .reduce((a, [, w]) => a + w, 0)
                return (
                  <tr key={r.date}>
                    <td>{cnDate(r.date).replace('年', '/').replace('月', '/').replace('日', '')}</td>
                    <td>{r.leader_name}</td>
                    <td className="r">{pct(eq, 0)}</td>
                    <td className="r">{r.gate ? '开' : '关'}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </section>
    </>
  )
}
