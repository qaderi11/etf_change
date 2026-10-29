"""净值曲线图：推荐配置 vs 基准 vs 混合闸门修正版。"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backtest import Backtester
from data import load_panel
from run_frontier import vol_target
from run_gate_mode import gated_rotation
from strategies import buy_hold, equal_weight, momentum_rotation

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "output")
POOL = ["159915", "513100", "510300"]
BOND = "511010"
START = "2014-06-01"

COLORS = {
    "沪深300": "#8c8c8c",
    "三资产等权": "#7fb3d5",
    "推荐：300闸门 + VT15": "#c0392b",
    "修正：混合闸门 + VT12": "#e67e22",
}


def main():
    close = load_panel("close", POOL + [BOND])
    open_ = load_panel("open", POOL + [BOND])
    bt = Backtester(close, open_, cost=0.0005, min_history=260)

    cfgs = {
        "沪深300": buy_hold("510300"),
        "三资产等权": equal_weight(POOL),
        "推荐：300闸门 + VT15": vol_target(
            momentum_rotation(POOL, 252, 1, skip=0, market_gate=200, defensive=BOND), 0.15),
        "修正：混合闸门 + VT12": vol_target(gated_rotation("mixed"), 0.12),
    }
    navs, stats = {}, {}
    for name, fn in cfgs.items():
        res = bt.run(fn, start=START)
        navs[name] = res.nav
        stats[name] = res.stats()

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mtick

    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS"]
    plt.rcParams["axes.unicode_minus"] = False

    fig, axes = plt.subplots(2, 1, figsize=(13, 8.6), sharex=True,
                             gridspec_kw={"height_ratios": [2.6, 1]})

    for name, nav in navs.items():
        s = stats[name]
        lw = 2.0 if name.startswith("推荐") else (1.6 if name.startswith("修正") else 1.2)
        style = "--" if name.startswith("修正") else "-"
        axes[0].plot(nav.index, nav, lw=lw, ls=style, color=COLORS[name],
                     label=f"{name}   年化 {s['年化收益']:.1%} | 回撤 {s['最大回撤']:.1%} | 夏普 {s['夏普']:.2f}")
    axes[0].set_yscale("log")
    axes[0].set_yticks([1, 1.5, 2, 3, 4, 5])
    axes[0].yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"{v:.1f}x"))
    axes[0].yaxis.set_minor_formatter(mtick.NullFormatter())
    axes[0].yaxis.get_offset_text().set_visible(False)
    axes[0].set_title("ETF 轮动净值曲线（2014-06 ~ 2026-10，对数轴，含 0.05% 单边成本）",
                      fontsize=13, pad=12)
    axes[0].legend(loc="upper left", fontsize=9.5, framealpha=0.9)
    axes[0].grid(alpha=0.25, which="both")

    # 标注 2015 回撤
    nav = navs["推荐：300闸门 + VT15"]
    dd = nav / nav.cummax() - 1
    trough = dd.idxmin()
    peak = nav.loc[:trough].idxmax()
    axes[0].axvspan(peak, trough, color="#c0392b", alpha=0.10, lw=0)
    axes[0].annotate(f"2015 回撤 {dd.min():.1%}", xy=(trough, nav.loc[trough]),
                     xytext=(pd.Timestamp("2016-06-01"), nav.loc[trough] * 0.86),
                     fontsize=9, color="#c0392b",
                     arrowprops=dict(arrowstyle="->", color="#c0392b", lw=0.9))

    for name, nav in navs.items():
        axes[1].plot(nav.index, nav / nav.cummax() - 1, lw=1.2, color=COLORS[name], label=name)
    axes[1].yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"{v:.0%}"))
    axes[1].set_title("回撤", fontsize=11)
    axes[1].grid(alpha=0.25)
    axes[1].set_ylim(-0.58, 0.03)

    fig.tight_layout()
    path = os.path.join(OUT, "figs", "nav_curve.png")
    fig.savefig(path, dpi=170, bbox_inches="tight")
    plt.close(fig)
    print("saved", path)


if __name__ == "__main__":
    main()
