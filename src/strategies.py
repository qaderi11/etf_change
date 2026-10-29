"""经典 ETF 轮动策略集合。

所有策略签名：fn(signal_date, close_upto) -> {code: weight}
close_upto 为截至信号日收盘的复权价面板（含信号日，不含未来数据）。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------- #
# 资产池
# --------------------------------------------------------------------------- #
POOL_A = ["510050", "510300", "510500", "159915", "510880", "159901"]
POOL_A_MODERN = POOL_A + ["512100", "512890"]
POOL_ERBA = ["510300", "510500"]
POOL_GLOBAL = POOL_A + ["513100", "513500", "510900", "518880"]
BOND = "511010"
GOLD = "518880"


# --------------------------------------------------------------------------- #
# 工具
# --------------------------------------------------------------------------- #
def _px(close: pd.DataFrame, code: str) -> pd.Series:
    if code not in close.columns:
        return pd.Series(dtype=float)
    return close[code].dropna()


def momentum(close: pd.DataFrame, code: str, lookback: int, skip: int = 0) -> float:
    px = _px(close, code)
    if len(px) < lookback + skip + 1:
        return np.nan
    end = px.iloc[-1 - skip] if skip > 0 else px.iloc[-1]
    start = px.iloc[-1 - skip - lookback]
    return end / start - 1


def ann_vol(close: pd.DataFrame, code: str, lookback: int) -> float:
    px = _px(close, code)
    if len(px) < lookback + 1:
        return np.nan
    ret = px.iloc[-lookback - 1:].pct_change().dropna()
    return ret.std() * np.sqrt(252)


def above_ma(close: pd.DataFrame, code: str, window: int) -> bool:
    px = _px(close, code)
    if len(px) < window:
        return False
    return bool(px.iloc[-1] > px.iloc[-window:].mean())


def _normalize(w: dict) -> dict:
    tot = sum(w.values())
    return {k: v / tot for k, v in w.items()} if tot > 0 else {}


# --------------------------------------------------------------------------- #
# 基准
# --------------------------------------------------------------------------- #
def buy_hold(code: str):
    def fn(signal_date, close):
        return {code: 1.0}

    return fn


def equal_weight(pool):
    def fn(signal_date, close):
        avail = [c for c in pool if len(_px(close, c)) >= 60]
        return _normalize({c: 1.0 for c in avail})

    return fn


def inverse_vol(pool, lookback: int = 63):
    def fn(signal_date, close):
        w = {}
        for c in pool:
            v = ann_vol(close, c, lookback)
            if np.isfinite(v) and v > 0:
                w[c] = 1.0 / v
        return _normalize(w)

    return fn


# --------------------------------------------------------------------------- #
# 1. 动量轮动（相对动量）
# --------------------------------------------------------------------------- #
def momentum_rotation(
    pool,
    lookback: int = 252,
    topn: int = 1,
    skip: int = 0,
    risk_adjusted: bool = False,
    abs_filter: bool = False,
    abs_vs: str | None = None,
    market_gate: int | None = None,
    gate_code: str = "510300",
    gate_leader_ma: int | None = None,
    defensive: str = BOND,
    ma_filter: int | None = None,
    weight: str = "equal",
):
    """经典横截面动量轮动：按过去 lookback 日涨幅排序，持有前 topn。

    abs_filter:    第一名动量 <= 0 时转 defensive
    abs_vs:        第一名动量 <= 该资产（通常债券）动量时转 defensive
    market_gate:   gate_code 跌破 N 日均线时整体转 defensive
    gate_leader_ma: 大盘跌破均线时，若第一名自身仍在其 N 日均线上方则放行
    ma_filter:     第一名跌破自身 N 日均线时转 defensive
    """

    def fn(signal_date, close):
        scores = {}
        for c in pool:
            r = momentum(close, c, lookback, skip)
            if not np.isfinite(r):
                continue
            if risk_adjusted:
                v = ann_vol(close, c, lookback)
                if not np.isfinite(v) or v <= 0:
                    continue
                r = r / v
            scores[c] = r
        if not scores:
            return {defensive: 1.0}

        ranked = sorted(scores, key=scores.get, reverse=True)
        picks = ranked[:topn]

        if market_gate and not above_ma(close, gate_code, market_gate):
            if not (gate_leader_ma and above_ma(close, ranked[0], gate_leader_ma)):
                return {defensive: 1.0}

        if abs_vs:
            bench = momentum(close, abs_vs, lookback, skip)
            bench = bench if np.isfinite(bench) else 0.0
            if scores[picks[0]] <= bench:
                return {defensive: 1.0}
        elif abs_filter and scores[picks[0]] <= 0:
            return {defensive: 1.0}

        if ma_filter:
            good = [c for c in picks if above_ma(close, c, ma_filter)]
            if not good:
                return {defensive: 1.0}
            picks = good

        if weight == "equal" or len(picks) == 1:
            return _normalize({c: 1.0 for c in picks})
        if weight == "inv_vol":
            return _normalize({c: 1.0 / max(ann_vol(close, c, 63), 1e-6) for c in picks})
        return _normalize({c: max(scores[c], 1e-6) for c in picks})

    return fn


# --------------------------------------------------------------------------- #
# 2. 双动量（Dual Momentum, Antonacci 2014）
# --------------------------------------------------------------------------- #
def dual_momentum(
    pool,
    lookback: int = 252,
    topn: int = 1,
    defensive: str = BOND,
    cash: str | None = None,
    absolute: bool = True,
):
    """相对动量选最强，绝对动量（对比债券/现金）决定是否进攻。"""

    def fn(signal_date, close):
        scores = {c: momentum(close, c, lookback, 0) for c in pool}
        scores = {c: s for c, s in scores.items() if np.isfinite(s)}
        if not scores:
            return {defensive: 1.0}
        ranked = sorted(scores, key=scores.get, reverse=True)
        picks = ranked[:topn]
        if absolute:
            bench = momentum(close, defensive, lookback, 0)
            bench = bench if np.isfinite(bench) else 0.0
            if scores[picks[0]] <= bench:
                return {defensive: 1.0}
        return _normalize({c: 1.0 for c in picks})

    return fn


# --------------------------------------------------------------------------- #
# 3. 二八轮动（沪深300 vs 中证500）
# --------------------------------------------------------------------------- #
def erba_rotation(
    lookback: int = 20,
    ma: int = 20,
    defensive: str = BOND,
    use_ma: bool = True,
    pairs=("510300", "510500"),
):
    """经典二八：比较近 lookback 日涨幅，持有较强者；若两者都弱/跌破均线则空仓。

    use_ma=True 时，强者还需站上 ma 日均线才持有，否则转 defensive。
    """

    def fn(signal_date, close):
        r = {c: momentum(close, c, lookback, 0) for c in pairs}
        r = {c: v for c, v in r.items() if np.isfinite(v)}
        if not r:
            return {defensive: 1.0}
        best = max(r, key=r.get)
        if r[best] <= 0:
            return {defensive: 1.0}
        if use_ma and not above_ma(close, best, ma):
            return {defensive: 1.0}
        return {best: 1.0}

    return fn


# --------------------------------------------------------------------------- #
# 4. 趋势择时 + 等权（Faber 式）
# --------------------------------------------------------------------------- #
def trend_timing(pool, ma: int = 200, defensive: str = BOND, risk_on_all: bool = True):
    """大盘均线择时：沪深300 在 ma 日均线上方才持有股票池，否则持债。"""

    def fn(signal_date, close):
        if above_ma(close, "510300", ma):
            avail = [c for c in pool if len(_px(close, c)) >= 60]
            return _normalize({c: 1.0 for c in avail})
        return {defensive: 1.0}

    return fn


# --------------------------------------------------------------------------- #
# 5. 多资产轮动（股/债/商品/海外）
# --------------------------------------------------------------------------- #
def multi_asset_rotation(
    pool,
    lookback: int = 252,
    topn: int = 2,
    abs_filter: bool = True,
    defensive: str = BOND,
    vol_target: float | None = None,
):
    def fn(signal_date, close):
        scores = {c: momentum(close, c, lookback, 0) for c in pool}
        scores = {c: s for c, s in scores.items() if np.isfinite(s)}
        if not scores:
            return {defensive: 1.0}
        ranked = sorted(scores, key=scores.get, reverse=True)
        picks = ranked[:topn]
        if abs_filter:
            picks = [c for c in picks if scores[c] > 0] or [defensive]
        w = _normalize({c: 1.0 for c in picks})
        if vol_target:
            v = 0.0
            for c, wt in w.items():
                v += wt * (ann_vol(close, c, 63) or 0.0)
            lev = min(1.0, vol_target / v) if v > 0 else 1.0
            w = {c: wt * lev for c, wt in w.items()}
            w[defensive] = w.get(defensive, 0) + (1 - lev)
        return _normalize(w)

    return fn


# --------------------------------------------------------------------------- #
# 6. 大小盘 / 风格相对强弱轮动
# --------------------------------------------------------------------------- #
def style_rotation(
    growth="159915",
    value="510880",
    lookback: int = 63,
    ma: int = 120,
    defensive: str = BOND,
):
    """成长 vs 红利 相对强弱轮动，带均线过滤。"""

    def fn(signal_date, close):
        rg = momentum(close, growth, lookback, 0)
        rv = momentum(close, value, lookback, 0)
        if not (np.isfinite(rg) and np.isfinite(rv)):
            return {value: 1.0}
        pick = growth if rg > rv else value
        if not above_ma(close, pick, ma):
            return {defensive: 1.0}
        return {pick: 1.0}

    return fn
