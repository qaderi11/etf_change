"""v2 净值曲线：四资产池 + 黄金底仓 vs 基准。"""
from __future__ import annotations

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backtest import Backtester
from data import load_panel
from run_frontier import vol_target
from run_pool import gated
from strategies import buy_hold, equal_weight

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "output")
BOND = "511010"
GOLD = "518880"
POOL4 = ["159915", "510300", "510500", "513500"]
POOL3 = ["159915", "513100", "510300"]
START = "2015-01-01"

COLORS = {
    "沪深300": "#8c8c8c",
    "四资产等权": "#7fb3d5",
    "v1：三资产+黄金": "#e67e22",
    "v2：四资产+黄金": "#c0392b",
}


def sleeve(base, g=0.2):
    def fn(s, cl):
        w = base(s, cl)
        out = {c: v * (1 - g) for c, v in w.items() if c != BOND}
        out[GOLD] = g
        out[BOND] = out.get(BOND, 0.0) + w.get(BOND, 0.0) * (1 - g)
        return out

    return fn


def main():
    codes = sorted(set(POOL4 + POOL3 + [GOLD, BOND]))
    close = load_panel("close", codes)
    open_ = load_panel("open", codes)
    bt = Backtester(close, open_, cost=0.0005, min_history=260)

    cfgs = {
        "沪深300": buy_hold("510300"),
        "四资产等权": equal_weight(POOL4),
        "v1：三资产+黄金": sleeve(vol_target(gated(POOL3, "mixed"), 0.12)),
        "v2：四资产+黄金": sleeve(vol_target(gated(POOL4, "mixed"), 0.12)),
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
        lw = 2.2 if name.startswith("v2") else (1.6 if name.startswith("v1") else 1.2)
        axes[0].plot(nav.index, nav, lw=lw, color=COLORS[name],
                     label=f"{name}  年化 {s['年化收益']:.1%} | 回撤 {s['最大回撤']:.1%} | 夏普 {s['夏普']:.2f}")
    axes[0].set_yscale("log")
    axes[0].set_yticks([1, 1.5, 2, 3, 4])
    axes[0].yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"{v:.1f}x"))
    axes[0].yaxis.set_minor_formatter(mtick.NullFormatter())
    axes[0].yaxis.get_offset_text().set_visible(False)
    axes[0].set_title("v2 净值曲线（2015-01 ~ 2026-10，对数轴，含 0.05% 单边成本）", fontsize=13, pad=12)
    axes[0].legend(loc="upper left", fontsize=9.5, framealpha=0.9)
    axes[0].grid(alpha=0.25, which="both")

    for name, nav in navs.items():
        axes[1].plot(nav.index, nav / nav.cummax() - 1, lw=1.2, color=COLORS[name], label=name)
    axes[1].yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"{v:.0%}"))
    axes[1].set_title("回撤", fontsize=11)
    axes[1].grid(alpha=0.25)
    axes[1].set_ylim(-0.58, 0.03)

    fig.tight_layout()
    path = os.path.join(OUT, "figs", "nav_curve_v2.png")
    fig.savefig(path, dpi=170, bbox_inches="tight")
    plt.close(fig)
    print("saved", path)


if __name__ == "__main__":
    main()
