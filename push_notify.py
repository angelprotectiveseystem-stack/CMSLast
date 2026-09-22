"""
push_notify.py — ارسالِ اعلان به گوشیِ مدیر مدرسه (Web Push / VAPID).

مسیرِ کار:
  ۱) مرورگرِ مدیر مدرسه بعد از گرفتنِ اجازه، یک «اشتراک» می‌سازه و به
     /api/principal/push/subscribe می‌فرسته (ذخیره در principal_push_subscriptions).
  ۲) وقتی ادمین از «پنل ادمین ← ارسال اعلان» اعلانِ تازه‌ای می‌فرسته،
     broadcast() اون رو برای همه‌ی اشتراک‌ها می‌فرسته.
  ۳) service worker (webapp_principal/sw.js) پوش رو می‌گیره و روی گوشی نشون می‌ده.

کلیدهای VAPID: اگه VAPID_PUBLIC_KEY و VAPID_PRIVATE_KEY توی env بذاری همون‌ها
استفاده می‌شن؛ وگرنه اولین باری که لازم بشن خودکار ساخته و توی جدولِ
push_config (دیتابیس) ذخیره می‌شن، پس نیازی به تنظیمِ دستی نیست. (اگه کلیدها
عوض بشن، اشتراک‌های قبلی معتبر نیستن؛ مرورگر دفعه‌ی بعد که پنل رو باز کنه
خودش دوباره مشترک می‌شه.)

وابستگی: pywebpush (توی requirements.txt). اگه نصب نباشه، ربات و پنل‌ها
بدونِ خطا کار می‌کنن و فقط ارسالِ پوش غیرفعاله (is_available() → False)؛ اعلان
همچنان توی پنل مدیر مدرسه ثبت و دیده می‌شه.
"""

import asyncio
import base64
import json
import logging
import os

import database as db

logger = logging.getLogger(__name__)

_SEND_TIMEOUT = 10        # ثانیه، برای هر دستگاه
_MAX_PARALLEL = 5
_PAYLOAD_BODY_MAX = 180   # پیامِ پوش کوتاه‌شده‌ی متنه؛ متنِ کامل داخلِ پنل دیده می‌شه
_PAYLOAD_TITLE_MAX = 80

_keys_cache = None        # (private_b64url, public_b64url)
_lib_warned = False


def is_available() -> bool:
    global _lib_warned
    try:
        import pywebpush  # noqa: F401
        return True
    except Exception:
        if not _lib_warned:
            _lib_warned = True
            logger.warning("pywebpush is not installed — push delivery is disabled "
                           "(pip install pywebpush). Notifications still show inside the panel.")
        return False


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _generate_vapid_pair():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    key = ec.generate_private_key(ec.SECP256R1())
    private_raw = key.private_numbers().private_value.to_bytes(32, "big")
    public_raw = key.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    return _b64url(private_raw), _b64url(public_raw)


async def get_vapid_keys():
    """(private, public) به‌صورت base64url. اولین بار در صورتِ نبودنِ کلید می‌سازه."""
    global _keys_cache
    if _keys_cache:
        return _keys_cache

    env_priv = os.environ.get("VAPID_PRIVATE_KEY", "").strip()
    env_pub = os.environ.get("VAPID_PUBLIC_KEY", "").strip()
    if env_priv and env_pub:
        _keys_cache = (env_priv, env_pub)
        return _keys_cache

    priv = await db.get_push_config("vapid_private")
    pub = await db.get_push_config("vapid_public")
    if not (priv and pub):
        new_priv, new_pub = _generate_vapid_pair()
        await db.set_push_config_if_absent("vapid_private", new_priv)
        await db.set_push_config_if_absent("vapid_public", new_pub)
        # اگه هم‌زمان دو درخواست کلید ساختن، همونی که واقعاً ذخیره شد برنده‌ست.
        priv = await db.get_push_config("vapid_private")
        pub = await db.get_push_config("vapid_public")
    _keys_cache = (priv, pub)
    return _keys_cache


