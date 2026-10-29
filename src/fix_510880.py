"""重新抓取 510880（中证红利ETF）的腾讯后复权序列，替换此前损坏的 qfq 数据。"""
from __future__ import annotations

import time

import pandas as pd
import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0 Safari/537.36"
URL = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"


def fetch_hfq(sym: str, start: str = "2013-01-01") -> pd.DataFrame:
    end = pd.Timestamp.today().strftime("%Y-%m-%d")
    rows: list[list] = []
    for _ in range(30):
        r = requests.get(URL, params={"param": f"{sym},day,{start},{end},640,hfq"},
                         headers={"User-Agent": UA}, timeout=20)
        d = r.json()["data"][sym]
        k = d.get("hfqday") or d.get("day") or []
        if not k:
            break
        rows = k + rows
        if k[0][0] <= start or len(k) < 10:
            break
        nxt = (pd.Timestamp(k[0][0]) - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        if nxt >= end:
            break
        end = nxt
        time.sleep(0.25)

    df = pd.DataFrame(rows, columns=["date", "open", "close", "high", "low", "volume"])
    df["date"] = pd.to_datetime(df["date"])
    for c in df.columns[1:]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.dropna(subset=["close"]).drop_duplicates("date").sort_values("date").reset_index(drop=True)


if __name__ == "__main__":
    df = fetch_hfq("sh510880")
    df.to_csv("data/510880.csv", index=False, encoding="utf-8-sig")
    r = df["close"].pct_change()
    print(f"{df.date.min().date()} ~ {df.date.max().date()} n={len(df)}")
    print(f"max|r| {r.abs().max():.1%} @ {r.abs().idxmax().date()}   "
          f"累计 {df.close.iloc[-1]/df.close.iloc[0]-1:.1%}")
