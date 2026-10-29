"""生成 PWA 所需的数据文件：latest / nav / history / meta。

周频 v2：四资产轮动 + 20% 黄金底仓，无交易带。
输出到 app/public/data/。
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from backtest import Backtester  # noqa: E402
from data import load_panel  # noqa: E402
from final_strategy import (  # noqa: E402
    POOL, GOLD, BOND, NAMES, GOLD_SLEEVE, VOL_TARGET, LOOKBACK, GATE_MA, VOL_WINDOW,
    MIN_TREND, compute_signal,
)
from backtest import month_end_trading_days  # noqa: E402
from run_frontier import vol_target  # noqa: E402
from run_pool import gated  # noqa: E402
from validate import sleeve, nw_t  # noqa: E402

OUT = ROOT / "app" / "public" / "data"
OUT.mkdir(parents=True, exist_ok=True)
TZ = timezone(timedelta(hours=8))


def weekly_dates(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    iso = index.isocalendar()
    s = pd.Series(index, index=index)
    return pd.DatetimeIndex(sorted(s.groupby([iso.year.values, iso.week.values]).max().values))


def main() -> None:
    codes = sorted(set(POOL + [GOLD, BOND]))
    close = load_panel("close", codes)
    open_ = load_panel("open", codes)

    fn = sleeve(vol_target(gated(POOL, "mixed", min_trend=MIN_TREND), VOL_TARGET))
    weekly = weekly_dates(close.index)
    month_ends = month_end_trading_days(close.index)
    quarterly = month_ends[month_ends.month.isin([3, 6, 9, 12])]
    semiannual = month_ends[month_ends.month.isin([6, 12])]

    def run(dates, start="2015-01-01"):
        return Backtester(close, open_, cost=0.0005, min_history=260).run(
            fn, start=start, signal_dates=dates, band=0.0)

    res = run(weekly)
    stats = res.stats()

    nav = res.nav
    nav_w = nav.resample("W-FRI").last().dropna()
    nav_w = nav_w / nav_w.iloc[0]

    # ---------- nav.json ----------
    nav_points = [{"date": d.strftime("%Y-%m-%d"), "nav": round(float(v), 4)}
                  for d, v in nav_w.items()]
    (OUT / "nav.json").write_text(json.dumps(nav_points, ensure_ascii=False), encoding="utf-8")

    # ---------- latest.json ----------
    sig = compute_signal(close)
    asof = pd.Timestamp(sig["asof"])
    assets = []
    for c in POOL:
        s = sig["stats"][c]
        assets.append({
            "code": c,
            "name": s["name"],
            "close": round(float(s["close"]), 4),
            "ret12": round(float(s["ret12"]), 4),
            "vol63": round(float(s["vol63"]), 4),
            "ma200": round(float(s["ma200"]), 4),
            "dist_ma": round(float(s["close"] / s["ma200"] - 1), 4),
            "eligible": bool(s["eligible"]),
        })
    latest = {
        "asof": asof.strftime("%Y-%m-%d"),
        "generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "gate": {
            "open": bool(sig["a_share_on"]),
            "index": "沪深300",
            "close": round(float(close["510300"].dropna().iloc[-1]), 4),
            "ma200": round(float(close["510300"].dropna().iloc[-GATE_MA:].mean()), 4),
        },
        "assets": assets,
        "leader": sig["leader"],
        "leader_name": NAMES.get(sig["leader"], "-") if sig["leader"] else None,
        "equity": round(float(sig["equity"]), 4),
        "weights": {k: round(float(v), 4) for k, v in sig["weights"].items()},
        "reason": sig["reason"],
    }
    (OUT / "latest.json").write_text(json.dumps(latest, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---------- history.json ----------
    w = res.weights.fillna(0.0)
    w = w.resample("W-FRI").last().dropna(how="all")
    s300 = close["510300"].dropna()

    def gate_on(d: pd.Timestamp) -> bool:
        sub = s300.loc[:d]
        return bool(len(sub) >= GATE_MA and sub.iloc[-1] > sub.iloc[-GATE_MA:].mean())

    hist = []
    for d, row in w.tail(60).iterrows():
        eq = {c: float(row.get(c, 0.0)) for c in POOL if row.get(c, 0.0) > 1e-6}
        lead = max(eq, key=eq.get) if eq else None
        hist.append({
            "date": d.strftime("%Y-%m-%d"),
            "leader": lead,
            "leader_name": NAMES.get(lead, "国债") if lead else "国债",
            "weights": {c: round(float(row.get(c, 0.0)), 3) for c in codes if row.get(c, 0.0) > 1e-6},
            "gate": gate_on(d),
        })
    (OUT / "history.json").write_text(json.dumps(hist, ensure_ascii=False), encoding="utf-8")

    # ---------- meta.json ----------
    yearly = nav.resample("YE").last().pct_change().dropna()
    yearly_rows = [{"year": int(i.year), "ret": round(float(v), 4)} for i, v in yearly.items()]

    r = nav.resample("ME").last().pct_change().dropna()
    ew = close[POOL].resample("ME").last().pct_change().mean(axis=1)
    ex = (r - ew).dropna()

    start_rows = []
    for y in range(2015, 2023):
        st = run(weekly, start=f"{y}-01-01").stats()
        start_rows.append({"start": y, "cagr": round(float(st["年化收益"]), 4),
                           "sharpe": round(float(st["夏普"]), 2),
                           "mdd": round(float(st["最大回撤"]), 4)})

    freq_rows = []
    for name, dates in [("周", weekly), ("月", None), ("季", quarterly), ("半年", semiannual)]:
        rr = run(dates)
        st = rr.stats()
        freq_rows.append({"freq": name, "cagr": round(float(st["年化收益"]), 4),
                          "sharpe": round(float(st["夏普"]), 2),
                          "mdd": round(float(st["最大回撤"]), 4),
                          "cost": round(float(rr.cost_paid), 4)})
    meta = {
        "version": "v2.2-trend3-weekly",
        "freq": "weekly",
        "band": 0,
        "params": {
            "pool": POOL,
            "lookback": LOOKBACK,
            "gate_ma": GATE_MA,
            "vol_window": VOL_WINDOW,
            "vol_target": VOL_TARGET,
            "gold_sleeve": GOLD_SLEEVE,
            "min_trend": MIN_TREND,
            "cost": 0.0005,
        },
        "expected": {
            "cagr": round(float(stats["年化收益"]), 4),
            "vol": round(float(stats["年化波动"]), 4),
            "sharpe": round(float(stats["夏普"]), 3),
            "mdd": round(float(stats["最大回撤"]), 4),
            "calmar": round(float(stats["卡玛"]), 3),
            "start": nav.index[0].strftime("%Y-%m-%d"),
            "end": nav.index[-1].strftime("%Y-%m-%d"),
        },
        "yearly": yearly_rows,
        "validation": {
            "start_sensitivity": start_rows,
            "frequency": freq_rows,
            "t_stat_vs_ew": round(float(nw_t(ex)), 2),
            "excess_vs_ew": round(float(ex.mean()), 4),
            "note": "起点敏感性与频率对比按当前口径（含 3% 趋势阈值）重算；参数网格基于旧口径。",
        },
        "generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
    }
    (OUT / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"asof {latest['asof']}  leader {latest['leader_name']}  weights {latest['weights']}")
    print(f"nav points {len(nav_points)}  history {len(hist)}  cagr {meta['expected']['cagr']:.1%} "
          f"mdd {meta['expected']['mdd']:.1%}  t={meta['validation']['t_stat_vs_ew']}")
    print(f"written to {OUT}")


if __name__ == "__main__":
    main()
