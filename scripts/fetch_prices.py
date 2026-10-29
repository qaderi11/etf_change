"""更新 6 只标的的日线数据（写入 data/）。

优先腾讯前复权，失败回退 akshare/东方财富。任何一只失败都会报错退出，
避免用残缺数据覆盖已有缓存。
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from data import DATA_DIR, fetch_tencent, fetch_akshare  # noqa: E402

CODES = ["159915", "510300", "510500", "513500", "518880", "511010"]


def main() -> None:
    failed = []
    for code in CODES:
        path = Path(DATA_DIR) / f"{code}.csv"
        try:
            df = fetch_tencent(code)
            if len(df) < 500:
                raise ValueError(f"行数异常 {len(df)}")
        except Exception as exc:  # noqa: BLE001
            print(f"[tencent fail] {code}: {exc}", flush=True)
            try:
                df = fetch_akshare(code)
            except Exception as exc2:  # noqa: BLE001
                print(f"[all fail] {code}: {exc2}", flush=True)
                failed.append(code)
                continue
        df.to_csv(path, index=False, encoding="utf-8-sig")
        print(f"[ok] {code} {df.date.min().date()} ~ {df.date.max().date()} n={len(df)}", flush=True)
        time.sleep(0.3)

    if failed:
        raise SystemExit(f"以下标的更新失败：{failed}")


if __name__ == "__main__":
    main()
