"""
knowledge_base.py — دانشِ کاملِ ربات (نقشه‌ی دقیقِ منوها/دکمه‌ها، تمام دستورات کلمه‌ای،
ابزارهای قابل‌اجرای دستیار به‌تفکیکِ نقش، و راهنمای گام‌به‌گامِ هر بخش) که به‌صورت خودکار
به system prompt دستیار هوشمند (ai_assistant.py) اضافه می‌شود.

منبع محتوا فایلِ AI_KNOWLEDGE_BASE.md در همین پوشه است — همان فایل هم برای مطالعه‌ی
انسانی (مستندسازی پروژه) خواناست و هم اینجا بدون تکرار، مستقیم لود و به دستیار داده می‌شود.
اگر جزئیاتِ منوها/کلمات/ابزارها در آینده عوض شد، فقط همان فایل مارک‌داون را ویرایش کن؛
نیازی به تغییرِ این ماژول یا ai_assistant.py نیست.
"""
import os
import functools

_KB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "AI_KNOWLEDGE_BASE.md")


@functools.lru_cache(maxsize=1)
def _load() -> str:
    try:
        with open(_KB_PATH, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def get_knowledge_base(role: str = "") -> str:
    """
    کل دانش‌نامه را برمی‌گرداند تا به system prompt دستیار اضافه شود.

    پارامتر role فعلاً استفاده نمی‌شود (سند برای هر سه نقش یک‌جا نوشته شده و خودش
    مشخص می‌کند کدام بخش برای کدام نقش است) — اما نگه داشته شده تا اگر بعداً خواستی
    برای کم‌کردنِ حجم توکن، نسخه‌ی فیلترشده به‌ازای هر نقش بسازی، بدون تغییر امضای
    تابع در ai_assistant.py این کار را انجام بدهی.
    """
    return _load()
