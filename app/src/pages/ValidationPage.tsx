import { pct } from '../lib/format'
import type { Meta } from '../lib/types'

export function ValidationPage({ meta }: { meta: Meta }) {
  const v = meta.validation
  const startCagr = v.start_sensitivity.map((r) => r.cagr)
  const startSharpe = v.start_sensitivity.map((r) => r.sharpe)
  const startMdd = v.start_sensitivity.map((r) => r.mdd)

  return (
    <>
      <section className="card">
        <h2>验证结论</h2>
        <p className="lead">
          规则在起点、频率、成本上都稳，但<strong>没有统计显著的 alpha</strong>
          （月均超额 {pct(v.excess_vs_ew, 2)}，t = {v.t_stat_vs_ew.toFixed(2)}）。
          它的夏普优势主要来自仓位管理、黄金和国债，不是选股。
        </p>
        <div className="range-list">
          <div>
            <span>起点年化</span>
            <strong>
              {pct(Math.min(...startCagr), 1)} ~ {pct(Math.max(...startCagr), 1)}
            </strong>
          </div>
          <div>
            <span>起点夏普</span>
            <strong>
              {Math.min(...startSharpe).toFixed(2)} ~ {Math.max(...startSharpe).toFixed(2)}
            </strong>
          </div>
          <div>
            <span>起点最大回撤</span>
            <strong>
              {pct(Math.abs(Math.max(...startMdd)), 1)} ~ {pct(Math.abs(Math.min(...startMdd)), 1)}
            </strong>
          </div>
        </div>
      </section>

      <section className="card">
        <h2>起点敏感性</h2>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>起点</th>
                <th className="r">年化</th>
                <th className="r">夏普</th>
                <th className="r">最大回撤</th>
              </tr>
            </thead>
            <tbody>
              {v.start_sensitivity.map((r) => (
                <tr key={r.start}>
                  <td>{r.start}</td>
                  <td className="r">{pct(r.cagr, 1)}</td>
                  <td className="r">{r.sharpe.toFixed(2)}</td>
                  <td className="r down">{pct(r.mdd, 1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="hint">8 个不同起点，收益与回撤都落在相近区间，不是某一年的运气。</p>
      </section>

      <section className="card">
        <h2>调仓频率对比</h2>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>频率</th>
                <th className="r">年化</th>
                <th className="r">夏普</th>
                <th className="r">最大回撤</th>
                <th className="r">累计成本</th>
              </tr>
            </thead>
            <tbody>
              {v.frequency.map((r) => (
                <tr key={r.freq} className={r.freq === '周' ? 'hl' : ''}>
                  <td>{r.freq}</td>
                  <td className="r">{pct(r.cagr, 1)}</td>
                  <td className="r">{r.sharpe.toFixed(2)}</td>
                  <td className="r down">{pct(r.mdd, 1)}</td>
                  <td className="r">{pct(r.cost, 1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="hint">
          周频收益略高、回撤最浅，但成本是月频的两倍。单边成本超过 0.15% 时，周频的优势会消失。
        </p>
      </section>

      <section className="card muted-card">
        <h2>局限</h2>
        <ul className="list">
          <li>样本 2015–2026，只有一轮完整的 A 股牛熊，统计功效有限。</li>
          <li>参数网格与显著性检验基于月频版本；周频完成了起点与频率对比。</li>
          <li>标普500 通过 QDII 交易，存在溢价与限购风险。</li>
          <li>回测用的是 ETF 前复权价格，实盘成交价与净值会有差异。</li>
        </ul>
        <p className="hint">{v.note}</p>
      </section>
    </>
  )
}