async def get_public_key() -> str:
    return (await get_vapid_keys())[1]


def subject_for(request) -> str:
    """claim «sub» در VAPID: باید mailto: یا آدرسِ https باشه. اگه VAPID_SUBJECT
    توی env نبود، از دامنه‌ی خودِ سرویس (پشتِ پراکسی) ساخته می‌شه."""
    env = os.environ.get("VAPID_SUBJECT", "").strip()
    if env:
        return env
    host = (request.headers.get("X-Forwarded-Host") or request.host or "").split(",")[0].strip()
    if host and not host.startswith(("localhost", "127.", "0.0.0.0")):
        return f"https://{host}"
    return "mailto:admin@example.com"


def _shorten(text: str, limit: int) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _send_one(sub: dict, payload: str, private_key: str, subject: str) -> str:
    """در یک thread اجرا می‌شه (pywebpush همگامه). نتیجه: ok | gone | failed"""
    from pywebpush import WebPushException, webpush

    try:
        webpush(
            subscription_info={
                "endpoint": sub["endpoint"],
                "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]},
            },
            data=payload,
            vapid_private_key=private_key,
            vapid_claims={"sub": subject},   # pywebpush این دیکشنری رو تغییر می‌ده؛ هر بار تازه
            ttl=86400,
            timeout=_SEND_TIMEOUT,
            headers={"Urgency": "high"},
        )
        return "ok"
    except WebPushException as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        if status in (404, 410):
            return "gone"          # اشتراک منقضی/لغو شده
        logger.warning("Web push failed (status=%s): %s", status, exc)
        return "failed"
    except Exception:
        logger.exception("Web push crashed for one subscription")
        return "failed"


async def broadcast(notif_id: int, title: str, body: str, subject: str) -> dict:
    """اعلان رو برای همه‌ی دستگاه‌های مشترک می‌فرسته و خلاصه‌ی نتیجه رو برمی‌گردونه.
    هیچ‌وقت استثنا پرت نمی‌کنه — شکستِ پوش نباید ثبتِ خودِ اعلان رو خراب کنه."""
    result = {"available": False, "total": 0, "sent": 0, "failed": 0, "removed": 0, "skipped": None}
    try:
        if not is_available():
            return result
        result["available"] = True

        # اگه مدیر ارشد پنل مدیر مدرسه رو خاموش کرده، محتوا نباید روی گوشی‌ها برسه.
        if (await db.get_setting("principal_panel_enabled", "1")) != "1":
            result["skipped"] = "panel_disabled"
            return result

        rows = await db.get_push_subscriptions()
        subs = []
        for row in rows or []:
            sub = dict(row)
            # دستگاهِ بلاک‌شده، حتی اگه قبلاً مشترک شده بود، نباید چیزی بگیره.
            if sub.get("device_id") and await db.is_principal_device_blocked(sub["device_id"]):
                continue
            subs.append(sub)
        result["total"] = len(subs)
        if not subs:
            return result

        private_key, _ = await get_vapid_keys()
        sem = asyncio.Semaphore(_MAX_PARALLEL)

        async def _one(sub):
            payload = json.dumps({
                "id": notif_id,
                "title": _shorten(title, _PAYLOAD_TITLE_MAX),
                "body": _shorten(body, _PAYLOAD_BODY_MAX),
                "url": (sub.get("open_url") or "/principal").split("#")[0] + "#notifications",
            }, ensure_ascii=False)
            async with sem:
                return sub, await asyncio.to_thread(_send_one, sub, payload, private_key, subject)

        for sub, status in await asyncio.gather(*[_one(s) for s in subs]):
            if status == "ok":
                result["sent"] += 1
            elif status == "gone":
                result["removed"] += 1
                await db.delete_push_subscription(sub["endpoint"])
            else:
                result["failed"] += 1
    except Exception:
        logger.exception("push broadcast failed")
    return result
