# لینک Subscription خودکار از کانال تلگرام

هر ۲ ساعت کانفیگ‌های ۴۸ ساعت اخیر کانال `@meliproxyy` را جمع می‌کند، تکراری‌ها و سرورهای خاموش را حذف می‌کند و یک لینک Subscription ثابت می‌سازد.

## راه‌اندازی (یک‌بار، ۵ دقیقه)

1. در GitHub یک **ریپوی Public جدید** بسازید (مثلاً `my-sub`).
2. این فایل‌ها را آپلود کنید (با همان ساختار پوشه):
   - `collector.py`
   - `.github/workflows/update.yml`
3. تب **Actions** → اگر پرسید، Actions را فعال کنید.
4. **Update subscription** → **Run workflow** (اجرای اول دستی).
5. بعد از ۱ دقیقه فایل `sub.txt` در ریپو ساخته می‌شود.

## لینک Subscription

یکی از این دو را در اپ بگذارید (`USER` و `REPO` را عوض کنید):

```
https://raw.githubusercontent.com/USER/REPO/main/sub.txt
https://cdn.jsdelivr.net/gh/USER/REPO@main/sub.txt
```

اگر `raw.githubusercontent` باز نشد، از لینک jsDelivr استفاده کنید (کش آن تا ۱۲ ساعت است).

## استفاده روزانه

**v2rayNG:** منو ← Subscription group setting ← `+` ← لینک را بدهید. بعد:
- منو ← **Update subscription**
- منو ← **Test all configurations real delay**
- منو ← **Remove invalid configurations** (حذف مرده‌ها)
- منو ← **Sort by test results**

**Hiddify:** `+` ← لینک را بدهید ← حالت **Auto / Lowest ping** را انتخاب کنید. خودش بهترین را انتخاب و جابه‌جا می‌کند.

## تنظیمات

در `update.yml`:
| متغیر | پیش‌فرض | توضیح |
|---|---|---|
| `CHANNELS` | `meliproxyy` | چند کانال با کاما |
| `MAX_AGE_HOURS` | `48` | فقط پست‌های این چند ساعت |
| `TCP_CHECK` | `1` | حذف سرورهایی که پورتشان بسته است |

زمان‌بندی: خط `cron` (پیش‌فرض هر ۲ ساعت).

## نکته‌ها
- تست TCP روی سرور GitHub (خارج از ایران) انجام می‌شود؛ فقط سرورهای کاملاً خاموش را حذف می‌کند. تست واقعی را باید اپ روی گوشی انجام دهد.
- ریپو Public است؛ لینک را جایی پخش نکنید.
- کانفیگ رایگان = سرور ناشناس. برای کار حساس (بانک، ایمیل کاری) استفاده نکنید.
