"""v3 验证：创业板 + 标普500（+20% 黄金），与 v2 四资产逐项对比。"""
from __future__ import annotations

import itertools
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backtest import Backtester
from data import load_panel
from validate import bootstrap, nw_t, run, sleeve, GOLD_W, VT, COST, NAMES

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "output", "tables")

BOND = "511010"
GOLD = "518880"
POOL2 = ["159915", "513500"]
POOL4 = ["159915", "510300", "510500", "513500"]
START = "2015-01-01"


def main():
    codes = sorted(set(POOL4 + [GOLD, BOND]))
    close = load_panel("close", codes)
    open_ = load_panel("open", codes)

    v2 = run(close, open_, pool=POOL4)
    v3 = run(close, open_, pool=POOL2)

    print("### 基线对比")
    rows = []
    for name, res in [("v2 四资产", v2), ("v3 两资产", v3)]:
        s = res.stats()
        rows.append({"版本": name, "年化": s["年化收益"], "波动": s["年化波动"], "夏普": s["夏普"],
                     "最大回撤": s["最大回撤"], "卡玛": s["卡玛"]})
    print(pd.DataFrame(rows).round(3).to_string(index=False))

    r2 = v2.nav.resample("ME").last().pct_change()
    r3 = v3.nav.resample("ME").last().pct_change()
    print(f"  v2/v3 月收益相关性：{r2.corr(r3):.2f}")

    print("\n### 分年度（%）")
    y2 = v2.nav.resample("YE").last(); y3 = v3.nav.resample("YE").last()
    t = pd.DataFrame({"v2": y2.pct_change(), "v3": y3.pct_change()})
    t.index = t.index.year
    print((t * 100).round(0).to_string())

    # A 起点
    print("\n### A 起点敏感性")
    rows = []
    for y in range(2015, 2023):
        a = run(close, open_, pool=POOL2, start=f"{y}-01-01").stats()
        b = run(close, open_, pool=POOL4, start=f"{y}-01-01").stats()
        rows.append({"起点": y, "v3年化": a["年化收益"], "v3夏普": a["夏普"], "v3回撤": a["最大回撤"],
                     "v2年化": b["年化收益"], "v2夏普": b["夏普"]})
    a_df = pd.DataFrame(rows)
    a_df.to_csv(os.path.join(OUT, "val_v3_start.csv"), index=False, encoding="utf-8-sig")
    print(a_df.round(3).to_string(index=False))

    # B 参数
    print("\n### B 参数扰动（v3）")
    rows = []
    for lb, ma, vw, g in itertools.product([252, 315], [150, 200, 250], [40, 63, 90], [0.1, 0.2, 0.3]):
        s = run(close, open_, pool=POOL2, lookback=lb, ma=ma, vw=vw, gold=g).stats()
        rows.append({"形成期": lb // 21, "均线": ma, "波动窗口": vw, "黄金": g,
                     "年化": s["年化收益"], "夏普": s["夏普"], "最大回撤": s["最大回撤"]})
    b_df = pd.DataFrame(rows)
    b_df.to_csv(os.path.join(OUT, "val_v3_param.csv"), index=False, encoding="utf-8-sig")
    print(b_df[["年化", "夏普", "最大回撤"]].describe().round(3).to_string())
    print(f"  夏普<0.8 占比 {(b_df['夏普'] < 0.8).mean():.0%}；负收益组合 {(b_df['年化'] < 0).sum()}")

    # C 成本 / D 滞后
    print("\n### C 成本 / D 执行")
    for c in [0.0005, 0.001, 0.002, 0.003]:
        s = run(close, open_, pool=POOL2, cost=c).stats()
        print(f"  成本 {c:.2%}: 年化 {s['年化收益']:.1%} 夏普 {s['夏普']:.2f}")
    for lag in [1, 2]:
        s = run(close, open_, pool=POOL2, exec_lag=lag).stats()
        print(f"  T+{lag}: 年化 {s['年化收益']:.1%} 夏普 {s['夏普']:.2f}")

    # E 留一
    print("\n### E 留一法")
    for c in POOL2:
        s = run(close, open_, pool=[x for x in POOL2 if x != c]).stats()
        print(f"  去掉 {NAMES[c]}: 年化 {s['年化收益']:.1%} 夏普 {s['夏普']:.2f} 回撤 {s['最大回撤']:.1%}")

    # F Bootstrap
    print("\n### F Bootstrap（v3）")
    bs = bootstrap(r3.dropna())
    print(bs.quantile([0.05, 0.5, 0.95]).round(3).to_string())

    # G 显著性
    print("\n### G 显著性（v3）")
    ew = close[POOL2].resample("ME").last().pct_change().mean(axis=1)
    hs = close["510300"].resample("ME").last().pct_change()
    for name, bench in [("两资产等权", ew), ("沪深300", hs)]:
        ex = (r3 - bench).dropna()
        print(f"  vs {name}: 超额 {ex.mean():+.2%}/月, t={nw_t(ex):.2f}, 胜率 {(ex>0).mean():.0%}")

    # 今日
    from strategies import momentum, above_ma, ann_vol
    d = close.index[-1]
    sc = {c: momentum(close, c, 252, 0) for c in POOL2}
    ok = {"159915": above_ma(close, "510300", 200), "513500": above_ma(close, "513500", 200)}
    print("\n### 今日信号（v3）")
    for c in POOL2:
        print(f"  {NAMES[c]}: 12M {sc[c]:+.1%}, 合格 {ok[c]}")
    elig = [c for c in POOL2 if ok[c]]
    if elig:
        lead = max(elig, key=sc.get)
        w = min(1, 0.12 / ann_vol(close, lead, 63)) * 0.8
        print(f"  → {NAMES[lead]} {w:.0%} + 黄金 20% + 国债 {0.8-w:.0%}")
    else:
        print("  → 国债 80% + 黄金 20%")


if __name__ == "__main__":
    main()
