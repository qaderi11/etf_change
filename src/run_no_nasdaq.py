"""去掉纳指会怎样：池子对比 + 收益归因。"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backtest import Backtester, yearly_returns
from data import load_panel
from run_frontier import vol_target
from run_pool import gated

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "output", "tables")
BOND = "511010"
GOLD = "518880"
START = "2014-08-01"
NAMES = {"159915": "创业板", "513100": "纳指100", "510300": "沪深300",
         "510500": "中证500", "518880": "黄金", "511010": "国债"}


def with_sleeve(base, g=0.2):
    def fn(s, cl):
        w = base(s, cl)
        out = {c: v * (1 - g) for c, v in w.items() if c != BOND}
        out[GOLD] = g
        out[BOND] = out.get(BOND, 0.0) + w.get(BOND, 0.0) * (1 - g)
        return out

    return fn


def main():
    pools = {
        "3资产（含纳指）": ["159915", "513100", "510300"],
        "2资产（创业板+300）": ["159915", "510300"],
        "3资产（纯A股：+中证500）": ["159915", "510300", "510500"],
    }
    codes = sorted(set([c for v in pools.values() for c in v] + [GOLD, BOND]))
    close = load_panel("close", codes)
    open_ = load_panel("open", codes)
    bt = Backtester(close, open_, cost=0.0005, min_history=260)

    rows = []
    for name, pool in pools.items():
        for g in [0.0, 0.2]:
            res = bt.run(with_sleeve(vol_target(gated(pool, "mixed"), 0.12), g), start=START)
            st = res.stats()
            rows.append({"池子": name, "黄金底仓": f"{g:.0%}", "年化": st["年化收益"],
                         "波动": st["年化波动"], "夏普": st["夏普"], "最大回撤": st["最大回撤"]})
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(OUT, "no_nasdaq.csv"), index=False, encoding="utf-8-sig")
    print(df.round(3).to_string(index=False))

    print("\n### 分年度（含 20% 黄金）")
    for name, pool in pools.items():
        res = bt.run(with_sleeve(vol_target(gated(pool, "mixed"), 0.12), 0.2), start=START)
        y = yearly_returns(res.nav)
        print(f"{name}: " + " ".join(f"{i.year}:{v:+.0%}" for i, v in y.items()))

    print("\n### 收益归因（3资产 + 20%黄金，按日权重×日收益累加）")
    res = bt.run(with_sleeve(vol_target(gated(pools["3资产（含纳指）"], "mixed"), 0.12), 0.2),
                 start=START)
    w = res.weights.reindex(columns=codes).fillna(0).shift(1).dropna()
    r = close.pct_change().reindex(w.index).fillna(0)
    contrib = (w * r).sum()
    total = contrib.sum()
    for c in codes:
        if abs(contrib[c]) > 1e-6:
            print(f"  {NAMES[c]:<6} 贡献 {contrib[c]:+.1%}  占总收益 {contrib[c]/total:+.0%}  "
                  f"平均权重 {w[c].mean():.0%}")

    print("\n### 纳指持仓时间")
    ww = res.weights
    print(f"  纳指有仓位月份占比: {(ww['513100'].fillna(0).resample('ME').last() > 0.01).mean():.0%}")


if __name__ == "__main__":
    main()
