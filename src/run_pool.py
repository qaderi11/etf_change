"""P0 扩池：3 资产 vs 5 资产（加中证500、黄金）。"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backtest import Backtester, yearly_returns
from data import load_panel
from run_frontier import vol_target
from strategies import momentum, above_ma, ann_vol

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "output")
BOND = "511010"
A_SHARE = {"159915", "510300", "510500"}     # 看沪深300 200日线
OWN = {"513100", "518880"}                    # 看自身 200日线
NAMES = {"159915": "创业板", "513100": "纳指100", "510300": "沪深300",
         "510500": "中证500", "518880": "黄金", "511010": "国债"}
POOL3 = ["159915", "513100", "510300"]
POOL5 = ["159915", "513100", "510300", "510500", "518880"]
START = "2014-08-01"


def gated(pool, gate: str = "mixed", lookback: int = 252, ma: int = 200, a_share=None,
          min_trend: float = 0.0):
    a_sh = A_SHARE if a_share is None else a_share

    def fn(sig, close):
        scores = {}
        for c in pool:
            r = momentum(close, c, lookback, 0)
            if np.isfinite(r):
                scores[c] = r
        if not scores:
            return {BOND: 1.0}

        def ok(c):
            if gate == "own":
                return above_ma(close, c, ma)
            if gate == "index":
                return above_ma(close, "510300", ma)
            return above_ma(close, "510300", ma) if c in a_sh else above_ma(close, c, ma)

        eligible = [c for c in scores if ok(c)]
        if not eligible:
            return {BOND: 1.0}
        lead = max(eligible, key=scores.get)
        if min_trend and scores[lead] < min_trend:
            return {BOND: 1.0}
        return {lead: 1.0}

    return fn


def main():
    close = load_panel("close", POOL5 + [BOND])
    open_ = load_panel("open", POOL5 + [BOND])
    bt = Backtester(close, open_, cost=0.0005, min_history=260)

    cfgs = {
        "3资产 混合闸门 VT12（现行修正版）": (POOL3, "mixed", 0.12),
        "5资产 混合闸门 VT12": (POOL5, "mixed", 0.12),
        "5资产 混合闸门 VT15": (POOL5, "mixed", 0.15),
        "5资产 各自均线 VT12": (POOL5, "own", 0.12),
        "5资产 统一300闸门 VT12": (POOL5, "index", 0.12),
    }
    rows, navs = [], {}
    for name, (pool, gate, tgt) in cfgs.items():
        res = bt.run(vol_target(gated(pool, gate), tgt), start=START)
        s = res.stats()
        rows.append({"方案": name, "年化": s["年化收益"], "波动": s["年化波动"], "夏普": s["夏普"],
                     "最大回撤": s["最大回撤"], "卡玛": s["卡玛"],
                     "平均股票仓位": 1 - res.weights[BOND].fillna(0).mean()})
        navs[name] = res.nav

    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(OUT, "tables", "p0_pool_compare.csv"), index=False, encoding="utf-8-sig")
    print(df.round(3).to_string(index=False))

    print("\n### 分年度（5资产 混合 VT12）")
    y = yearly_returns(navs["5资产 混合闸门 VT12"])
    print({i.year: f"{v:+.1%}" for i, v in y.items()})

    print("\n### 分区间")
    for label, s, e in [("2014-08~2019-12", "2014-08-01", "2019-12-31"),
                        ("2020-01~2026-10", "2020-01-01", None)]:
        for name in ["3资产 混合闸门 VT12（现行修正版）", "5资产 混合闸门 VT12"]:
            pool, gate, tgt = cfgs[name]
            st = bt.run(vol_target(gated(pool, gate), tgt), start=s, end=e).stats()
            print(f"  {label} {name}: 年化{st['年化收益']:.1%} 夏普{st['夏普']:.2f} 回撤{st['最大回撤']:.1%}")

    print("\n### 形成期敏感性（5资产 混合 VT12）")
    for lb in [126, 189, 252, 315]:
        st = bt.run(vol_target(gated(POOL5, "mixed", lb), 0.12), start=START).stats()
        print(f"  {lb//21}M: 年化{st['年化收益']:.1%} 夏普{st['夏普']:.2f} 回撤{st['最大回撤']:.1%}")

    print("\n### 今日信号（5资产 混合）")
    d = close.index[-1]
    scores = {c: momentum(close, c, 252, 0) for c in POOL5}
    ok = {c: (above_ma(close, "510300", 200) if c in A_SHARE else above_ma(close, c, 200)) for c in POOL5}
    for c in POOL5:
        print(f"  {NAMES[c]:<6} 12M {scores[c]:+.1%}  均线{'上' if ok[c] else '下'}")
    elig = [c for c in POOL5 if ok[c]]
    lead = max(elig, key=scores.get)
    v = ann_vol(close, lead, 63)
    print(f"  冠军 {NAMES[lead]}，波动 {v:.1%}，目标仓位 {min(1, 0.12/v):.0%} + 国债 {1-min(1, 0.12/v):.0%}")


if __name__ == "__main__":
    main()
