"""加入标普500（513500）后的池子对比。统一从 2015-01 起，保证可比。"""
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
SPX = "513500"
START = "2015-01-01"
NAMES = {"159915": "创业板", "513100": "纳指100", "510300": "沪深300",
         "510500": "中证500", "518880": "黄金", "511010": "国债", "513500": "标普500"}


def sleeve(base, g=0.2):
    def fn(s, cl):
        w = base(s, cl)
        out = {c: v * (1 - g) for c, v in w.items() if c != BOND}
        out[GOLD] = g
        out[BOND] = out.get(BOND, 0.0) + w.get(BOND, 0.0) * (1 - g)
        return out

    return fn


def main():
    pools = {
        "3资产": ["159915", "513100", "510300"],
        "4资产（+标普500）": ["159915", "513100", "510300", SPX],
        "5资产（+标普+中证500）": ["159915", "513100", "510300", SPX, "510500"],
        "纯A股+标普": ["159915", "510300", SPX],
    }
    codes = sorted(set([c for v in pools.values() for c in v] + [GOLD, BOND]))
    close = load_panel("close", codes)
    open_ = load_panel("open", codes)
    bt = Backtester(close, open_, cost=0.0005, min_history=260)

    rows, navs = [], {}
    for name, pool in pools.items():
        res = bt.run(sleeve(vol_target(gated(pool, "mixed"), 0.12)), start=START)
        s = res.stats()
        rows.append({"池子": name, "年化": s["年化收益"], "波动": s["年化波动"], "夏普": s["夏普"],
                     "最大回撤": s["最大回撤"], "卡玛": s["卡玛"]})
        navs[name] = res.nav

    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(OUT, "sp500_pool.csv"), index=False, encoding="utf-8-sig")
    print(df.round(3).to_string(index=False))

    print("\n### 分年度（%）")
    y = pd.DataFrame({k: yearly_returns(v) for k, v in navs.items()})
    y.index = y.index.year
    print((y * 100).round(0).to_string())

    print("\n### 纳指 vs 标普 相关性")
    r = close[["513100", SPX]].pct_change().dropna()
    print(f"  日收益相关 {r.corr().iloc[0,1]:.2f}")
    rm = close[["513100", SPX]].resample("ME").last().pct_change().dropna()
    print(f"  月收益相关 {rm.corr().iloc[0,1]:.2f}")
    print(f"  12M 收益相关 {close[['513100',SPX]].pct_change(252).dropna().corr().iloc[0,1]:.2f}")

    print("\n### 4资产版归因")
    res = bt.run(sleeve(vol_target(gated(pools["4资产（+标普500）"], "mixed"), 0.12)), start=START)
    w = res.weights.reindex(columns=codes).fillna(0).shift(1).dropna()
    rr = close.pct_change().reindex(w.index).fillna(0)
    contrib = (w * rr).sum()
    total = contrib.sum()
    for c in codes:
        if abs(contrib[c]) > 1e-6:
            print(f"  {NAMES[c]:<6} 贡献 {contrib[c]:+.1%}  占比 {contrib[c]/total:+.0%}  平均权重 {w[c].mean():.0%}")


if __name__ == "__main__":
    main()
