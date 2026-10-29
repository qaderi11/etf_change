"""最终对比：推荐配置 vs 基准，输出图表与年度表。"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from backtest import Backtester, yearly_returns
from data import load_panel
from strategies import momentum_rotation, buy_hold, equal_weight
from run_frontier import vol_target

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "output")
POOL = ["159915", "513100", "510300"]
BOND = "511010"
START = "2014-06-01"
NAMES = {"159915": "创业板", "513100": "纳指100", "510300": "沪深300", "511010": "国债"}


def main():
    close = load_panel("close", POOL + [BOND])
    open_ = load_panel("open", POOL + [BOND])
    bt = Backtester(close, open_, cost=0.0005, min_history=260)

    base = momentum_rotation(POOL, 252, 1, skip=0, market_gate=200, defensive=BOND)
    configs = {
        "沪深300": buy_hold("510300"),
        "三资产等权": equal_weight(POOL),
        "动量+均线(无VT)": base,
        "推荐：+VT15%": vol_target(base, 0.15),
    }
    rows, navs, holds = [], {}, {}
    for name, fn in configs.items():
        res = bt.run(fn, start=START)
        s = res.stats()
        w = res.weights.fillna(0)
        equity = 1 - w.get(BOND, pd.Series(0.0, index=w.index))
        rows.append({
            "方案": name, "年化": s["年化收益"], "波动": s["年化波动"], "夏普": s["夏普"],
            "最大回撤": s["最大回撤"], "卡玛": s["卡玛"], "月胜率": s["月胜率"],
            "平均股票仓位": equity.mean(),
        })
        navs[name] = res.nav
        holds[name] = w

    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(OUT, "tables", "final_compare.csv"), index=False, encoding="utf-8-sig")
    print(df.round(3).to_string(index=False), flush=True)

    yr = pd.DataFrame({k: yearly_returns(v) for k, v in navs.items()})
    yr.index = yr.index.year
    yr.to_csv(os.path.join(OUT, "tables", "final_yearly.csv"), encoding="utf-8-sig")
    print("\n年度收益(%)")
    print((yr * 100).round(1).to_string(), flush=True)

    # 换手与切换次数
    res = bt.run(vol_target(base, 0.15), start=START)
    per_year = res.trades.groupby(res.trades["date"].dt.year)["target_weight"].sum()
    print(f"\n平均年换手(权重和) {per_year.mean():.2f}", flush=True)
    w = res.weights.fillna(0)
    print("持仓时间占比：", {NAMES[c]: round(w[c].gt(0.01).mean(), 3) for c in POOL + [BOND]})

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS"]
    plt.rcParams["axes.unicode_minus"] = False

    fig, axes = plt.subplots(3, 1, figsize=(12, 11), sharex=True,
                             gridspec_kw={"height_ratios": [2.2, 1, 1]})
    for name, nav in navs.items():
        axes[0].plot(nav.index, nav, lw=1.4, label=f"{name}  ({nav.iloc[-1]-1:+.0%})")
    axes[0].set_yscale("log")
    axes[0].set_title("推荐配置 vs 基准：净值（对数，2014-06 ~ 2026-10）")
    axes[0].legend(fontsize=9)
    axes[0].grid(alpha=0.3)

    for name, nav in navs.items():
        axes[1].plot(nav.index, nav / nav.cummax() - 1, lw=1.1, label=name)
    axes[1].set_title("回撤")
    axes[1].grid(alpha=0.3)

    eq = 1 - holds["推荐：+VT15%"].get(BOND, pd.Series(0.0, index=holds["推荐：+VT15%"].index))
    axes[2].fill_between(eq.index, 0, eq, color="#1f77b4", alpha=0.5, step="pre")
    axes[2].set_ylim(0, 1.05)
    axes[2].set_title("推荐配置的股票仓位（其余为国债）")
    axes[2].grid(alpha=0.3)

    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "figs", "fig5_final.png"), dpi=150)
    plt.close(fig)

    # 年度收益柱状
    fig, ax = plt.subplots(figsize=(11, 4.5))
    x = np.arange(len(yr.index))
    width = 0.2
    for i, col in enumerate(yr.columns):
        ax.bar(x + (i - 1.5) * width, yr[col] * 100, width, label=col)
    ax.set_xticks(x)
    ax.set_xticklabels(yr.index, rotation=0)
    ax.axhline(0, color="black", lw=0.8)
    ax.set_ylabel("年度收益 (%)")
    ax.set_title("分年度收益")
    ax.legend(fontsize=9)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "figs", "fig6_yearly.png"), dpi=150)
    plt.close(fig)
    print(f"\n已保存 {OUT}", flush=True)


if __name__ == "__main__":
    main()
