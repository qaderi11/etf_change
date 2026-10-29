"""加入中证红利（510880）的回测对比。"""
from __future__ import annotations

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backtest import Backtester
from data import load_panel
from run_frontier import vol_target
from run_pool import gated
from validate import run, GOLD_W, VT, COST, NAMES

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "output", "tables")
BOND = "511010"
GOLD = "518880"
DIV = "510880"
V2 = ["159915", "510300", "510500", "513500"]
V5 = V2 + [DIV]
START = "2015-01-01"
A_ALL = {"159915", "510300", "510500", DIV}


def sleeve(base, g=GOLD_W):
    def fn(s, cl):
        w = base(s, cl)
        out = {c: v * (1 - g) for c, v in w.items() if c != BOND}
        out[GOLD] = g
        out[BOND] = out.get(BOND, 0.0) + w.get(BOND, 0.0) * (1 - g)
        return out

    return fn


def main():
    codes = sorted(set(V5 + [GOLD, BOND]))
    close = load_panel("close", codes)
    open_ = load_panel("open", codes)
    bt = Backtester(close, open_, cost=COST, min_history=260)

    cfgs = {
        "v2 四资产": (V2, None),
        "v2+红利（红利看自身均线）": (V5, None),
        "v2+红利（红利看300均线）": (V5, A_ALL),
        "红利替换中证500": (["159915", "510300", DIV, "513500"], None),
    }
    rows, navs = [], {}
    for name, (pool, a_sh) in cfgs.items():
        res = bt.run(sleeve(vol_target(gated(pool, "mixed", a_share=a_sh), VT)), start=START)
        s = res.stats()
        rows.append({"方案": name, "年化": s["年化收益"], "波动": s["年化波动"], "夏普": s["夏普"],
                     "最大回撤": s["最大回撤"], "卡玛": s["卡玛"]})
        navs[name] = res.nav
    print(pd.DataFrame(rows).round(3).to_string(index=False))

    print("\n### 分年度（%）")
    y = pd.DataFrame({k: v.resample("YE").last().pct_change() for k, v in navs.items()})
    y.index = y.index.year
    print((y * 100).round(0).to_string())

    print("\n### 红利年度收益")
    d = close[DIV]
    print({i: f"{v:+.0%}" for i, v in d.resample("YE").last().pct_change().items()})

    print("\n### 五资产归因（红利看自身均线）")
    res = bt.run(sleeve(vol_target(gated(V5, "mixed"), VT)), start=START)
    w = res.weights.reindex(columns=codes).fillna(0).shift(1).dropna()
    r = close.pct_change().reindex(w.index).fillna(0)
    contrib = (w * r).sum()
    tot = contrib.sum()
    for c in codes:
        if abs(contrib[c]) > 1e-6:
            print(f"  {NAMES.get(c,c):<6} 贡献 {contrib[c]:+.1%} 占比 {contrib[c]/tot:+.0%} 平均权重 {w[c].mean():.0%}")

    print("\n### 留一法")
    for c in V5:
        s = bt.run(sleeve(vol_target(gated([x for x in V5 if x != c], "mixed"), VT)),
                   start=START).stats()
        print(f"  去掉 {NAMES.get(c,c)}: 年化 {s['年化收益']:.1%} 夏普 {s['夏普']:.2f} 回撤 {s['最大回撤']:.1%}")

    print("\n### 起点敏感性（五资产，红利自身均线）")
    for yy in range(2015, 2023):
        s = bt.run(sleeve(vol_target(gated(V5, "mixed"), VT)), start=f"{yy}-01-01").stats()
        print(f"  {yy}: 年化 {s['年化收益']:.1%} 夏普 {s['夏普']:.2f} 回撤 {s['最大回撤']:.1%}")

    print("\n### 今日信号（五资产）")
    from strategies import momentum, above_ma, ann_vol
    sc = {c: momentum(close, c, 252, 0) for c in V5}
    ok = {c: (above_ma(close, "510300", 200) if c in {"159915", "510300", "510500"}
              else above_ma(close, c, 200)) for c in V5}
    for c in V5:
        print(f"  {NAMES.get(c,c):<6} 12M {sc[c]:+.1%} 合格 {ok[c]}")


if __name__ == "__main__":
    main()
