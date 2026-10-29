"""动量延续性诊断：先回答"跟不跟得住最强"，再谈回测。

输出：
  output/tables/*.csv   各诊断表
  output/figs/*.png     关键图
  output/diagnostics.md 汇总
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from backtest import month_end_trading_days
from data import load_panel

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "output")
os.makedirs(os.path.join(OUT, "tables"), exist_ok=True)
os.makedirs(os.path.join(OUT, "figs"), exist_ok=True)

CODES = ["159915", "513100", "510300"]
NAMES = {"159915": "创业板", "513100": "纳指100", "510300": "沪深300", "511010": "国债"}
DEF = "511010"
START = "2013-06-01"
HORIZONS = [("1M", 1, 0), ("2M", 2, 0), ("3M", 3, 0), ("6M", 6, 0),
            ("9M", 9, 0), ("12M", 12, 0), ("12-1M", 12, 1)]


def load():
    px = load_panel("close", CODES + [DEF])
    px = px[px.index >= START]
    dates = month_end_trading_days(px.index)
    m = pd.DataFrame({c: px[c].reindex(dates, method="ffill") for c in px.columns})
    return px, m


def formation(m: pd.DataFrame, k: int, skip: int = 0) -> pd.DataFrame:
    px = m[CODES]
    return px.shift(skip) / px.shift(skip + k) - 1


def forward(m: pd.DataFrame, h: int = 1) -> pd.DataFrame:
    px = m[CODES]
    return px.shift(-h) / px - 1


def tstat(x: pd.Series) -> float:
    x = x.dropna()
    if len(x) < 3 or x.std() == 0:
        return np.nan
    return x.mean() / x.std() * np.sqrt(len(x))


def rank_panel(sig: pd.DataFrame) -> pd.DataFrame:
    ok = sig.notna().sum(axis=1) == 3
    rk = sig.rank(axis=1, ascending=False, method="first")
    rk.loc[~ok] = np.nan
    return rk


def leader_of(sig: pd.DataFrame) -> pd.Series:
    """当月信号冠军；样本不足 3 个资产时为 NaN。"""
    rk = rank_panel(sig)
    lead = pd.Series(index=rk.index, dtype=object)
    ok = rk.notna().sum(axis=1) == 3
    if ok.any():
        lead[ok] = rk[ok].idxmax(axis=1)
    return lead


# --------------------------------------------------------------------------- #
def t1_signal_quality(m: pd.DataFrame) -> pd.DataFrame:
    fwd = forward(m, 1)
    fr = fwd.rank(axis=1, ascending=False, method="first")
    rows = []
    for label, k, skip in HORIZONS:
        sig = formation(m, k, skip)
        rk = rank_panel(sig)
        valid = rk.notna().sum(axis=1) == 3
        top = fwd.where(rk == 1).max(axis=1)
        mid = fwd.where(rk == 2).max(axis=1)
        bot = fwd.where(rk == 3).max(axis=1)
        s = pd.concat([top, mid, bot], axis=1, keys=["top", "mid", "bot"]).dropna()
        spread = s["top"] - s["bot"]
        hit = ((rk == 1) & (fr == 1)).sum(axis=1)[valid]
        rows.append({
            "形成期": label,
            "样本月": len(s),
            "Top月均": s["top"].mean(),
            "Mid月均": s["mid"].mean(),
            "Bot月均": s["bot"].mean(),
            "多空差": spread.mean(),
            "多空t": tstat(spread),
            "命中率": hit.mean(),
            "跑赢等权率": (top[valid] > fwd[valid].mean(axis=1)).mean(),
        })
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(OUT, "tables", "T1_signal_quality.csv"), index=False, encoding="utf-8-sig")
    return df


def t2_persistence(m: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    rows, mats = [], {}
    for label, k, skip in HORIZONS:
        sig = formation(m, k, skip)
        rk = rank_panel(sig)
        leader = leader_of(sig)
        nxt = leader.shift(-1)
        ok = leader.notna() & nxt.notna()
        persist = (leader == nxt)[ok].mean()
        runs, cur, cnt = [], None, 0
        for x in leader.dropna():
            if x == cur:
                cnt += 1
            else:
                if cur is not None:
                    runs.append(cnt)
                cur, cnt = x, 1
        if cur is not None:
            runs.append(cnt)
        rows.append({
            "形成期": label,
            "样本月": int(ok.sum()),
            "冠军延续率": persist,
            "随机基准": 1 / 3,
            "平均在位月数": np.mean(runs) if runs else np.nan,
        })
        mats[label] = pd.crosstab(leader, nxt, normalize="index")
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(OUT, "tables", "T2_persistence.csv"), index=False, encoding="utf-8-sig")
    return df, mats


def t3_conditional(m: pd.DataFrame, px: pd.DataFrame, k: int = 12, skip: int = 0) -> pd.DataFrame:
    sig = formation(m, k, skip)
    rk = rank_panel(sig)
    leader = leader_of(sig)
    nxt = leader.shift(-1)
    ok = leader.notna() & nxt.notna()
    persist = (leader == nxt).where(ok)

    ss = sig.where(rk.notna().sum(axis=1) == 3)
    srt = np.sort(ss.values, axis=1)
    disp = pd.Series(srt[:, -1] - srt[:, -2], index=ss.index)

    ma200 = px["510300"].rolling(200).mean()
    state = (px["510300"] > ma200).reindex(m.index, method="ffill").fillna(False).astype(bool)
    ew = (1 + px[CODES].pct_change()).cumprod().sum(axis=1)
    vol60 = (ew.pct_change().rolling(60).std() * np.sqrt(252)).reindex(m.index, method="ffill")
    dd = (px["510300"] / px["510300"].cummax() - 1).reindex(m.index, method="ffill")

    df = pd.DataFrame({
        "persist": persist,
        "top_fwd": forward(m, 1).where(rk == 1).max(axis=1),
        "ew_fwd": forward(m, 1).mean(axis=1),
        "disp": disp, "ma": state, "vol": vol60, "dd": dd,
    })
    rows = []

    def add(name, mask):
        x = df[mask.fillna(False)]
        rows.append({
            "条件": name, "月数": int(len(x)),
            "延续率": x["persist"].mean(),
            "Top月均": x["top_fwd"].mean(),
            "等权月均": x["ew_fwd"].mean(),
            "超额": x["top_fwd"].mean() - x["ew_fwd"].mean(),
        })

    qs = disp.quantile([1 / 3, 2 / 3]).values
    add(f"离散度低(<{qs[0]:.3f})", disp <= qs[0])
    add("离散度中", (disp > qs[0]) & (disp <= qs[1]))
    add(f"离散度高(>{qs[1]:.3f})", disp > qs[1])
    add("300在200日线上", df["ma"])
    add("300在200日线下", ~df["ma"])
    v1, v2 = vol60.quantile([1 / 3, 2 / 3])
    add("低波动", vol60 <= v1)
    add("中波动", (vol60 > v1) & (vol60 <= v2))
    add("高波动", vol60 > v2)
    add("300回撤<-10%", dd < -0.10)
    add("300回撤>=-10%", dd >= -0.10)

    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(OUT, "tables", "T3_conditional.csv"), index=False, encoding="utf-8-sig")
    return out


def _smooth_one(px: pd.Series, dates, k: int, skip: int) -> pd.DataFrame:
    rows = []
    for d in dates:
        pos_end = px.index.searchsorted(d) - 1 - skip * 21
        pos_start = pos_end - k * 21
        if pos_start < 1 or pos_end >= len(px):
            continue
        seg = px.iloc[pos_start:pos_end + 1].dropna()
        if len(seg) < 40:
            continue
        y = np.log(seg.values)
        x = np.arange(len(y))
        corr = np.corrcoef(x, y)[0, 1]
        ret = seg.iloc[-1] / seg.iloc[0] - 1
        daily = seg.pct_change().dropna()
        rows.append({
            "date": d, "code": px.name,
            "r2": corr ** 2 if np.isfinite(corr) else np.nan,
            "pos_ratio": (daily > 0).mean(),
            "max_day_share": daily.max() / ret if ret > 0 else np.nan,
        })
    return pd.DataFrame(rows)


def t4_smoothness(m: pd.DataFrame, px: pd.DataFrame, k: int = 12, skip: int = 0) -> pd.DataFrame:
    sig = formation(m, k, skip)
    rk = rank_panel(sig)
    leader = leader_of(sig)
    nxt = leader.shift(-1)
    fwd = forward(m, 1)

    sm = pd.concat([_smooth_one(px[c].rename(c), m.index, k, skip) for c in CODES])
    smap = {(r.date, r.code): r for r in sm.itertuples()}

    recs = []
    for d, c in leader.dropna().items():
        rec = smap.get((d, c))
        if rec is None:
            continue
        recs.append({
            "date": d, "code": c, "r2": rec.r2, "pos_ratio": rec.pos_ratio,
            "max_day_share": rec.max_day_share,
            "fwd": fwd.loc[d, c] if c in fwd.columns else np.nan,
            "persist": float(nxt.loc[d] == c) if pd.notna(nxt.loc[d]) else np.nan,
        })
    v = pd.DataFrame(recs).dropna(subset=["fwd"])
    rows = []
    for feat in ["r2", "pos_ratio", "max_day_share"]:
        x = v.dropna(subset=[feat])
        med = x[feat].median()
        for lab, mask in [("低", x[feat] <= med), ("高", x[feat] > med)]:
            rows.append({
                "特征": feat, "分组": lab, "样本": int(mask.sum()),
                "下月延续率": x.loc[mask, "persist"].mean(),
                "持有下月均收益": x.loc[mask, "fwd"].mean(),
            })
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(OUT, "tables", "T4_smoothness.csv"), index=False, encoding="utf-8-sig")
    return out


def t5_capture(m: pd.DataFrame, k: int = 12, skip: int = 0) -> pd.DataFrame:
    sig = formation(m, k, skip)
    rk = rank_panel(sig)
    rows = []
    for h in [1, 3, 6, 12]:
        fwd = forward(m, h)
        fr = fwd.rank(axis=1, ascending=False, method="first")
        held = fwd.where(rk == 1).max(axis=1)
        held_rank = fr.where(rk == 1).max(axis=1)
        best = fwd.max(axis=1)
        valid = held.notna() & best.notna()
        regret = (best - held)[valid]
        rows.append({
            "前瞻": f"{h}M",
            "样本": int(valid.sum()),
            "持有平均排名": held_rank[valid].mean(),
            "持有=最强": (held_rank[valid] == 1).mean(),
            "持有在前2": (held_rank[valid] <= 2).mean(),
            "平均后悔": regret.mean(),
            "后悔90分位": regret.quantile(0.9),
        })
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(OUT, "tables", "T5_capture.csv"), index=False, encoding="utf-8-sig")
    return out


def t6_new_vs_incumbent(m: pd.DataFrame, k: int = 12, skip: int = 0) -> pd.DataFrame:
    """新晋冠军 vs 连任冠军：换仓是否买在末期。"""
    sig = formation(m, k, skip)
    rk = rank_panel(sig)
    leader = leader_of(sig)
    prev = leader.shift(1)
    state = pd.Series(np.where(leader == prev, "连任", "新晋"), index=leader.index)
    state[leader.isna() | prev.isna()] = np.nan
    rows = []
    for h in [1, 3]:
        fwd = forward(m, h)
        held = fwd.where(rk == 1).max(axis=1)
        for lab in ["连任", "新晋"]:
            mask = state == lab
            rows.append({
                "前瞻": f"{h}M", "类型": lab, "月数": int(mask.sum()),
                "持有期收益": held[mask].mean(),
                "胜率": (held[mask] > 0).mean(),
            })
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(OUT, "tables", "T6_new_vs_incumbent.csv"), index=False, encoding="utf-8-sig")
    return out


def t7_state_returns(m: pd.DataFrame, px: pd.DataFrame) -> pd.DataFrame:
    """不同市场状态下：等权股票、冠军、债券的**未来一月**收益与尾部。"""
    ret = m[CODES + [DEF]].shift(-1) / m[CODES + [DEF]] - 1
    ew = ret[CODES].mean(axis=1)
    sig = formation(m, 12, 0)
    leader = leader_of(sig)
    top = ret[CODES].where(rank_panel(sig) == 1).max(axis=1)
    bond = ret[DEF]

    ma200 = px["510300"].rolling(200).mean()
    state = (px["510300"] > ma200).reindex(m.index, method="ffill").fillna(False).astype(bool)
    ew_nav = (1 + px[CODES].pct_change()).cumprod().sum(axis=1)
    vol60 = (ew_nav.pct_change().rolling(60).std() * np.sqrt(252)).reindex(m.index, method="ffill")
    v1, v2 = vol60.quantile([1 / 3, 2 / 3])

    rows = []

    def add(name, mask):
        x = pd.DataFrame({"ew": ew, "top": top, "bond": bond})[mask.fillna(False)].dropna()
        rows.append({
            "状态": name, "月数": len(x),
            "股票等权月均": x["ew"].mean(),
            "冠军月均": x["top"].mean(),
            "债券月均": x["bond"].mean(),
            "股票最差月": x["ew"].min(),
            "股票下跌月占比": (x["ew"] < 0).mean(),
            "股票5%分位": x["ew"].quantile(0.05),
        })

    add("300>200MA", state)
    add("300<200MA", ~state)
    add("低波动", vol60 <= v1)
    add("中波动", (vol60 > v1) & (vol60 <= v2))
    add("高波动", vol60 > v2)
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(OUT, "tables", "T7_state_returns.csv"), index=False, encoding="utf-8-sig")
    return out


def t8_abs_momentum(m: pd.DataFrame) -> pd.DataFrame:
    """绝对动量：冠军的 12M 收益是否跑赢债券，对下月有无预测力。"""
    sig = formation(m, 12, 0)
    rk = rank_panel(sig)
    leader = leader_of(sig)
    bond_mom = m[DEF] / m[DEF].shift(12) - 1
    leader_mom = pd.Series([sig.loc[d, c] if pd.notna(c) else np.nan for d, c in leader.items()],
                           index=leader.index)
    abs_sig = leader_mom - bond_mom
    fwd = forward(m, 1)
    top_fwd = fwd.where(rk == 1).max(axis=1)
    bond_fwd = (m[DEF].shift(-1) / m[DEF] - 1)
    rows = []
    for lab, mask in [("绝对动量>0", abs_sig > 0), ("绝对动量<=0", abs_sig <= 0)]:
        x = pd.DataFrame({"top": top_fwd, "bond": bond_fwd})[mask.fillna(False)].dropna()
        rows.append({
            "条件": lab, "月数": len(x),
            "股票月均": x["top"].mean(),
            "债券月均": x["bond"].mean(),
            "股票下跌概率": (x["top"] < 0).mean(),
            "股票最差月": x["top"].min(),
        })
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(OUT, "tables", "T8_abs_momentum.csv"), index=False, encoding="utf-8-sig")
    return out


def main():
    px, m = load()
    print(f"面板: {m.index[0].date()} ~ {m.index[-1].date()}  月末数={len(m)}", flush=True)

    t1 = t1_signal_quality(m)
    print("\n### T1 信号质量（预测下月收益）")
    print(t1.round(4).to_string(index=False), flush=True)

    t2, mats = t2_persistence(m)
    print("\n### T2 冠军持续性（随机基准 1/3）")
    print(t2.round(4).to_string(index=False), flush=True)
    for k, mat in mats.items():
        print(f"\n[{k}] 转移矩阵（行=本月冠军，列=下月冠军）")
        print(mat.round(3).to_string(), flush=True)

    t3 = t3_conditional(m, px)
    print("\n### T3 条件持续性（12M 信号）")
    print(t3.round(4).to_string(index=False), flush=True)

    t4 = t4_smoothness(m, px)
    print("\n### T4 路径平滑度（当月冠军）")
    print(t4.round(4).to_string(index=False), flush=True)

    t5 = t5_capture(m)
    print("\n### T5 捕获率（12M 信号）")
    print(t5.round(4).to_string(index=False), flush=True)

    t6 = t6_new_vs_incumbent(m)
    print("\n### T6 新晋 vs 连任")
    print(t6.round(4).to_string(index=False), flush=True)

    t7 = t7_state_returns(m, px)
    print("\n### T7 各状态下的收益与尾部（月频）")
    print(t7.round(4).to_string(index=False), flush=True)

    t8 = t8_abs_momentum(m)
    print("\n### T8 绝对动量（冠军 12M 是否跑赢债券）")
    print(t8.round(4).to_string(index=False), flush=True)

    fwd1 = forward(m, 1)
    perfect = (1 + fwd1.max(axis=1).fillna(0)).cumprod()
    ew = (1 + fwd1.mean(axis=1).fillna(0)).cumprod()
    hs = (1 + fwd1["510300"].fillna(0)).cumprod()
    print("\n### 参考上限（月末调仓、无成本）")
    for name, s in [("完美预知", perfect), ("三资产等权", ew), ("沪深300", hs)]:
        yrs = len(s) / 12
        print(f"{name}: 累计 {s.iloc[-1]-1:.1%}  年化 {s.iloc[-1]**(1/yrs)-1:.1%}  最大回撤 {(s/s.cummax()-1).min():.1%}")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS"]
    plt.rcParams["axes.unicode_minus"] = False

    fig, ax = plt.subplots(figsize=(11, 5.5))
    norm = m[CODES] / m[CODES].iloc[0]
    for c in CODES:
        ax.plot(norm.index, norm[c], label=NAMES[c], lw=1.4)
    leader = leader_of(formation(m, 12, 0))
    colors = {"159915": "#d62728", "513100": "#1f77b4", "510300": "#2ca02c"}
    for i in range(len(leader) - 1):
        if pd.isna(leader.iloc[i]):
            continue
        ax.axvspan(leader.index[i], leader.index[i + 1],
                   color=colors.get(leader.iloc[i], "gray"), alpha=0.08, lw=0)
    ax.set_yscale("log")
    ax.set_title("三资产净值（对数）与 12M 动量冠军（底色）")
    ax.legend(loc="upper left")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "figs", "fig1_nav_leader.png"), dpi=150)
    plt.close(fig)

    with open(os.path.join(OUT, "diagnostics.md"), "w", encoding="utf-8") as f:
        f.write("# 动量延续性诊断\n\n")
        f.write(f"面板: {m.index[0].date()} ~ {m.index[-1].date()}，月末数 {len(m)}\n\n")
        for title, df in [("T1 信号质量", t1), ("T2 冠军持续性", t2), ("T3 条件持续性", t3),
                          ("T4 路径平滑度", t4), ("T5 捕获率", t5), ("T6 新晋vs连任", t6)]:
            f.write(f"## {title}\n\n{df.round(4).to_string(index=False)}\n\n")
    print(f"\n已保存到 {OUT}", flush=True)


if __name__ == "__main__":
    main()
