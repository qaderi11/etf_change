"""Email the freshly generated weekly signal using QQ Mail SMTP over TLS."""
import json
import os
from email.message import EmailMessage
from pathlib import Path
import smtplib
import ssl
import sys

NAMES = {
    "159915": "创业板", "510300": "沪深300", "510500": "中证500",
    "513500": "标普500", "518880": "黄金", "511010": "国债",
}


def main() -> None:
    sender = os.environ.get("QQ_MAIL_USER", "").strip()
    password = os.environ.get("QQ_MAIL_AUTH_CODE", "").strip()
    recipient = os.environ.get("EMAIL_TO", "").strip()
    if not all((sender, password, recipient)):
        raise SystemExit("请在 GitHub Actions Secrets 中设置 QQ_MAIL_USER、QQ_MAIL_AUTH_CODE 和 EMAIL_TO。")
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "app/public/data/latest.json")
    signal = json.loads(path.read_text(encoding="utf-8"))
    allocations = "\n".join(
        f"  {NAMES.get(code, code)}（{code}）：{weight:.1%}"
        for code, weight in signal["weights"].items() if weight > 0
    )
    message = EmailMessage()
    message["Subject"] = f"ETF 轮动周报 | 信号日期 {signal['asof']}"
    message["From"] = sender
    message["To"] = recipient
    message.set_content(
        f"ETF 轮动每周信号\n\n行情截止：{signal['asof']}\n"
        f"信号生成：{signal['generated_at']}\n\n目标仓位：\n{allocations}\n\n"
        f"信号说明：{signal['reason']}\n\n"
        "查看应用：https://qaderi11.github.io/etf_change/\n\n"
        "请核对行情截止日期；历史回测不代表未来收益。"
    )
    with smtplib.SMTP_SSL("smtp.qq.com", 465, timeout=30, context=ssl.create_default_context()) as smtp:
        smtp.login(sender, password)
        smtp.send_message(message)
    print("信号邮件已交给邮件服务器。")


if __name__ == "__main__":
    main()
