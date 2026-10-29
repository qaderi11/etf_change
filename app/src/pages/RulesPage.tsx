import { pct } from '../lib/format'
import type { Meta } from '../lib/types'

export function RulesPage({ meta }: { meta: Meta }) {
  const p = meta.params
  return (
    <>
      <section className="card">
        <h2>四步规则</h2>
        <ol className="steps">
          <li>
            <strong>定合格资产</strong>
            <p>
              A 股三只（沪深300、中证500、创业板）要求沪深300 收盘站上 200 日均线；标普500
              要求自己站上 200 日均线。
            </p>
          </li>
          <li>
            <strong>选冠军</strong>
            <p>
              合格资产中，取过去 252 个交易日涨幅最大的一只。若它的涨幅低于{" "}
              {pct(p.min_trend, 0)} 趋势阈值，视为“没有趋势”，只留黄金与国债。
            </p>
          </li>
          <li>
            <strong>定股票仓位</strong>
            <p>
              冠军仓位 = min(1, {pct(p.vol_target, 0)} / 63日年化波动) × {(1 - p.gold_sleeve) * 100}%。
              波动越高，仓位越低。
            </p>
          </li>
          <li>
            <strong>分配</strong>
            <p>
              黄金固定 {pct(p.gold_sleeve, 0)}，其余买国债。每周最后一个交易日收盘后计算，次一交易日开盘执行。
            </p>
          </li>
        </ol>
      </section>

      <section className="card">
        <h2>参数</h2>
        <div className="params">
          <div>
            <span>形成期</span>
            <strong>{p.lookback} 日</strong>
          </div>
          <div>
            <span>均线</span>
            <strong>{p.gate_ma} 日</strong>
          </div>
          <div>
            <span>波动窗口</span>
            <strong>{p.vol_window} 日</strong>
          </div>
          <div>
            <span>目标波动</span>
            <strong>{pct(p.vol_target, 0)}</strong>
          </div>
          <div>
            <span>黄金底仓</span>
            <strong>{pct(p.gold_sleeve, 0)}</strong>
          </div>
          <div>
            <span>趋势阈值</span>
            <strong>{pct(p.min_trend, 0)}</strong>
          </div>
          <div>
            <span>成本假设</span>
            <strong>{pct(p.cost, 2)} 单边</strong>
          </div>
        </div>
      </section>

      <section className="card">
        <h2>要知道的风险</h2>
        <ul className="list">
          <li>
            <strong>它不是 alpha 策略。</strong>相对等权的超额在统计上不显著，收益主要来自仓位管理与黄金、国债。
          </li>
          <li>
            <strong>会错过独立行情。</strong>沪深300 破位时 A 股资产全部暂停，2020、2021
            都因此错过过创业板和标普的强势段。
          </li>
          <li>
            <strong>周频成本更高。</strong>年换手约 1.1 倍，累计成本约为月频的两倍；单边成本超过 0.15%
            时优势消失。
          </li>
          <li>
            <strong>QDII 溢价。</strong>标普500 溢价过高时买入会额外吃亏，建议溢价 &gt;3% 时暂缓。
          </li>
          <li>
            <strong>历史不代表未来。</strong>样本内年化 {pct(meta.expected.cagr, 1)}，实盘请按 8–10% 预期。
          </li>
        </ul>
      </section>

      <section className="card muted-card">
        <h2>数据</h2>
        <p className="hint">
          行情来自腾讯财经前复权日线，每日收盘后更新。信号在每周最后一个交易日收盘后生成，页面上的
          “信号日”即数据截止日。若自动更新失败，页面会保留上一次信号并提示数据过期。
        </p>
      </section>
    </>
  )
}
