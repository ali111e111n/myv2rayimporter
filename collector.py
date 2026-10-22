#!/usr/bin/env python3
"""
جمع‌آوری کانفیگ‌های V2Ray از کانال(های) عمومی تلگرام و ساخت لینک Subscription.

خروجی:
  sub.txt        -> نسخه base64 (برای v2rayNG / Hiddify / NekoBox)
  sub_plain.txt  -> همان لیست به‌صورت متن ساده (هر خط یک کانفیگ)
"""

import base64
import html
import json
import os
import re
import socket
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

# ---------------- تنظیمات (از متغیرهای محیطی هم قابل تغییر است) ----------------
CHANNELS = [c.strip() for c in os.getenv("CHANNELS", "meliproxyy").split(",") if c.strip()]
MAX_AGE_HOURS = int(os.getenv("MAX_AGE_HOURS", "48"))   # فقط کانفیگ‌های پست‌های این چند ساعت اخیر
MAX_PAGES = int(os.getenv("MAX_PAGES", "8"))            # هر صفحه حدود ۲۰ پست
TCP_CHECK = os.getenv("TCP_CHECK", "1") == "1"          # حذف سرورهایی که اصلاً پورتشان باز نیست
TCP_TIMEOUT = float(os.getenv("TCP_TIMEOUT", "3"))
REMARK_PREFIX = os.getenv("REMARK_PREFIX", "meli")

PROTOCOLS = ("vless", "vmess", "trojan", "ss", "hysteria2", "hy2", "tuic")
CONFIG_RE = re.compile(r"(?:%s)://[^\s<>\"'`]+" % "|".join(PROTOCOLS))
POST_RE = re.compile(r'<div class="tgme_widget_message_wrap.*?(?=<div class="tgme_widget_message_wrap|\Z)', re.S)
TIME_RE = re.compile(r'<time[^>]*datetime="([^"]+)"')
BEFORE_RE = re.compile(r'data-post="[^/]+/(\d+)"')
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", "replace")


def scrape_channel(channel: str, cutoff: datetime) -> list[str]:
    found, before = [], None
    for _ in range(MAX_PAGES):
        url = f"https://t.me/s/{channel}" + (f"?before={before}" if before else "")
        try:
            page = fetch(url)
        except Exception as e:
            print(f"[!] {channel}: {e}", file=sys.stderr)
            break
        posts = POST_RE.findall(page)
        if not posts:
            break
        too_old = False
        for post in posts:
            m = TIME_RE.search(post)
            if m:
                t = datetime.fromisoformat(m.group(1).replace("Z", "+00:00"))
                if t < cutoff:
                    too_old = True
                    continue
            text = html.unescape(re.sub(r"<br\s*/?>", "\n", post))
            text = re.sub(r"<[^>]+>", " ", text)
            found.extend(CONFIG_RE.findall(text))
        ids = [int(x) for x in BEFORE_RE.findall(page)]
        if too_old or not ids:
            break
        before = min(ids)
    print(f"[+] {channel}: {len(found)} raw configs")
    return found


def parse(cfg: str):
    """(کلید یکتا, host, port) برمی‌گرداند؛ None اگر خراب باشد."""
    proto = cfg.split("://", 1)[0]
    try:
        if proto == "vmess":
            raw = cfg[8:].split("#")[0]
            data = json.loads(base64.b64decode(raw + "=" * (-len(raw) % 4)).decode())
            host, port = str(data["add"]), int(data["port"])
            key = ("vmess", host, port, data.get("id"), data.get("net"), data.get("path"), data.get("host"))
            return key, host, port
        u = urllib.parse.urlsplit(cfg.split("#")[0])
        host, port = u.hostname, u.port
        if not host or not port:
            return None
        q = urllib.parse.parse_qs(u.query)
        sig = tuple(q.get(k, [""])[0] for k in ("type", "sni", "host", "path", "serviceName", "security"))
        key = (proto, host.lower(), port, urllib.parse.unquote(u.username or "")) + sig
        return key, host, port
    except Exception:
        return None


def tcp_ok(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=TCP_TIMEOUT):
            return True
    except Exception:
        return False


def rename(cfg: str, name: str) -> str:
    if cfg.startswith("vmess://"):
        raw = cfg[8:].split("#")[0]
        data = json.loads(base64.b64decode(raw + "=" * (-len(raw) % 4)).decode())
        data["ps"] = name
        return "vmess://" + base64.b64encode(json.dumps(data, ensure_ascii=False).encode()).decode()
    return cfg.split("#")[0] + "#" + urllib.parse.quote(name)


def main():
    cutoff = datetime.now(timezone.utc) - timedelta(hours=MAX_AGE_HOURS)
    raw = []
    for ch in CHANNELS:
        raw.extend(scrape_channel(ch, cutoff))

    # حذف تکراری‌ها (جدیدترین‌ها اول)
    seen, unique = set(), []
    for cfg in reversed(raw):
        p = parse(cfg)
        if not p or p[0] in seen:
            continue
        seen.add(p[0])
        unique.append((cfg, p[1], p[2]))
    print(f"[+] unique: {len(unique)}")

    if TCP_CHECK and unique:
        with ThreadPoolExecutor(max_workers=50) as ex:
            alive = list(ex.map(lambda x: tcp_ok(x[1], x[2]), unique))
        unique = [u for u, ok in zip(unique, alive) if ok]
        print(f"[+] reachable (TCP): {len(unique)}")

    out = []
    for i, (cfg, _, _) in enumerate(unique, 1):
        proto = cfg.split("://", 1)[0]
        try:
            out.append(rename(cfg, f"{REMARK_PREFIX}-{i:03d}-{proto}"))
        except Exception:
            out.append(cfg)

    if not out:
        print("[!] هیچ کانفیگی پیدا نشد؛ فایل‌های قبلی دست نخورد.")
        return

    plain = "\n".join(out) + "\n"
    with open("sub_plain.txt", "w", encoding="utf-8") as f:
        f.write(plain)
    with open("sub.txt", "w", encoding="utf-8") as f:
        f.write(base64.b64encode(plain.encode()).decode())
    print(f"[✓] {len(out)} configs written")


if __name__ == "__main__":
    main()
