"""ETF 日线数据下载与缓存。

数据源：腾讯行情（前复权，含分红调整），必要时回退到 akshare/东方财富。
缓存目录：data/{code}.csv
"""
from __future__ import annotations

import os
import time

import pandas as pd
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
os.makedirs(DATA_DIR, exist_ok=True)

# code -> (简称, 类别)
UNIVERSE: dict[str, tuple[str, str]] = {
    "510050": ("上证50", "A股宽基"),
    "510300": ("沪深300", "A股宽基"),
    "510500": ("中证500", "A股宽基"),
    "512100": ("中证1000", "A股宽基"),
    "159915": ("创业板指", "A股宽基"),
    "588000": ("科创50", "A股宽基"),
    "159901": ("深证100", "A股宽基"),
    "510880": ("红利", "A股风格"),
    "512890": ("红利低波", "A股风格"),
    "511010": ("国债ETF", "债券"),
    "511260": ("十年国债", "债券"),
    "518880": ("黄金ETF", "商品"),
    "513100": ("纳指ETF", "海外"),
    "513500": ("标普500", "海外"),
    "510900": ("H股ETF", "海外"),
    "513050": ("中概互联", "海外"),
}

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


def _tencent_symbol(code: str) -> str:
    return ("sh" if code.startswith(("5", "6")) else "sz") + code


def fetch_tencent(code: str, start: str = "2005-01-01") -> pd.DataFrame:
    """腾讯前复权日线，分页向前抓取。"""
    sym = _tencent_symbol(code)
    url = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
    end = pd.Timestamp.today().strftime("%Y-%m-%d")
    rows: list[list] = []
    for _ in range(30):
        param = {"param": f"{sym},day,{start},{end},640,qfq"}
        r = requests.get(url, params=param, headers={"User-Agent": UA}, timeout=20)
        r.raise_for_status()
        data = r.json()["data"][sym]
        k = data.get("qfqday") or data.get("day") or []
        if not k:
            break
        rows = k + rows
        first = k[0][0]
        if first <= start or len(k) < 10:
            break
        nxt = (pd.Timestamp(first) - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        if nxt >= end:
            break
        end = nxt
        time.sleep(0.25)

    df = pd.DataFrame(rows, columns=["date", "open", "close", "high", "low", "volume"])
    df["date"] = pd.to_datetime(df["date"])
    for c in ["open", "close", "high", "low", "volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["close"]).drop_duplicates("date").sort_values("date")
    return df.reset_index(drop=True)


def fetch_akshare(code: str) -> pd.DataFrame:
    import akshare as ak

    df = ak.fund_etf_hist_em(
        symbol=code, period="daily", start_date="20050101", end_date="20261231", adjust="hfq"
    )
    df = df.rename(
        columns={"日期": "date", "开盘": "open", "收盘": "close", "最高": "high", "最低": "low", "成交量": "volume"}
    )[["date", "open", "close", "high", "low", "volume"]]
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)


def download_all(force: bool = False) -> None:
    for code, (name, _) in UNIVERSE.items():
        path = os.path.join(DATA_DIR, f"{code}.csv")
        if os.path.exists(path) and not force:
            print(f"[skip] {code} {name}", flush=True)
            continue
        try:
            df = fetch_tencent(code)
            src = "tencent"
        except Exception as exc:  # noqa: BLE001
            print(f"[tencent fail] {code}: {exc}", flush=True)
            df = fetch_akshare(code)
            src = "akshare"
        df.to_csv(path, index=False, encoding="utf-8-sig")
        print(
            f"[ok] {code} {name} {df.date.min().date()}~{df.date.max().date()} n={len(df)} ({src})",
            flush=True,
        )
        time.sleep(0.3)


def load_panel(field: str = "close", codes: list[str] | None = None) -> pd.DataFrame:
    codes = codes or list(UNIVERSE)
    out = {}
    for code in codes:
        path = os.path.join(DATA_DIR, f"{code}.csv")
        if not os.path.exists(path):
            continue
        df = pd.read_csv(path, parse_dates=["date"]).set_index("date")
        out[code] = df[field]
    return pd.DataFrame(out).sort_index()


if __name__ == "__main__":
    import sys

    codes = sys.argv[1:] or list(UNIVERSE)
    for code in codes:
        name = UNIVERSE.get(code, ("?", "?"))[0]
        path = os.path.join(DATA_DIR, f"{code}.csv")
        if os.path.exists(path):
            print(f"[skip] {code} {name}", flush=True)
            continue
        try:
            df = fetch_tencent(code)
            src = "tencent"
        except Exception as exc:  # noqa: BLE001
            print(f"[tencent fail] {code}: {exc}", flush=True)
            df = fetch_akshare(code)
            src = "akshare"
        df.to_csv(path, index=False, encoding="utf-8-sig")
        print(
            f"[ok] {code} {name} {df.date.min().date()}~{df.date.max().date()} n={len(df)} ({src})",
            flush=True,
        )
        time.sleep(0.3)
