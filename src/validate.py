"""v2 策略验证套件。

不调参，只检验稳健性：
  A 起点敏感性    B 参数扰动      C 成本压力
  D 执行滞后      E 留一法        F Bootstrap 置信区间
  G 显著性检验    H 实现一致性
"""
from __future__ import annotations

import os
import sys
import itertools

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backtest import Backtester
from data import load_panel
from run_frontier import vol_target
from run_pool import gated

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "output", "tables")
os.makedirs(OUT, exist_ok=True)

BOND = "511010"
GOLD = "518880"
POOL = ["159915", "510300", "510500", "513500"]
START = "2015-01-01"
COST = 0.0005
VT = 0.12
GOLD_W = 0.20
NAMES = {"159915": "创业板", "510300": "沪深300", "510500": "中证500", "512100": "中证1000",
         "513500": "标普500", "518880": "黄金", "511010": "国债"}


def sleeve(base, g=GOLD_W):
    def fn(s, cl):
        w = base(s, cl)
        out = {c: v * (1 - g) for c, v in w.items() if c != BOND}
        out[GOLD] = g
        out[BOND] = out.get(BOND, 0.0) + w.get(BOND, 0.0) * (1 - g)
        return out

    return fn


def make(pool=POOL, lookback=252, ma=200, vt=VT, gold=GOLD_W, cost=COST):
    return lambda close, open_: Backtester(close, open_, cost=cost, min_history=260)


def run(close, open_, pool=POOL, lookback=252, ma=200, vt=VT, gold=GOLD_W,
        cost=COST, start=START, end=None, exec_lag=1, vw=63):
    bt = Backtester(close, open_, cost=cost, min_history=260)
    fn = sleeve(vol_target(gated(pool, "mixed", lookback, ma), vt, vw), gold)
    return bt.run(fn, start=start, end=end, exec_lag=exec_lag)


def nw_t(x: pd.Series, lags: int = 6) -> float:
    x = np.asarray(pd.Series(x).dropna(), dtype=float)
    n = len(x)
    if n < 10:
        return np.nan
    m = x.mean()
    e = x - m
    s = e @ e / n
    for l in range(1, lags + 1):
        w = 1 - l / (lags + 1)
        s += 2 * w * (e[l:] @ e[:-l]) / n
    return m / np.sqrt(s / n)


def bootstrap(r: pd.Series, n_sim: int = 2000, block: int = 6, seed: int = 7):
    rng = np.random.default_rng(seed)
    x = np.asarray(r.dropna(), dtype=float)
    n = len(x)
    out = []
    for _ in range(n_sim):
        idx = []
        while len(idx) < n:
            s = rng.integers(0, n - block + 1)
            idx.extend(range(s, s + block))
        rr = x[np.array(idx[:n])]
        nav = np.cumprod(1 + rr)
        years = n / 12
        cagr = nav[-1] ** (1 / years) - 1
        vol = rr.std() * np.sqrt(12)
        sharpe = rr.mean() / rr.std() * np.sqrt(12) if rr.std() > 0 else np.nan
        mdd = (nav / np.maximum.accumulate(nav) - 1).min()
        out.append((cagr, sharpe, mdd))
    return pd.DataFrame(out, columns=["年化", "夏普", "最大回撤"])


