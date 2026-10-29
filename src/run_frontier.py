"""回撤预算前沿：波动率目标 / 固定股债比例，找出 CAGR-MDD 的可行边界。"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from backtest import Backtester, perf_stats
from data import load_panel
from strategies import momentum_rotation

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "output")
os.makedirs(os.path.join(OUT, "tables"), exist_ok=True)
os.makedirs(os.path.join(OUT, "figs"), exist_ok=True)

POOL = ["159915", "513100", "510300"]
BOND = "511010"
START = "2014-06-01"
COST = 0.0005
NAMES = {"159915": "创业板", "513100": "纳指100", "510300": "沪深300", "511010": "国债"}


def ann_vol(close, code, n=63):
    px = close[code].dropna()
    if len(px) < n + 1:
        return np.nan
    return px.iloc[-n:].pct_change().std() * np.sqrt(252)


def vol_target(base, target: float, lookback: int = 63):
    def fn(sig, close):
        w = base(sig, close)
        if not w:
            return w
        if w.get(BOND, 0) >= 0.999:
            return w
        v = sum(wt * ann_vol(close, c, lookback) for c, wt in w.items()
                if c != BOND and np.isfinite(ann_vol(close, c, lookback)))
        lev = min(1.0, target / v) if v and v > 0 else 1.0
        out = {c: wt * lev for c, wt in w.items() if c != BOND}
        out[BOND] = out.get(BOND, 0.0) + (1 - lev)
        return out

    return fn


def fixed_mix(base, equity: float):
    def fn(sig, close):
        w = base(sig, close)
        out = {c: wt * equity for c, wt in w.items() if c != BOND}
        out[BOND] = out.get(BOND, 0.0) + (1 - equity)
        return out

    return fn


def main():
    close = load_panel("close", POOL + [BOND])
    open_ = load_panel("open", POOL + [BOND])
    bt = Backtester(close, open_, cost=COST, min_history=260)

    base = momentum_rotation(POOL, 252, 1, skip=0, market_gate=200, defensive=BOND)
    res = bt.run(base, start=START)
    nav = res.nav
    dd = nav / nav.cummax() - 1
    trough = dd.idxmin()
    peak = nav.loc[:trough].idxmax()
    print(f"C 组合最大回撤 {dd.min():.1%}：峰值 {peak.date()} → 谷底 {trough.date()}")

    rows = []
    r = res.stats()
    rows.append({"方案": "C_原始", "年化": r["年化收益"], "波动": r["年化波动"],
                 "夏普": r["夏普"], "最大回撤": r["最大回撤"], "卡玛": r["卡玛"]})

    for tgt in [0.08, 0.10, 0.12, 0.15, 0.18, 0.22, 0.30]:
        rr = bt.run(vol_target(base, tgt), start=START)
        s = rr.stats()
        rows.append({"方案": f"波动目标{tgt:.0%}", "年化": s["年化收益"], "波动": s["年化波动"],
                     "夏普": s["夏普"], "最大回撤": s["最大回撤"], "卡玛": s["卡玛"]})

    for eq in [0.2, 0.4, 0.6, 0.8]:
        rr = bt.run(fixed_mix(base, eq), start=START)
        s = rr.stats()
        rows.append({"方案": f"股票上限{eq:.0%}", "年化": s["年化收益"], "波动": s["年化波动"],
                     "夏普": s["夏普"], "最大回撤": s["最大回撤"], "卡玛": s["卡玛"]})

    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(OUT, "tables", "drawdown_frontier.csv"), index=False, encoding="utf-8-sig")
    print(df.round(4).to_string(index=False), flush=True)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS"]
    plt.rcParams["axes.unicode_minus"] = False

    fig, ax = plt.subplots(figsize=(8, 5.5))
    for _, row in df.iterrows():
        ax.scatter(abs(row["最大回撤"]) * 100, row["年化"] * 100, s=60)
        ax.annotate(row["方案"], (abs(row["最大回撤"]) * 100, row["年化"] * 100),
                    textcoords="offset points", xytext=(5, 4), fontsize=8)
    ax.set_xlabel("最大回撤 (%)")
    ax.set_ylabel("年化收益 (%)")
    ax.set_title("回撤预算前沿：想少亏多少，就要放弃多少收益")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "figs", "fig3_frontier.png"), dpi=150)
    plt.close(fig)

    # 选三个代表画净值
    fig, ax = plt.subplots(figsize=(11, 5.5))
    for label, fn in [("C_原始", base), ("波动目标15%", vol_target(base, 0.15)),
                      ("波动目标10%", vol_target(base, 0.10))]:
        rr = bt.run(fn, start=START)
        ax.plot(rr.nav.index, rr.nav, lw=1.3, label=f"{label} (MDD {(rr.nav/rr.nav.cummax()-1).min():.0%})")
    ax.set_yscale("log")
    ax.legend()
    ax.grid(alpha=0.3)
    ax.set_title("不同回撤预算下的净值")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "figs", "fig4_voltgt.png"), dpi=150)
    plt.close(fig)
    print(f"\n已保存 {OUT}")


if __name__ == "__main__":
    main()
