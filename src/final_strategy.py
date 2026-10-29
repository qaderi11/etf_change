"""最终策略（v2）：四资产轮动 + 黄金底仓。

池子：沪深300、中证500、创业板、标普500
规则：
  1. 每月末按 252 日涨幅排序，只在"合格"资产中选第一名；
  2. 合格 = 该资产站上自身 200 日均线；A股资产（300/500/创业板）改用沪深300 的 200 日线；
  3. 冠军仓位 = min(1, 12% / 63日年化波动) × 80%，黄金固定 20%，其余国债；
  4. 次日开盘调仓。

用法：
    python src/final_strategy.py --signal
    python src/final_strategy.py --signal --hold 511010:0.26,518880:0.20,513500:0.54
    python src/final_strategy.py --check
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data import load_panel  # noqa: E402

# ------------------------------ 参数 ------------------------------ #
POOL = ["159915", "510300", "510500", "513500"]
A_SHARE = {"159915", "510300", "510500"}
BOND = "511010"
GOLD = "518880"
LOOKBACK = 252
GATE_MA = 200
VOL_WINDOW = 63
VOL_TARGET = 0.12
GOLD_SLEEVE = 0.20
MIN_TREND = 0.03      # 冠军 12M 涨幅低于该值时不参与
BAND = 0.0            # 周频，无交易带
NAMES = {"159915": "创业板", "513100": "纳指100", "510300": "沪深300",
         "510500": "中证500", "513500": "标普500", "518880": "黄金", "511010": "国债"}


def compute_signal(close: pd.DataFrame, asof: pd.Timestamp | None = None) -> dict:
    px = close.loc[:asof] if asof is not None else close

    s300 = px["510300"].dropna()
    if len(s300) < GATE_MA:
        raise ValueError("沪深300 历史不足 200 日")
    a_share_on = bool(s300.iloc[-1] > s300.iloc[-GATE_MA:].mean())

    stats = {}
    for c in POOL:
        s = px[c].dropna()
        if len(s) < LOOKBACK + 1:
            raise ValueError(f"{c} 历史不足 {LOOKBACK + 1} 日")
        latest = s.iloc[-1]
        stats[c] = {
            "name": NAMES[c],
            "close": latest,
            "ret12": latest / s.iloc[-LOOKBACK - 1] - 1,
            "vol63": s.iloc[-(VOL_WINDOW + 1):].pct_change().std() * np.sqrt(252),
            "ma200": s.iloc[-GATE_MA:].mean(),
            "eligible": a_share_on if c in A_SHARE else bool(latest > s.iloc[-GATE_MA:].mean()),
        }

    eligible = [c for c in POOL if stats[c]["eligible"]]
    if not eligible:
        weights = {GOLD: GOLD_SLEEVE, BOND: 1 - GOLD_SLEEVE}
        return {"asof": px.index[-1], "stats": stats, "a_share_on": a_share_on,
                "leader": None, "equity": 0.0, "weights": weights,
                "reason": "全部资产均在 200 日均线下方，只保留黄金与国债"}

    leader = max(eligible, key=lambda c: stats[c]["ret12"])
    if stats[leader]["ret12"] < MIN_TREND:
        weights = {GOLD: GOLD_SLEEVE, BOND: 1 - GOLD_SLEEVE}
        return {
            "asof": px.index[-1], "stats": stats, "a_share_on": a_share_on,
            "leader": None, "equity": 0.0, "weights": weights,
            "reason": f"冠军 {NAMES[leader]} 12M 仅 {stats[leader]['ret12']:+.1%}，"
                      f"低于趋势阈值 {MIN_TREND:.0%}，只保留黄金与国债",
        }

    vol = stats[leader]["vol63"]
    equity = min(1.0, VOL_TARGET / vol) if vol > 0 else 1.0
    equity *= (1 - GOLD_SLEEVE)
    weights = {leader: equity, GOLD: GOLD_SLEEVE, BOND: 1 - equity - GOLD_SLEEVE}
    return {
        "asof": px.index[-1], "stats": stats, "a_share_on": a_share_on,
        "leader": leader, "equity": equity, "weights": weights,
        "reason": f"{NAMES[leader]} 动量最强，波动 {vol:.1%} → 股票仓位 {equity:.0%}",
    }


def print_signal(sig: dict, hold: dict | None = None) -> None:
    print(f"\n信号日：{pd.Timestamp(sig['asof']).date()}")
    print("-" * 78)
    print(f"{'资产':<8}{'收盘':>9}{'12M':>9}{'63日波动':>10}{'距200日线':>11}{'合格':>6}")
    for c in POOL:
        s = sig["stats"][c]
        print(f"{s['name']:<8}{s['close']:>9.3f}{s['ret12']:>8.1%}{s['vol63']:>10.1%}"
              f"{s['close']/s['ma200']-1:>11.1%}{'是' if s['eligible'] else '否':>6}")
    print("-" * 78)
    print(f"沪深300 > 200日线：{'是' if sig['a_share_on'] else '否'}"
          f"　趋势阈值：{MIN_TREND:.0%}")
    print(f"结论：{sig['reason']}")
    print("\n目标仓位：")
    for c, w in sig["weights"].items():
        if w > 0.001:
            print(f"  {NAMES[c]:<8} {w:>6.1%}")

    if hold:
        print(f"\n调仓指令（无交易带 {BAND:.0%}）：")
        skipped = []
        for c in sorted(set(hold) | set(sig["weights"])):
            delta = sig["weights"].get(c, 0) - hold.get(c, 0)
            if abs(delta) > BAND:
                print(f"  {'买入' if delta > 0 else '卖出'} {NAMES.get(c, c):<8} {abs(delta):>6.1%}")
            elif abs(delta) > 0.005:
                skipped.append(f"{NAMES.get(c, c)} {abs(delta):.1%}")
        if skipped:
            print(f"  忽略（带内）：{'、'.join(skipped)}")


def parse_hold(s: str) -> dict:
    out = {}
    for part in s.split(","):
        if ":" in part:
            k, v = part.split(":")
            out[k.strip()] = float(v)
    return out


def check() -> None:
    from backtest import Backtester
    from run_frontier import vol_target
    from run_pool import gated

    def sleeve(base, g=GOLD_SLEEVE):
        def fn(s, cl):
            w = base(s, cl)
            out = {c: v * (1 - g) for c, v in w.items() if c != BOND}
            out[GOLD] = g
            out[BOND] = out.get(BOND, 0.0) + w.get(BOND, 0.0) * (1 - g)
            return out

        return fn

    codes = POOL + [GOLD, BOND]
    close = load_panel("close", codes)
    open_ = load_panel("open", codes)
    bt = Backtester(close, open_, cost=0.0005, min_history=260)
    res = bt.run(sleeve(vol_target(gated(POOL, "mixed"), VOL_TARGET)), start="2015-01-01", band=BAND)
    s = res.stats()
    print(f"2015-01 ~ {res.nav.index[-1].date()}  年化 {s['年化收益']:.1%}  "
          f"波动 {s['年化波动']:.1%}  夏普 {s['夏普']:.2f}  最大回撤 {s['最大回撤']:.1%}  "
          f"（无交易带 {BAND:.0%}）")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--signal", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--hold", default=None)
    ap.add_argument("--asof", default=None)
    args = ap.parse_args()

    if args.check:
        check()
        return
    if args.signal:
        close = load_panel("close", POOL + [GOLD, BOND])
        sig = compute_signal(close, pd.Timestamp(args.asof) if args.asof else None)
        print_signal(sig, parse_hold(args.hold) if args.hold else None)
        return
    ap.print_help()


if __name__ == "__main__":
    main()
