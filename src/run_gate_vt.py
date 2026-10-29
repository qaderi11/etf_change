"""在波动率目标之下，比较各闸门是否仍有增量价值。"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from backtest import Backtester
from data import load_panel
from strategies import momentum_rotation
from run_frontier import vol_target, ann_vol  # 复用

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "output")
POOL = ["159915", "513100", "510300"]
BOND = "511010"
START = "2014-06-01"


def main():
    close = load_panel("close", POOL + [BOND])
    open_ = load_panel("open", POOL + [BOND])
    bt = Backtester(close, open_, cost=0.0005, min_history=260)

    variants = {
        "B_绝对动量": momentum_rotation(POOL, 252, 1, skip=0, abs_vs=BOND, defensive=BOND),
        "C_300均线": momentum_rotation(POOL, 252, 1, skip=0, market_gate=200, defensive=BOND),
        "D_双闸门": momentum_rotation(POOL, 252, 1, skip=0, abs_vs=BOND, market_gate=200, defensive=BOND),
        "E_自身均线": momentum_rotation(POOL, 252, 1, skip=0, ma_filter=200, defensive=BOND),
    }
    rows = []
    for name, base in variants.items():
        for tgt in [0.0, 0.12, 0.15, 0.18]:
            fn = base if tgt == 0 else vol_target(base, tgt)
            res = bt.run(fn, start=START)
            s = res.stats()
            rows.append({
                "策略": name, "波动目标": f"{tgt:.0%}" if tgt else "无",
                "年化": s["年化收益"], "波动": s["年化波动"], "夏普": s["夏普"],
                "最大回撤": s["最大回撤"], "卡玛": s["卡玛"],
            })
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(OUT, "tables", "gate_vs_voltarget.csv"), index=False, encoding="utf-8-sig")
    print(df.round(4).to_string(index=False), flush=True)


if __name__ == "__main__":
    main()
