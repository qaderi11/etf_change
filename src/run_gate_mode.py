"""闸门口径对比：大盘统一闸门 vs 各资产看自身均线。"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

from backtest import Backtester, yearly_returns
from data import load_panel
from run_frontier import vol_target
from strategies import momentum, above_ma, ann_vol

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "output")
POOL = ["159915", "513100", "510300"]
BOND = "511010"
NAMES = {"159915": "创业板", "513100": "纳指100", "510300": "沪深300", "511010": "国债"}


def gated_rotation(mode: str, lookback: int = 252):
    """mode:
    index  - 全部看沪深300 200日线（现行）
    own    - 各看各的 200 日线，先过滤再排序
    mixed  - A股资产看沪深300，纳指看自身
    """

    def fn(signal_date, close):
        scores = {}
        for c in POOL:
            r = momentum(close, c, lookback, 0)
            if np.isfinite(r):
                scores[c] = r
        if not scores:
            return {BOND: 1.0}

        def eligible(c):
            if mode == "index":
                return above_ma(close, "510300", 200)
            if mode == "own":
                return above_ma(close, c, 200)
            return above_ma(close, "510300", 200) if c != "513100" else above_ma(close, c, 200)

        ok = [c for c in scores if eligible(c)]
        if not ok:
            return {BOND: 1.0}
        return {max(ok, key=scores.get): 1.0}

    return fn


def main():
    close = load_panel("close", POOL + [BOND])
    open_ = load_panel("open", POOL + [BOND])
    bt = Backtester(close, open_, cost=0.0005, min_history=260)

    modes = {"现行：大盘统一闸门": "index", "各看自身均线": "own", "混合：A股看300/纳指看自身": "mixed"}
    rows, navs = [], {}
    for name, mode in modes.items():
        res = bt.run(vol_target(gated_rotation(mode), 0.15), start="2014-06-01")
        s = res.stats()
        rows.append({
            "方案": name, "年化": s["年化收益"], "波动": s["年化波动"], "夏普": s["夏普"],
            "最大回撤": s["最大回撤"], "卡玛": s["卡玛"],
            "平均股票仓位": 1 - res.weights[BOND].fillna(0).mean(),
        })
        navs[name] = res.nav
        yr = yearly_returns(res.nav)
        print(f"\n{name}: " + "  ".join(f"{i.year}:{v:+.1%}" for i, v in yr.items()))

    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(OUT, "tables", "gate_mode_compare.csv"), index=False, encoding="utf-8-sig")
    print("\n" + df.round(3).to_string(index=False))

    # 今日信号
    print("\n今日信号：")
    for name, mode in modes.items():
        w = gated_rotation(mode)(close.index[-1], close)
        print(f"  {name}: " + ", ".join(f"{NAMES[c]} {v:.0%}" for c, v in w.items()))

    # 2021 年纳指暴露
    print("\n2021 年纳指持仓时间占比：")
    for name, mode in modes.items():
        res = bt.run(vol_target(gated_rotation(mode), 0.15), start="2014-06-01")
        w = res.weights["513100"].fillna(0)
        print(f"  {name}: {(w.loc['2021'] > 0.01).mean():.0%}")


if __name__ == "__main__":
    main()
