#!/usr/bin/env python3
"""
تست کانفیگ‌ها روی اینترنت خود گوشی (Termux) و کپی بهترین‌ها در کلیپ‌بورد.

مراحل:
  1. دریافت pool.txt از GitHub (اگر نشد، از نسخه‌ی ذخیره‌شده‌ی قبلی)
  2. درخواست خاموش کردن VPN
  3. تست واقعی همه‌ی کانفیگ‌ها با xray-knife
  4. مرتب‌سازی و کپی بهترین‌ها در کلیپ‌بورد -> در v2rayNG: Import from clipboard
"""

import base64
import csv
import json
import os
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request

REPO = os.getenv("V2T_REPO", "ali111e111n/myv2rayimporter")
POOL_URLS = [
    f"https://raw.githubusercontent.com/{REPO}/main/pool.txt",
    f"https://cdn.jsdelivr.net/gh/{REPO}@main/pool.txt",
    f"https://fastly.jsdelivr.net/gh/{REPO}@main/pool.txt",
]
KEEP = int(os.getenv("V2T_KEEP", "15"))            # چند کانفیگ برتر کپی شود
MAX_DELAY = int(os.getenv("V2T_MAX_DELAY", "3000"))
THREADS = os.getenv("V2T_THREADS", "30")
ASK_VPN = os.getenv("V2T_ASK_VPN", "1") == "1"     # اگر Termux را از VPN مستثنا کرده‌اید: 0
WORK = os.path.expanduser("~/.v2test")
KNIFE = shutil.which("xray-knife") or os.path.join(os.getenv("PREFIX", "/usr"), "bin", "xray-knife")

G, Y, R, B, N = "\033[32m", "\033[33m", "\033[31m", "\033[1m", "\033[0m"


def say(msg, color=""):
    print(f"{color}{msg}{N}", flush=True)


def download_pool() -> list[str]:
    cache = os.path.join(WORK, "pool.txt")
    for url in POOL_URLS:
        try:
            req = urllib.request.Request(url, headers={"Cache-Control": "no-cache"})
            with urllib.request.urlopen(req, timeout=15) as r:
                text = r.read().decode("utf-8", "replace")
            links = [l.strip() for l in text.splitlines() if "://" in l]
            if links:
                with open(cache, "w", encoding="utf-8") as f:
                    f.write("\n".join(links) + "\n")
                say(f"✓ لیست جدید دریافت شد ({len(links)} کانفیگ)", G)
                return links
        except Exception:
            continue
    if os.path.isfile(cache):
        links = [l.strip() for l in open(cache, encoding="utf-8") if "://" in l]
        say(f"! دریافت لیست جدید ممکن نشد؛ از لیست قبلی استفاده می‌شود ({len(links)} کانفیگ)", Y)
        say("  (برای لیست جدید: VPN را روشن کنید و دوباره اجرا کنید)", Y)
        return links
    return []


def rename(cfg: str, name: str) -> str:
    if cfg.startswith("vmess://"):
        raw = cfg[8:].split("#")[0]
        data = json.loads(base64.b64decode(raw + "=" * (-len(raw) % 4)).decode())
        data["ps"] = name
        return "vmess://" + base64.b64encode(json.dumps(data, ensure_ascii=False).encode()).decode()
    return cfg.split("#")[0] + "#" + urllib.parse.quote(name)


def test(links: list[str]):
    src = os.path.join(WORK, "candidates.txt")
    out = os.path.join(WORK, "results.csv")
    with open(src, "w", encoding="utf-8") as f:
        f.write("\n".join(links) + "\n")
    if os.path.exists(out):
        os.remove(out)
    cmd = [KNIFE, "http", "-f", src, "-o", out, "-x", "csv", "-t", THREADS,
           "-d", str(MAX_DELAY), "--prescan", "--diagnose=false"]
    subprocess.run(cmd, check=False)
    rows = []
    if not os.path.isfile(out):
        return rows
    allowed = set(links)
    with open(out, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r.get("link") not in allowed or r.get("status") not in ("passed", "semi-passed"):
                continue
            try:
                d = int(float(r.get("delay") or -1))
            except ValueError:
                continue
            if 0 < d <= MAX_DELAY:
                loc = (r.get("location") or "").strip().upper()
                rows.append((r["link"], d, loc if len(loc) == 2 and loc.isalpha() else ""))
    rows.sort(key=lambda x: x[1])
    return rows


def to_clipboard(text: str) -> bool:
    try:
        subprocess.run(["termux-clipboard-set"], input=text.encode(), check=True, timeout=15)
        return True
    except Exception:
        return False


def notify(msg: str):
    try:
        subprocess.run(["termux-toast", msg], timeout=10)
    except Exception:
        pass


def main():
    os.makedirs(WORK, exist_ok=True)
    if not os.path.isfile(KNIFE):
        say("✗ xray-knife نصب نیست. اسکریپت نصب را دوباره اجرا کنید.", R)
        return 1

    say(f"{B}── ۱/۳  دریافت لیست ──{N}")
    links = download_pool()
    if not links:
        say("✗ هیچ لیستی در دسترس نیست. VPN را روشن کنید و دوباره اجرا کنید.", R)
        return 1

    if ASK_VPN:
        say(f"\n{B}── ۲/۳  VPN را خاموش کنید ──{N}")
        say("تست باید روی اینترنت خودتان انجام شود، نه از داخل VPN.", Y)
        try:
            input("وقتی VPN خاموش شد، Enter بزنید... ")
        except EOFError:
            pass

    say(f"\n{B}── ۳/۳  تست {len(links)} کانفیگ (حدود ۱ دقیقه) ──{N}")
    rows = test(links)
    if not rows:
        say("✗ هیچ کانفیگی روی اینترنت شما وصل نشد.", R)
        say("  مطمئن شوید VPN خاموش است، یا چند ساعت بعد دوباره امتحان کنید.", Y)
        notify("هیچ کانفیگی وصل نشد")
        return 1

    best = rows[:KEEP]
    out, names = [], []
    for i, (cfg, d, loc) in enumerate(best, 1):
        proto = cfg.split("://", 1)[0]
        name = "-".join(p for p in (f"ok{i:02d}", proto, loc, f"{d}ms") if p)
        names.append(name)
        try:
            out.append(rename(cfg, name))
        except Exception:
            out.append(cfg)

    say(f"\n{G}✓ {len(rows)} کانفیگ روی اینترنت شما وصل شد. {len(best)} تای برتر:{N}")
    for name in names:
        say("   " + name)

    with open(os.path.join(WORK, "best.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")

    if to_clipboard("\n".join(out)):
        say(f"\n{G}{B}✓ در کلیپ‌بورد کپی شد.{N}")
        say("در v2rayNG:  ➕  ←  Import config from Clipboard")
        notify(f"{len(best)} کانفیگ سالم کپی شد")
    else:
        say(f"\n{Y}! کپی در کلیپ‌بورد نشد (اپ Termux:API نصب است؟)", Y)
        say(f"  فایل نتیجه: {os.path.join(WORK, 'best.txt')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
