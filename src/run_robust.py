"""稳健性：分区间、参数平面、成本敏感性。"""
from __future__ import annotations

import os
import itertools

import numpy as np
import pandas as pd

from backtest import Backtester
from data import load_panel
from strategies import momentum_rotation
from run_frontier import vol_target

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "output")
POOL = ["159915", "513100", "510300"]
BOND = "511010"


def build(close, open_, lookback, ma, vt, cost=0.0005, start="2014-06-01", end=None):
    bt = Backtester(close, open_, cost=cost, min_history=260)
    base = momentum_rotation(POOL, lookback, 1, skip=0, market_gate=ma, defensive=BOND)
    fn = base if vt == 0 else vol_target(base, vt)
    return bt.run(fn, start=start, end=end)


def main():
    close = load_panel("close", POOL + [BOND])
    open_ = load_panel("open", POOL + [BOND])

    # 1) 分区间
    print("### 分区间（12M + MA200 + VT15%）", flush=True)
    rows = []
    for label, s, e in [("2014-06~2019-12", "2014-06-01", "2019-12-31"),
                        ("2020-01~2026-10", "2020-01-01", None)]:
        for vt in [0, 0.15]:
            r = build(close, open_, 252, 200, vt, start=s, end=e)
            st = r.stats()
            rows.append({"区间": label, "VT": f"{vt:.0%}" if vt else "无",
                         "年化": st["年化收益"], "夏普": st["夏普"],
                         "最大回撤": st["最大回撤"], "年数": st["年数"]})
    df = pd.DataFrame(rows)
    print(df.round(3).to_string(index=False), flush=True)

    # 2) 参数平面（VT15）
    print("\n### 参数平面：年化 / 夏普 / 最大回撤（VT15%）", flush=True)
    rows = []
    for lb, ma in itertools.product([126, 189, 252, 315], [120, 150, 200, 250]):
        r = build(close, open_, lb, ma, 0.15)
        st = r.stats()
        rows.append({"形成期": f"{lb//21}M", "均线": ma,
                     "年化": st["年化收益"], "夏普": st["夏普"], "最大回撤": st["最大回撤"]})
    grid = pd.DataFrame(rows)
    grid.to_csv(os.path.join(OUT, "tables", "robust_grid.csv"), index=False, encoding="utf-8-sig")
    print(grid.pivot(index="形成期", columns="均线", values="夏普").round(3).to_string(), flush=True)
    print("\n年化")
    print(grid.pivot(index="形成期", columns="均线", values="年化").round(3).to_string(), flush=True)
    print("\n最大回撤")
    print(grid.pivot(index="形成期", columns="均线", values="最大回撤").round(3).to_string(), flush=True)

    # 3) 成本敏感性
    print("\n### 成本敏感性（12M + MA200 + VT15%）", flush=True)
    rows = []
    for c in [0.0005, 0.0010, 0.0020]:
        r = build(close, open_, 252, 200, 0.15, cost=c)
        st = r.stats()
        rows.append({"单边成本": c, "年化": st["年化收益"], "夏普": st["夏普"],
                     "最大回撤": st["最大回撤"]})
    print(pd.DataFrame(rows).round(4).to_string(index=False), flush=True)

    # 4) 持仓分布
    r = build(close, open_, 252, 200, 0.15)
    w = r.weights.fillna(0)
    print("\n### 平均持仓权重", flush=True)
    print(w.mean().round(3).to_string(), flush=True)
    print(f"平均股票仓位 {(1 - w.get(BOND, pd.Series(0, index=w.index))).mean():.1%}")


if __name__ == "__main__":
    main()
