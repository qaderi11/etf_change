"""闸门对比回测：12M 动量选强 + 不同的回撤控制方式。"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from backtest import Backtester, perf_stats, yearly_returns
from data import load_panel
from strategies import momentum_rotation, equal_weight, buy_hold

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "output")
os.makedirs(os.path.join(OUT, "tables"), exist_ok=True)
os.makedirs(os.path.join(OUT, "figs"), exist_ok=True)

POOL = ["159915", "513100", "510300"]
BOND = "511010"
START = "2014-06-01"
COST = 0.0005
NAMES = {"159915": "创业板", "513100": "纳指100", "510300": "沪深300", "511010": "国债"}


def main():
    close = load_panel("close", POOL + [BOND])
    open_ = load_panel("open", POOL + [BOND])
    bt = Backtester(close, open_, cost=COST, min_history=260)

    strategies = {
        "沪深300买入持有": buy_hold("510300"),
        "三资产等权": equal_weight(POOL),
        "A_12M选强_无闸门": momentum_rotation(POOL, 252, 1, skip=0, defensive=BOND),
        "B_12M选强+绝对动量": momentum_rotation(
            POOL, 252, 1, skip=0, abs_vs=BOND, defensive=BOND),
        "C_12M选强+300均线": momentum_rotation(
            POOL, 252, 1, skip=0, market_gate=200, defensive=BOND),
        "D_12M选强+双闸门": momentum_rotation(
            POOL, 252, 1, skip=0, abs_vs=BOND, market_gate=200, defensive=BOND),
        "E_12M选强+自身均线": momentum_rotation(
            POOL, 252, 1, skip=0, ma_filter=200, defensive=BOND),
        "F_6M选强+双闸门": momentum_rotation(
            POOL, 126, 1, skip=0, abs_vs=BOND, market_gate=200, defensive=BOND),
        "G_12M选前2+双闸门": momentum_rotation(
            POOL, 252, 2, skip=0, abs_vs=BOND, market_gate=200, defensive=BOND),
    }

    rows, navs, holds = [], {}, {}
    for name, fn in strategies.items():
        res = bt.run(fn, start=START)
        st = res.stats()
        # 月度换手
        tr = res.trades.groupby("date")["target_weight"].sum()
        turns = []
        prev = {}
        for d, g in res.trades.groupby("date"):
            cur = dict(zip(g["code"], g["target_weight"]))
            turns.append(sum(abs(cur.get(k, 0) - prev.get(k, 0)) for k in set(cur) | set(prev)) / 2)
            prev = cur
        st.update({"策略": name, "月均换手": np.mean(turns) if turns else np.nan,
                   "持债月占比": float((res.weights.get(BOND, pd.Series(0, index=res.weights.index)) > 0.5).mean())
                   if not res.weights.empty else np.nan})
        rows.append(st)
        navs[name] = res.nav
        holds[name] = res.weights

    df = pd.DataFrame(rows)
    cols = ["策略", "累计收益", "年化收益", "年化波动", "夏普", "最大回撤", "卡玛", "月胜率", "月均换手", "持债月占比"]
    df = df[cols]
    df.to_csv(os.path.join(OUT, "tables", "gate_comparison.csv"), index=False, encoding="utf-8-sig")
    print(df.round(4).to_string(index=False), flush=True)

    # 年度收益
    yr = pd.DataFrame({k: yearly_returns(v) for k, v in navs.items()})
    yr.index = yr.index.year
    yr.to_csv(os.path.join(OUT, "tables", "gate_yearly.csv"), encoding="utf-8-sig")
    print("\n年度收益")
    print((yr * 100).round(1).to_string(), flush=True)

    # 捕获率：相对"每月都持最强"的完美预知
    close_m = close[POOL].resample("ME").last()
    best_m = close_m.pct_change().max(axis=1)
    print("\n捕获率（对比完美预知）")
    for name, nav in navs.items():
        r = nav.resample("ME").last().pct_change()
        mask = r.notna() & best_m.notna()
        perfect_final = (1 + best_m[mask]).prod()
        capture = (nav.iloc[-1] - 1) / (perfect_final - 1)
        hit = (r[mask] >= best_m[mask] - 0.005).mean()
        print(f"{name}: 利润捕获 {capture:.1%}  当月=最强 {hit:.1%} (随机 33.3%)")

    # 图
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS"]
    plt.rcParams["axes.unicode_minus"] = False

    fig, axes = plt.subplots(2, 1, figsize=(12, 9), sharex=True,
                             gridspec_kw={"height_ratios": [2, 1]})
    for name, nav in navs.items():
        axes[0].plot(nav.index, nav, lw=1.3, label=name)
    axes[0].set_yscale("log")
    axes[0].set_title("闸门对比：净值（对数）")
    axes[0].legend(fontsize=8, ncol=2)
    axes[0].grid(alpha=0.3)
    for name, nav in navs.items():
        axes[1].plot(nav.index, nav / nav.cummax() - 1, lw=1.1, label=name)
    axes[1].set_title("回撤")
    axes[1].grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "figs", "fig2_gates.png"), dpi=150)
    plt.close(fig)
    print(f"\n已保存 {OUT}")


if __name__ == "__main__":
    main()
