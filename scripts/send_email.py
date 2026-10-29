"""Email the freshly generated weekly signal using QQ Mail SMTP over TLS."""
import json
import os
import html
import io
import math
import statistics
from datetime import date
from email.message import EmailMessage
from pathlib import Path
import smtplib
import ssl
import sys

NAMES = {
    "159915": "创业板", "510300": "沪深300", "510500": "中证500",
    "513500": "标普500", "518880": "黄金", "511010": "国债",
}


def evaluate(nav, expected):
    """Match the PWA's 52-week sample and evaluation thresholds."""
    if len(nav) < 53:
        return None
    rows = nav[-53:]
    values = [row["nav"] for row in rows]
    if any(not math.isfinite(v) or v <= 0 for v in values):
        raise ValueError("净值数据无效，无法生成评估")
    cagr = values[-1] / values[0] - 1
    changes = [b / a - 1 for a, b in zip(values, values[1:])]
    vol = statistics.stdev(changes) * math.sqrt(52)
    peak = values[0]
    mdd = 0.0
    for value in values:
        peak = max(peak, value)
        mdd = min(mdd, value / peak - 1)
    levels = [
        2 if cagr < 0 else 1 if cagr < expected["cagr"] * .75 else 0,
        2 if vol > expected["vol"] * 1.6 else 1 if vol > expected["vol"] * 1.3 else 0,
        2 if mdd < expected["mdd"] * 1.5 else 1 if mdd < expected["mdd"] * 1.15 else 0,
    ]
    return {"cagr": cagr, "vol": vol, "mdd": mdd, "level": max(levels), "rows": rows}


def make_chart(rows):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(8, 3.6), layout="constrained")
    dates = [date.fromisoformat(row["date"]) for row in rows]
    for key, label, color in [("nav", "Strategy", "#b23a2f"), ("sp500", "S&P 500 ETF", "#1f7a5c"), ("hs300", "CSI 300 ETF", "#2c5282")]:
        base = rows[0].get(key)
        if base is None or base <= 0:
            continue
        values = [(row[key] / base - 1) * 100 if row.get(key) is not None else float("nan") for row in rows]
        ax.plot(dates, values, label=label, color=color, linewidth=1.8)
    ax.axhline(0, color="#aaa", linewidth=.7)
    ax.set_title("52-week cumulative return")
    ax.set_ylabel("Return (%)")
    ax.grid(alpha=.2)
    ax.legend(loc="best", fontsize=8)
    fig.autofmt_xdate()
    output = io.BytesIO()
    fig.savefig(output, format="png", dpi=150)
    plt.close(fig)
    return output.getvalue()


def main() -> None:
    sender = os.environ.get("QQ_MAIL_USER", "").strip()
    password = os.environ.get("QQ_MAIL_AUTH_CODE", "").strip()
    recipient = os.environ.get("EMAIL_TO", "").strip()
    if not all((sender, password, recipient)):
        raise SystemExit("请在 GitHub Actions Secrets 中设置 QQ_MAIL_USER、QQ_MAIL_AUTH_CODE 和 EMAIL_TO。")
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "app/public/data/latest.json")
    signal = json.loads(path.read_text(encoding="utf-8"))
    nav = json.loads((path.parent / "nav.json").read_text(encoding="utf-8"))
    meta = json.loads((path.parent / "meta.json").read_text(encoding="utf-8"))
    result = evaluate(nav, meta["expected"])
    allocations = "\n".join(
        f"  {NAMES.get(code, code)}（{code}）：{weight:.1%}"
        for code, weight in signal["weights"].items() if weight > 0
    )
    message = EmailMessage()
    message["Subject"] = f"ETF 轮动周报 | 信号日期 {signal['asof']}"
    message["From"] = sender
    message["To"] = recipient
    if result is None:
        assessment = "近 52 周表现评估：数据不足 53 个周度净值点，无法评估或绘制一年曲线。"
    else:
        status = ["正常", "关注", "异常"][result["level"]]
        assessment = (
            f"近 52 周表现评估：{status}（按应用内历史指标阈值）\n"
            f"  年化收益：{result['cagr']:.1%}（长期 {meta['expected']['cagr']:.1%}）\n"
            f"  年化波动率：{result['vol']:.1%}（长期 {meta['expected']['vol']:.1%}）\n"
            f"  最大回撤：{result['mdd']:.1%}（历史最大 {meta['expected']['mdd']:.1%}）\n"
            f"  周度区间：{result['rows'][0]['date']} 至 {result['rows'][-1]['date']}（周末标签）\n"
            "该状态仅表示指标相对历史阈值，不保证策略正确或未来表现。"
        )
    body = (
        f"ETF 轮动每周信号\n\n行情截止：{signal['asof']}\n"
        f"信号生成：{signal['generated_at']}\n\n目标仓位：\n{allocations}\n\n"
        f"信号说明：{signal['reason']}\n\n"
        f"{assessment}\n\n"
        "查看应用：https://qaderi11.github.io/etf_change/\n\n"
        "请核对行情截止日期；历史回测不代表未来收益。"
    )
    message.set_content(body)
    if result is not None:
        chart = make_chart(result["rows"])
        message.add_alternative(
            f"<html><body><pre style='font: 14px sans-serif; white-space: pre-wrap'>{html.escape(body)}</pre>"
            "<p>近 52 周累计收益曲线（以区间起点归零）</p>"
            "<img src='cid:nav-chart' alt='52-week cumulative return chart'></body></html>",
            subtype="html",
        )
        message.get_payload()[-1].add_related(chart, maintype="image", subtype="png", cid="<nav-chart>", filename="52-week-return.png", disposition="inline")
    with smtplib.SMTP_SSL("smtp.qq.com", 465, timeout=30, context=ssl.create_default_context()) as smtp:
        smtp.login(sender, password)
        smtp.send_message(message)
    print("信号邮件已交给邮件服务器。")


if __name__ == "__main__":
    main()
