"""月度调仓组合回测引擎 + 绩效指标。

约定
----
- 价格：后复权收盘价 / 开盘价（ETF，含分红再投资）
- 信号：调仓日（每月最后一个交易日）收盘后计算
- 成交：下一个交易日开盘价成交，计入双边费用
- 费用：佣金 + 冲击成本，默认单边 0.05%（万3佣金 + 约0.02%滑点，ETF 无印花税）
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

TRADING_DAYS = 252


# --------------------------------------------------------------------------- #
# 绩效指标
# --------------------------------------------------------------------------- #
def perf_stats(nav: pd.Series, rf: float = 0.02, freq: int = TRADING_DAYS) -> dict:
    nav = nav.dropna()
    if len(nav) < 2:
        return {}
    ret = nav.pct_change().dropna()
    years = (nav.index[-1] - nav.index[0]).days / 365.25
    total = nav.iloc[-1] / nav.iloc[0] - 1
    cagr = (1 + total) ** (1 / years) - 1 if years > 0 else np.nan
    vol = ret.std() * np.sqrt(freq)
    sharpe = (ret.mean() * freq - rf) / vol if vol > 0 else np.nan
    downside = ret[ret < 0].std() * np.sqrt(freq)
    sortino = (ret.mean() * freq - rf) / downside if downside and downside > 0 else np.nan
    dd = nav / nav.cummax() - 1
    mdd = dd.min()
    calmar = cagr / abs(mdd) if mdd < 0 else np.nan
    monthly = nav.resample("ME").last().pct_change().dropna()
    win = (monthly > 0).mean() if len(monthly) else np.nan
    return {
        "累计收益": total,
        "年化收益": cagr,
        "年化波动": vol,
        "夏普": sharpe,
        "索提诺": sortino,
        "最大回撤": mdd,
        "卡玛": calmar,
        "月胜率": win,
        "年数": years,
    }


def yearly_returns(nav: pd.Series) -> pd.Series:
    y = nav.resample("YE").last()
    prev = y.shift(1)
    prev.iloc[0] = nav.iloc[0]
    return (y / prev - 1).rename("年度收益")


def drawdown_series(nav: pd.Series) -> pd.Series:
    return nav / nav.cummax() - 1


# --------------------------------------------------------------------------- #
# 回测引擎
# --------------------------------------------------------------------------- #
@dataclass
class Result:
    nav: pd.Series
    weights: pd.DataFrame
    trades: pd.DataFrame
    cost_paid: float = 0.0
    meta: dict = field(default_factory=dict)

    def stats(self, rf: float = 0.02) -> dict:
        return perf_stats(self.nav, rf=rf)

    @property
    def turnover(self) -> float:
        if self.trades.empty:
            return 0.0
        return self.trades.groupby("date")["weight"].sum().mean()


def month_end_trading_days(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    s = pd.Series(index, index=index)
    out = s.groupby([index.year, index.month]).max().values
    return pd.DatetimeIndex(out).sort_values()


class Backtester:
    """月度调仓的 ETF 轮动回测器（支持任意调仓频率）。"""

    def __init__(
        self,
        close: pd.DataFrame,
        open_: pd.DataFrame | None = None,
        cost: float = 0.0005,
        min_history: int = 60,
    ):
        self.close = close.sort_index()
        self.open = (open_ if open_ is not None else close).reindex_like(self.close)
        self.cost = cost
        self.min_history = min_history

    # ------------------------------------------------------------------ #
    def _pair_dates(self, signal_dates, dates, exec_lag):
        pairs = []
        for s in signal_dates:
            pos = dates.searchsorted(s, side="right") - 1 + exec_lag
            if 0 <= pos < len(dates):
                pairs.append((s, dates[pos]))
        # 去重（保留最早的信号）
        seen, out = set(), []
        for s, e in pairs:
            if e in seen:
                continue
            seen.add(e)
            out.append((s, e))
        return out

    def run(
        self,
        weight_fn,
        start: str | None = None,
        end: str | None = None,
        signal_dates: pd.DatetimeIndex | None = None,
        exec_lag: int = 1,
        band: float = 0.0,
    ) -> Result:
        """weight_fn(signal_date, close_upto_signal) -> {code: weight}

        band: 无交易带。目标权重与当前权重之差 <= band 的腿不交易。
        """
        dates = self.close.index
        if start:
            dates = dates[dates >= pd.Timestamp(start)]
        if end:
            dates = dates[dates <= pd.Timestamp(end)]

        if signal_dates is None:
            signal_dates = month_end_trading_days(dates)
        signal_dates = pd.DatetimeIndex([d for d in signal_dates if dates[0] <= d <= dates[-1]])

        pairs = self._pair_dates(signal_dates, dates, exec_lag)
        if not pairs:
            raise ValueError("没有有效的调仓日")

        cash = 1.0
        shares = pd.Series(dtype=float)
        nav_rows, weight_rows, trade_rows = [], [], []
        cost_total = 0.0

        for i, (sig_d, exec_d) in enumerate(pairs):
            px_open = self.open.loc[exec_d]

            def price_of(code, d):
                """执行价：优先开盘价；停牌/缺价时用最近有效收盘价。"""
                p = px_open.get(code, np.nan)
                if not np.isfinite(p) or p <= 0:
                    p = self.close.loc[:d, code].dropna().iloc[-1]
                return p

            # 1) 以开盘价估值
            cur_vals = {c: sh * price_of(c, exec_d) for c, sh in shares.items()}
            cur_val = cash + sum(cur_vals.values())

            # 2) 目标权重
            raw = weight_fn(sig_d, self.close.loc[:sig_d]) or {}
            w = {k: float(v) for k, v in raw.items() if v and v > 0 and k in self.close.columns}
            tot = sum(w.values())
            w = {k: v / tot for k, v in w.items()} if tot > 0 else {}

            # 过滤不可交易（历史不足的剔除；缺价但可估值的保留）
            tradable = {}
            for code, wt in w.items():
                hist = self.close.loc[:sig_d, code].dropna()
                if len(hist) >= self.min_history:
                    tradable[code] = wt
            w = tradable

            # 3) 按无交易带决定每条腿的目标市值
            tgt_vals = {}
            for code in set(w) | set(cur_vals):
                cur_w = cur_vals.get(code, 0.0) / cur_val if cur_val > 0 else 0.0
                tgt_w = w.get(code, 0.0)
                if band > 0 and abs(tgt_w - cur_w) <= band:
                    tgt_vals[code] = cur_vals.get(code, 0.0)
                else:
                    tgt_vals[code] = tgt_w * cur_val

            traded = sum(abs(tgt_vals[c] - cur_vals.get(c, 0.0)) for c in tgt_vals)
            fee = traded * self.cost
            cost_total += fee

            invest = sum(tgt_vals.values())
            if invest > cur_val - fee and invest > 0:
                scale = (cur_val - fee) / invest
                tgt_vals = {c: v * scale for c, v in tgt_vals.items()}

            shares = pd.Series({c: v / price_of(c, exec_d) for c, v in tgt_vals.items()
                                if v > 1e-10})
            cash = max(0.0, cur_val - sum(tgt_vals.values()) - fee)

            for code, wt in w.items():
                trade_rows.append({"date": exec_d, "code": code, "target_weight": wt})

            # 4) 段内每日净值
            nxt = pairs[i + 1][1] if i + 1 < len(pairs) else dates[-1] + pd.Timedelta(days=1)
            seg = dates[(dates >= exec_d) & (dates < nxt)]
            for d in seg:
                vals = {}
                v = cash
                for code, sh in shares.items():
                    p = self.close.at[d, code]
                    if not np.isfinite(p):
                        p = self.close.loc[:d, code].dropna().iloc[-1]
                    vals[code] = sh * p
                    v += vals[code]
                nav_rows.append((d, v))
                weight_rows.append({"date": d, **{c: val / v for c, val in vals.items()}})

        nav = pd.Series(dict(nav_rows)).sort_index()
        nav = nav[~nav.index.duplicated(keep="last")]
        weights = pd.DataFrame(weight_rows).set_index("date")
        trades = pd.DataFrame(trade_rows)
        return Result(
            nav=nav / nav.iloc[0],
            weights=weights,
            trades=trades,
            cost_paid=cost_total,
        )