def main():
    codes = sorted(set(POOL + [GOLD, BOND]))
    close = load_panel("close", codes)
    open_ = load_panel("open", codes)

    base = run(close, open_)
    nav = base.nav

    # ---------------- A 起点敏感性 ----------------
    print("### A 起点敏感性")
    rows = []
    for y in range(2015, 2023):
        res = run(close, open_, start=f"{y}-01-01")
        s = res.stats()
        rows.append({"起点": y, "年化": s["年化收益"], "夏普": s["夏普"],
                     "最大回撤": s["最大回撤"], "年数": round(s["年数"], 1)})
    a = pd.DataFrame(rows)
    a.to_csv(os.path.join(OUT, "val_start_year.csv"), index=False, encoding="utf-8-sig")
    print(a.round(3).to_string(index=False))

    # ---------------- B 参数扰动 ----------------
    print("\n### B 参数扰动（全期）")
    rows = []
    for lb, ma, vw, g in itertools.product([252, 315], [150, 200, 250], [40, 63, 90], [0.1, 0.2, 0.3]):
        res = run(close, open_, lookback=lb, ma=ma, vw=vw, gold=g)
        s = res.stats()
        rows.append({"形成期": lb // 21, "均线": ma, "波动窗口": vw, "黄金": g,
                     "年化": s["年化收益"], "夏普": s["夏普"], "最大回撤": s["最大回撤"]})
    b = pd.DataFrame(rows)
    b.to_csv(os.path.join(OUT, "val_param_grid.csv"), index=False, encoding="utf-8-sig")
    print(b[["年化", "夏普", "最大回撤"]].describe().round(3).to_string())
    print(f"  夏普<0.8 的组合占比: {(b['夏普'] < 0.8).mean():.0%}")
    print(f"  年化<0 的组合数: {(b['年化'] < 0).sum()}")

    # ---------------- C 成本压力 ----------------
    print("\n### C 成本压力")
    rows = []
    for c in [0.0005, 0.001, 0.002, 0.003]:
        s = run(close, open_, cost=c).stats()
        rows.append({"单边成本": f"{c:.2%}", "年化": s["年化收益"], "夏普": s["夏普"],
                     "最大回撤": s["最大回撤"]})
    c_df = pd.DataFrame(rows)
    c_df.to_csv(os.path.join(OUT, "val_cost.csv"), index=False, encoding="utf-8-sig")
    print(c_df.round(3).to_string(index=False))

    # ---------------- D 执行滞后 ----------------
    print("\n### D 执行滞后（T+1 开盘 vs T+2 开盘）")
    rows = []
    for lag in [1, 2]:
        s = run(close, open_, exec_lag=lag).stats()
        rows.append({"执行": f"T+{lag} 开盘", "年化": s["年化收益"], "夏普": s["夏普"]})
    d_df = pd.DataFrame(rows)
    d_df.to_csv(os.path.join(OUT, "val_exec_lag.csv"), index=False, encoding="utf-8-sig")
    print(d_df.round(3).to_string(index=False))

    # ---------------- E 留一法 ----------------
    print("\n### E 留一法（去掉单个资产）")
    rows = []
    for c in POOL:
        pool = [x for x in POOL if x != c]
        s = run(close, open_, pool=pool).stats()
        rows.append({"去掉": NAMES[c], "年化": s["年化收益"], "夏普": s["夏普"],
                     "最大回撤": s["最大回撤"]})
    s = run(close, open_).stats()
    rows.append({"去掉": "（无）", "年化": s["年化收益"], "夏普": s["夏普"], "最大回撤": s["最大回撤"]})
    e_df = pd.DataFrame(rows)
    e_df.to_csv(os.path.join(OUT, "val_leave_one_out.csv"), index=False, encoding="utf-8-sig")
    print(e_df.round(3).to_string(index=False))

    # ---------------- F Bootstrap ----------------
    print("\n### F Bootstrap（月度收益，block=6，2000 次）")
    r = nav.resample("ME").last().pct_change().dropna()
    bs = bootstrap(r)
    bs.quantile([0.05, 0.5, 0.95]).round(3).to_csv(
        os.path.join(OUT, "val_bootstrap.csv"), encoding="utf-8-sig")
    print(bs.quantile([0.05, 0.5, 0.95]).round(3).to_string())

    # ---------------- G 显著性 ----------------
    print("\n### G 显著性（月度超额，Newey-West t）")
    ew = (close[POOL].resample("ME").last().pct_change().mean(axis=1))
    hs = close["510300"].resample("ME").last().pct_change()
    rows = []
    for name, bench in [("四资产等权", ew), ("沪深300", hs)]:
        ex = (r - bench).dropna()
        rows.append({"基准": name, "月均超额": ex.mean(), "NW_t": nw_t(ex),
                     "胜率": (ex > 0).mean()})
        print(f"  vs {name}: 月均超额 {ex.mean():+.2%}, t={nw_t(ex):.2f}, 胜率 {(ex>0).mean():.0%}")
    pd.DataFrame(rows).to_csv(os.path.join(OUT, "val_significance.csv"),
                              index=False, encoding="utf-8-sig")

    # ---------------- H 实现一致性 ----------------
    print("\n### H 实现一致性（回测末仓 vs 生产信号）")
    from final_strategy import compute_signal
    sig = compute_signal(close)
    last_w = base.weights.iloc[-1].fillna(0)
    for c in codes:
        if abs(last_w.get(c, 0) - sig["weights"].get(c, 0)) > 0.02:
            print(f"  !! {NAMES[c]} 回测 {last_w.get(c,0):.1%} vs 信号 {sig['weights'].get(c,0):.1%}")
    print("  回测末仓:", {NAMES[c]: f"{last_w.get(c,0):.1%}" for c in codes if last_w.get(c, 0) > 0.01})
    print("  生产信号:", {NAMES[c]: f"{v:.1%}" for c, v in sig["weights"].items() if v > 0.01})

    # 滚动 36 个月
    print("\n### 滚动 36 个月收益")
    roll = (nav / nav.shift(36) - 1).dropna()
    print(f"  最差 {roll.min():.1%}（{roll.idxmin().date()}），最好 {roll.max():.1%}，"
          f"负值占比 {(roll < 0).mean():.0%}")


if __name__ == "__main__":
    main()
