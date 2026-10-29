"""P0 扩池检验：轮动候选扩池 vs 黄金固定底仓。"""
from __future__ import annotations

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backtest import Backtester
from data import load_panel
from run_frontier import vol_target
from run_pool import gated

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "output", "tables")
BOND = "511010"
BASE = ["159915", "513100", "510300"]
GOLD = "518880"
POOL500 = "510500"
START = "2014-08-01"


def main():
    codes = sorted(set(BASE + [GOLD, POOL500, BOND]))
    close = load_panel("close", codes)
    open_ = load_panel("open", codes)
    bt = Backtester(close, open_, cost=0.0005, min_history=260)

    pools = {
        "3资产": BASE,
        "3+黄金": BASE + [GOLD],
        "3+中证500": BASE + [POOL500],
        "3+500+黄金": BASE + [POOL500, GOLD],
    }
    rows = []
    for name, pool in pools.items():
        for s, e, lab in [(START, None, "全期"), (START, "2019-12-31", "2014-19"),
                          ("2020-01-01", None, "2020-26")]:
            st = bt.run(vol_target(gated(pool, "mixed"), 0.12), start=s, end=e).stats()
            rows.append({"池子": name, "区间": lab, "年化": st["年化收益"],
                         "夏普": st["夏普"], "最大回撤": st["最大回撤"]})
    pool_df = pd.DataFrame(rows)
    pool_df.to_csv(os.path.join(OUT, "p0_pool_expand.csv"), index=False, encoding="utf-8-sig")
    print(pool_df.pivot(index="池子", columns="区间", values=["年化", "夏普", "最大回撤"]).round(3).to_string())

    base = vol_target(gated(BASE, "mixed"), 0.12)

    def sleeve(g: float):
        def fn(s, cl):
            w = base(s, cl)
            out = {c: v * (1 - g) for c, v in w.items() if c != BOND}
            out[GOLD] = g
            out[BOND] = out.get(BOND, 0.0) + w.get(BOND, 0.0) * (1 - g)
            return out

        return fn

    rows = []
    for g in [0.0, 0.1, 0.2, 0.3]:
        for s, e, lab in [("2014-06-01", None, "全期"), ("2014-06-01", "2019-12-31", "2014-19"),
                          ("2020-01-01", None, "2020-26")]:
            st = bt.run(sleeve(g), start=s, end=e).stats()
            rows.append({"黄金底仓": f"{g:.0%}", "区间": lab, "年化": st["年化收益"],
                         "波动": st["年化波动"], "夏普": st["夏普"], "最大回撤": st["最大回撤"]})
    sleeve_df = pd.DataFrame(rows)
    sleeve_df.to_csv(os.path.join(OUT, "p0_gold_sleeve.csv"), index=False, encoding="utf-8-sig")
    print("\n")
    print(sleeve_df.pivot(index="黄金底仓", columns="区间",
                          values=["年化", "夏普", "最大回撤"]).round(3).to_string())

    # 今日信号（20% 黄金底仓）
    from strategies import momentum, above_ma, ann_vol
    d = close.index[-1]
    scores = {c: momentum(close, c, 252, 0) for c in BASE}
    ok = {c: (above_ma(close, "510300", 200) if c != "513100" else above_ma(close, c, 200))
          for c in BASE}
    elig = [c for c in BASE if ok[c]]
    print("\n今日（20% 黄金底仓 + 混合闸门 + VT12）：")
    if not elig:
        print("  闸门全关：国债 80% + 黄金 20%")
    else:
        lead = max(elig, key=scores.get)
        v = ann_vol(close, lead, 63)
        w = min(1.0, 0.12 / v)
        print(f"  冠军 {lead}，波动 {v:.1%}，仓位 {w*0.8:.0%} + 黄金 20% + 国债 {(1-w)*0.8:.0%}")


if __name__ == "__main__":
    main()
