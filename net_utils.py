"""
net_utils.py — تنظیمات مشترک شبکه برای درخواست‌های خروجی (فعلاً: Gemini).

علتِ وجودش (تشخیصِ کندیِ کلیِ هوش‌مصنوعی‌ها — چت شطرنج زنده، دستیار ربات،
دستیار پنل مدیر مدرسه — که با وجودِ کش‌کردنِ کامل دیتابیس همچنان تا ~۱ دقیقه
طول می‌کشید):

۱) IPv4-only DNS: زیرساختِ خروجیِ Railway گاهی مسیرِ IPv6 را «blackhole»
   می‌کند — یعنی بسته فرستاده می‌شود ولی هیچ پاسخ/ردی نمی‌آید. وقتی
   socket.getaddrinfo برای دامنه‌ای (مثل generativelanguage.googleapis.com)
   یک رکوردِ IPv6 برمی‌گرداند و httpx/asyncio همان را اول امتحان می‌کند،
   اتصال تا رسیدنِ کاملِ به timeout (۲۰ تا ۴۵ ثانیه، دقیقاً همان چیزی که
   در ai_assistant.py/principal_panel.py تنظیم شده) معلق می‌ماند — و چون
   اینجا هیچ Happy-Eyeballsی بینِ IPv4/IPv6 فعال نیست، تا شکستِ کاملِ
   IPv6 اصلاً سراغِ IPv4 نمی‌رود. راه‌حل: نتایجِ DNS را همیشه به فقط
   IPv4 محدود می‌کنیم تا این مسیر اصلاً امتحان نشود.

۲) کلاینتِ httpx مشترک و ماندگار برای Gemini: قبلاً ai_assistant.py و
   principal_panel.py هرکدام برای *هر تک درخواست* یک httpx.AsyncClient
   تازه می‌ساختند (async with httpx.AsyncClient(...) داخلِ خودِ تابعِ
   فراخوانی) — یعنی هر پیام یک DNS lookup + دست‌دادنِ TCP + هندشیکِ TLS
   کاملاً از صفر، دقیقاً برخلافِ turso_db.py که از اول یک کلاینتِ
   singleton با keep-alive داشت. الان همان الگو برای Gemini هم پیاده
   شده: یک کلاینتِ مشترک که بینِ درخواست‌های پیاپی اتصال را نگه می‌دارد.
"""

import logging
import socket

import httpx

logger = logging.getLogger("net_utils")


# ─── (۱) اجبار DNS به IPv4 ──────────────────────────────────────────
_orig_getaddrinfo = socket.getaddrinfo


def _ipv4_only_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    """اگه صدازننده روی خانواده‌ی خاصی (مثلاً AF_INET6) اصرار نداشته،
    نتایجِ IPv6 رو حذف می‌کنیم تا مسیرِ خروجیِ بالقوه‌بلک‌هول‌شده اصلاً
    امتحان نشه. اگه برای اون دامنه اصلاً رکوردِ IPv4 نبود (نادر)، همون
    نتیجه‌ی اصلی (شاملِ IPv6) رو برمی‌گردونیم تا چیزی نشکنه."""
    results = _orig_getaddrinfo(host, port, family, type, proto, flags)
    if family == 0:
        ipv4_only = [r for r in results if r[0] == socket.AF_INET]
        if ipv4_only:
            return ipv4_only
    return results


def force_ipv4_dns():
    """باید همون اولِ استارتِ برنامه (قبل از هر اتصالِ خروجی‌ای) صدا زده
    بشه. idempotent است — صدازدنِ دوباره‌ش مشکلی ایجاد نمی‌کنه."""
    if socket.getaddrinfo is not _ipv4_only_getaddrinfo:
        socket.getaddrinfo = _ipv4_only_getaddrinfo
        logger.info("net_utils: DNS resolution restricted to IPv4")


force_ipv4_dns()


# ─── (۲) کلاینتِ مشترکِ Gemini ──────────────────────────────────────
_gemini_client: httpx.AsyncClient | None = None


def get_gemini_client() -> httpx.AsyncClient:
    """یک httpx.AsyncClient مشترک و ماندگار برمی‌گردونه (اولین بار می‌سازدش،
    بعدش همون رو reuse می‌کنه). timeout اینجا تنظیم نمی‌شه چون هر صدازننده
    (ai_assistant.py با ۴۵ ثانیه، principal_panel.py با ۲۰ ثانیه) مقدارِ
    خودش رو موقعِ هر request جداگانه پاس می‌ده."""
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = httpx.AsyncClient(
            http2=True,
            limits=httpx.Limits(max_keepalive_connections=10, keepalive_expiry=30.0),
        )
    return _gemini_client
