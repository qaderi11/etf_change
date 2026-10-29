"""最终池子：沪深300、中证500、创业板、标普500（+ 黄金底仓）。"""
from __future__ import annotations

import os
import sys

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
START = "2015-01-01"
POOL4 = ["159915", "510300", "510500", "513500"]
POOL3 = ["159915", "513100", "510300"]
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
    codes = sorted(set(POOL4 + POOL3 + [GOLD, BOND]))
    close = load_panel("close", codes)
    open_ = load_panel("open", codes)
    bt = Backtester(close, open_, cost=0.0005, min_history=260)

    cfgs = {
        "新池4 VT12+黄金20%": (POOL4, 0.12),
        "新池4 VT12（无黄金）": (POOL4, 0.12),
        "新池4 VT15+黄金20%": (POOL4, 0.15),
        "旧池3 VT12+黄金20%（对照）": (POOL3, 0.12),
    }
    rows, navs = [], {}
    for name, (pool, tgt) in cfgs.items():
        g = 0.0 if "无黄金" in name else 0.2
        res = bt.run(sleeve(vol_target(gated(pool, "mixed"), tgt), g), start=START)
        s = res.stats()
        rows.append({"方案": name, "年化": s["年化收益"], "波动": s["年化波动"], "夏普": s["夏普"],
                     "最大回撤": s["最大回撤"], "卡玛": s["卡玛"]})
        navs[name] = res.nav
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(OUT, "final_pool4.csv"), index=False, encoding="utf-8-sig")
    print(df.round(3).to_string(index=False))

    print("\n### 分年度（%）")
    y = pd.DataFrame({k: yearly_returns(v) for k, v in navs.items()})
    y.index = y.index.year
    print((y * 100).round(0).to_string())

    print("\n### 分区间")
    for label, s, e in [("2015-2020", "2015-01-01", "2020-12-31"),
                        ("2021-2026", "2021-01-01", None)]:
        for name, (pool, tgt) in cfgs.items():
            g = 0.0 if "无黄金" in name else 0.2
            st = bt.run(sleeve(vol_target(gated(pool, "mixed"), tgt), g), start=s, end=e).stats()
            print(f"  {label} {name}: 年化{st['年化收益']:.1%} 夏普{st['夏普']:.2f} 回撤{st['最大回撤']:.1%}")

    print("\n### 形成期敏感性（新池4 VT12+黄金20%）")
    for lb in [126, 189, 252, 315]:
        st = bt.run(sleeve(vol_target(gated(POOL4, "mixed", lb), 0.12)), start=START).stats()
        print(f"  {lb//21}M: 年化{st['年化收益']:.1%} 夏普{st['夏普']:.2f} 回撤{st['最大回撤']:.1%}")

    print("\n### 归因")
    res = bt.run(sleeve(vol_target(gated(POOL4, "mixed"), 0.12)), start=START)
    w = res.weights.reindex(columns=codes).fillna(0).shift(1).dropna()
    r = close.pct_change().reindex(w.index).fillna(0)
    contrib = (w * r).sum()
    tot = contrib.sum()
    for c in codes:
        if abs(contrib[c]) > 1e-6:
            print(f"  {NAMES[c]:<6} 贡献 {contrib[c]:+.1%} 占比 {contrib[c]/tot:+.0%} 平均权重 {w[c].mean():.0%}")

    print("\n### 今日信号")
    from strategies import momentum, above_ma, ann_vol
    d = close.index[-1]
    sc = {c: momentum(close, c, 252, 0) for c in POOL4}
    ok = {c: (above_ma(close, "510300", 200) if c != "513500" else above_ma(close, c, 200))
          for c in POOL4}
    for c in POOL4:
        print(f"  {NAMES[c]:<6} 12M {sc[c]:+.1%}  均线{'上' if ok[c] else '下'}")
    elig = [c for c in POOL4 if ok[c]]
    if elig:
        lead = max(elig, key=sc.get)
        v = ann_vol(close, lead, 63)
        wgt = min(1, 0.12 / v) * 0.8
        print(f"  → {NAMES[lead]} {wgt:.0%} + 黄金 20% + 国债 {0.8-wgt:.0%}")
    else:
        print("  → 闸门全关：国债 80% + 黄金 20%")


if __name__ == "__main__":
    main()
