"""加入中证1000（512100）的回测对比。受其上市时间限制，统一从 2018-01 起。"""
from __future__ import annotations

import itertools
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from validate import run, bootstrap, nw_t, GOLD_W, VT, COST, NAMES

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "output", "tables")

BOND = "511010"
GOLD = "518880"
V2 = ["159915", "510300", "510500", "513500"]
V5 = ["159915", "510300", "510500", "512100", "513500"]
V4B = ["159915", "510300", "512100", "513500"]   # 用 1000 替换 500
START = "2018-01-01"


def main():
    codes = sorted(set(V5 + [GOLD, BOND]))
    close = load_panel_codes = None
    from data import load_panel
    close = load_panel("close", codes)
    open_ = load_panel("open", codes)

    print("### 基线（2018-01 ~ 2026-10，同一区间）")
    rows = []
    for name, pool in [("v2 四资产（300/500/创业/标普）", V2),
                       ("五资产（+中证1000）", V5),
                       ("四资产（1000 替换 500）", V4B)]:
        res = run(close, open_, pool=pool, start=START)
        s = res.stats()
        rows.append({"方案": name, "年化": s["年化收益"], "波动": s["年化波动"], "夏普": s["夏普"],
                     "最大回撤": s["最大回撤"], "卡玛": s["卡玛"]})
    print(pd.DataFrame(rows).round(3).to_string(index=False))

    print("\n### 分年度（%）")
    yy = {}
    for name, pool in [("v2", V2), ("+1000", V5), ("1000替500", V4B)]:
        nav = run(close, open_, pool=pool, start=START).nav
        yy[name] = nav.resample("YE").last().pct_change()
    t = pd.DataFrame(yy)
    t.index = t.index.year
    print((t * 100).round(0).to_string())

    print("\n### 五资产归因")
    res5 = run(close, open_, pool=V5, start=START)
    w = res5.weights.reindex(columns=codes).fillna(0).shift(1).dropna()
    r = close.pct_change().reindex(w.index).fillna(0)
    contrib = (w * r).sum()
    tot = contrib.sum()
    for c in codes:
        if abs(contrib[c]) > 1e-6:
            print(f"  {NAMES.get(c,c):<6} 贡献 {contrib[c]:+.1%} 占比 {contrib[c]/tot:+.0%} 平均权重 {w[c].mean():.0%}")

    print("\n### 五资产留一法")
    for c in V5:
        s = run(close, open_, pool=[x for x in V5 if x != c], start=START).stats()
        print(f"  去掉 {NAMES[c]}: 年化 {s['年化收益']:.1%} 夏普 {s['夏普']:.2f} 回撤 {s['最大回撤']:.1%}")

    print("\n### 五资产起点敏感性")
    for y in range(2018, 2023):
        s = run(close, open_, pool=V5, start=f"{y}-01-01").stats()
        print(f"  {y}: 年化 {s['年化收益']:.1%} 夏普 {s['夏普']:.2f} 回撤 {s['最大回撤']:.1%}")

    print("\n### 五资产参数扰动")
    rows = []
    for lb, ma, vw, g in itertools.product([252, 315], [150, 200, 250], [40, 63, 90], [0.1, 0.2, 0.3]):
        s = run(close, open_, pool=V5, lookback=lb, ma=ma, vw=vw, gold=g, start=START).stats()
        rows.append({"年化": s["年化收益"], "夏普": s["夏普"], "最大回撤": s["最大回撤"]})
    b = pd.DataFrame(rows)
    b.to_csv(os.path.join(OUT, "val_add1000_param.csv"), index=False, encoding="utf-8-sig")
    print(b.describe().round(3).to_string())

    print("\n### 今日信号（五资产）")
    from strategies import momentum, above_ma, ann_vol
    A = {"159915", "510300", "510500", "512100"}
    sc = {c: momentum(close, c, 252, 0) for c in V5}
    ok = {c: (above_ma(close, "510300", 200) if c in A else above_ma(close, c, 200)) for c in V5}
    for c in V5:
        print(f"  {NAMES[c]:<6} 12M {sc[c]:+.1%} 合格 {ok[c]}")
    elig = [c for c in V5 if ok[c]]
    if elig:
        lead = max(elig, key=sc.get)
        w = min(1, 0.12 / ann_vol(close, lead, 63)) * 0.8
        print(f"  → {NAMES[lead]} {w:.0%} + 黄金 20% + 国债 {0.8-w:.0%}")


if __name__ == "__main__":
    main()
