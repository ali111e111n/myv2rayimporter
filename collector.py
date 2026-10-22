#!/usr/bin/env python3
"""
جمع‌آوری کانفیگ‌های V2Ray از کانال(های) عمومی تلگرام و ساخت لینک Subscription.

خروجی:
  sub.txt        -> نسخه base64 (برای v2rayNG / Hiddify / NekoBox)
  sub_plain.txt  -> همان لیست به‌صورت متن ساده (هر خط یک کانفیگ)
"""

import base64
import csv
import html
import json
import os
import re
import socket
import subprocess
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
REAL_TEST = os.getenv("REAL_TEST", "1") == "1"          # تست واقعی با xray-knife
XRAY_KNIFE = os.getenv("XRAY_KNIFE", "./xray-knife")
MAX_DELAY = int(os.getenv("MAX_DELAY", "3000"))         # کانفیگ‌های کندتر از این (ms) حذف
MAX_CONFIGS = int(os.getenv("MAX_CONFIGS", "30"))       # فقط این تعداد از بهترین‌ها
KEEP_IR_HOSTS = os.getenv("KEEP_IR_HOSTS", "1") == "1"  # نگه‌داشتن سرورهای .ir که از خارج تست‌پذیر نیستند
MAX_IR = int(os.getenv("MAX_IR", "10"))

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


def real_test(configs: list[str]):
    """هر کانفیگ را واقعاً وصل می‌کند و یک درخواست HTTP از داخلش می‌فرستد.
    خروجی: [(cfg, delay_ms, location)] مرتب از سریع به کند، یا None اگر ابزار در دسترس نبود."""
    if not os.path.isfile(XRAY_KNIFE):
        print(f"[!] {XRAY_KNIFE} not found; falling back to TCP check", file=sys.stderr)
        return None
    with open("candidates.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(configs) + "\n")
    cmd = [XRAY_KNIFE, "http", "-f", "candidates.txt", "-o", "results.csv", "-x", "csv",
           "-t", "50", "-d", str(MAX_DELAY), "--prescan", "--quiet"]
    try:
        # کد خروج 3 یعنی «هیچ کانفیگی رد نشد» و خطا نیست
        subprocess.run(cmd, timeout=1500, check=False)
    except subprocess.TimeoutExpired:
        print("[!] real test timed out", file=sys.stderr)
    if not os.path.isfile("results.csv"):
        return None

    allowed = set(configs)
    rows = []
    with open("results.csv", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            link = r.get("link", "")
            if link not in allowed or r.get("status") not in ("passed", "semi-passed"):
                continue
            try:
                delay = int(float(r.get("delay") or -1))
            except ValueError:
                continue
            if 0 < delay <= MAX_DELAY:
                loc = (r.get("location") or "").strip()
                loc = loc if re.fullmatch(r"[A-Za-z]{2}", loc) else None
                rows.append((link, delay, loc.upper() if loc else None))
    rows.sort(key=lambda x: x[1])
    return rows


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

    # ---- تست واقعی (اتصال کامل از داخل تونل) ----
    tested = real_test([u[0] for u in unique]) if REAL_TEST and unique else None

    if tested == []:
        print("[!] هیچ کانفیگی تست را رد نکرد؛ لیست قبلی دست نخورد.")
        return

    if tested is not None:
        # tested: لیست (cfg, delay_ms, location) مرتب‌شده از سریع به کند
        print(f"[+] passed real test: {len(tested)}")
        final = tested[:MAX_CONFIGS]
        if KEEP_IR_HOSTS:
            # سرورهای داخلی (.ir) معمولاً از خارج ایران جواب نمی‌دهند ولی در ایران کار می‌کنند
            passed = {t[0] for t in tested}
            ir = [(u[0], None, "IR") for u in unique
                  if u[0] not in passed and u[1].lower().endswith(".ir")]
            final += ir[:MAX_IR]
            print(f"[+] kept untested .ir relays: {len(ir[:MAX_IR])}")
    else:
        if TCP_CHECK and unique:
            with ThreadPoolExecutor(max_workers=50) as ex:
                alive = list(ex.map(lambda x: tcp_ok(x[1], x[2]), unique))
            unique = [u for u, ok in zip(unique, alive) if ok]
            print(f"[+] reachable (TCP): {len(unique)}")
        final = [(u[0], None, None) for u in unique[:MAX_CONFIGS]]

    out = []
    for i, (cfg, delay, loc) in enumerate(final, 1):
        proto = cfg.split("://", 1)[0]
        parts = [f"{i:02d}", proto]
        if loc:
            parts.append(loc)
        if delay:
            parts.append(f"{delay}ms")
        try:
            out.append(rename(cfg, f"{REMARK_PREFIX}-" + "-".join(parts)))
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
