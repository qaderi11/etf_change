import { Chip } from '../components/StatCard'
import { assetColor, assetName, cnDate, pct, signedPct } from '../lib/format'
import type { Latest, Meta } from '../lib/types'

export function SignalPage({ latest, meta }: { latest: Latest; meta: Meta }) {
  const entries = Object.entries(latest.weights).sort((a, b) => b[1] - a[1])
  const staleDays = Math.floor((Date.now() - new Date(`${latest.asof}T15:00:00+08:00`).getTime()) / 86400000)

  return (
    <>
      <section className="hero">
        <div className="hero-head">
          <span className="eyebrow">本周目标仓位</span>
          <Chip
            text={latest.gate.open ? 'A股闸门开' : 'A股闸门关'}
            level={latest.gate.open ? 'good' : 'neutral'}
          />
        </div>

        <div className="bar" aria-hidden>
          {entries.map(([code, w]) => (
            <span key={code} style={{ width: `${w * 100}%`, background: assetColor(code) }} />
          ))}
        </div>

        <div className="weight-list">
          {entries.map(([code, w]) => (
            <div className="weight-row" key={code}>
              <span className="dot" style={{ background: assetColor(code) }} />
              <span className="name">{assetName(code)}</span>
              {code === latest.leader && <span className="tag">冠军</span>}
              <strong>{pct(w, 1)}</strong>
            </div>
          ))}
        </div>

        <p className="reason">{latest.reason}</p>
      </section>

      <section className="card">
        <h2>闸门</h2>
        <div className="kv">
          <div>
            <span>沪深300 收盘</span>
            <strong>{latest.gate.close.toFixed(3)}</strong>
          </div>
          <div>
            <span>200 日均线</span>
            <strong>{latest.gate.ma200.toFixed(3)}</strong>
          </div>
          <div>
            <span>偏离</span>
            <strong className={latest.gate.open ? 'up' : 'down'}>
              {pct(latest.gate.close / latest.gate.ma200 - 1, 1)}
            </strong>
          </div>
        </div>
        <p className="hint">
          {latest.gate.open
            ? '沪深300 在 200 日均线上方，A 股资产有资格参与轮动。'
            : '沪深300 跌破 200 日均线，A 股资产暂停，只保留标普、黄金与国债。'}
        </p>
      </section>

      <section className="card">
        <h2>资产体检</h2>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>资产</th>
                <th className="r">12M</th>
                <th className="r">63日波动</th>
                <th className="r">距200日线</th>
                <th className="r">状态</th>
              </tr>
            </thead>
            <tbody>
              {latest.assets.map((a) => (
                <tr key={a.code} className={a.eligible ? '' : 'dim'}>
                  <td>
                    <span className="dot" style={{ background: assetColor(a.code) }} />
                    {a.name}
                  </td>
                  <td className={`r ${a.ret12 >= 0 ? 'up' : 'down'}`}>{signedPct(a.ret12, 1)}</td>
                  <td className="r">{pct(a.vol63, 1)}</td>
                  <td className={`r ${a.dist_ma >= 0 ? 'up' : 'down'}`}>{signedPct(a.dist_ma, 1)}</td>
                  <td className="r">
                    <Chip text={a.eligible ? '合格' : '不合格'} level={a.eligible ? 'good' : 'neutral'} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="hint">
          A 股资产看沪深300 的 200 日线；标普500 看自己的 200 日线。冠军 12M 涨幅需 ≥
          {(meta.params.min_trend * 100).toFixed(0)}%，否则不参与轮动。
        </p>
      </section>

      <section className="meta-strip">
        <div>
          <span>信号日</span>
          <strong>{cnDate(latest.asof)}</strong>
        </div>
        <div>
          <span>下次更新</span>
          <strong>每周五收盘后</strong>
        </div>
        <div>
          <span>频率</span>
          <strong>每周 · 无缓冲带</strong>
        </div>
      </section>

      {staleDays > 10 && (
        <div className="alert">数据已 {staleDays} 天未更新，可能抓取失败，请以券商行情为准。</div>
      )}

      <section className="card muted-card">
        <h2>长期基准</h2>
        <div className="kv">
          <div>
            <span>年化</span>
            <strong>{pct(meta.expected.cagr, 1)}</strong>
          </div>
          <div>
            <span>最大回撤</span>
            <strong>{pct(meta.expected.mdd, 1)}</strong>
          </div>
          <div>
            <span>夏普</span>
            <strong>{meta.expected.sharpe.toFixed(2)}</strong>
          </div>
        </div>
        <p className="hint">
          {meta.expected.start} 起的周频回测，含 0.05% 单边成本。样本内结果，实盘预期需打折。
        </p>
      </section>
    </>
  )
}
