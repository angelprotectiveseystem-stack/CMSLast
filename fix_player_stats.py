"""
اسکریپت یک‌باره‌ی اصلاح آمار بازیکنان.

باگ: دکمه‌ی «🗑️ حذف مسابقه» توی matches.py قبلاً db.delete_match() خام رو
صدا می‌زد که فقط ردیف مسابقه رو از جدول matches پاک می‌کرد، بدون اینکه اگه
اون مسابقه قبلاً نتیجه داشته، wins/losses/draws بازیکن‌های مربوطه رو کم کنه.
نتیجه: بعد از هر بار حذفِ یک مسابقه‌ی دارای نتیجه، شمارنده‌های روی جدول
players از تعداد واقعیِ مسابقاتِ باقی‌مانده در جدول matches جلو می‌افتاد.

این اسکریپت آمار wins/losses/draws همه‌ی بازیکنان رو مستقیماً از روی خودِ
جدول matches (که منبع حقیقتِ نهایی‌ه) از نو محاسبه و جایگزین می‌کنه. اجرای
دوباره‌ش هم بی‌خطره (idempotent) — اگه چیزی برای اصلاح نباشه، فقط می‌گه
هیچ‌کدوم تغییر نکردن.

اجرا:
    python fix_player_stats.py --confirm
یا با ست‌کردن متغیر محیطی:
    RUN_FIX=YES python fix_player_stats.py
"""
import asyncio
import os
import sys

import database as db


async def main():
    await db.init_db()  # اگه از قبل init نشده باشه (جدول‌ها رو می‌سازه، دیتای موجود رو دست نمی‌زنه)
    changed = await db.recalculate_all_player_stats()
    if changed == 0:
        print("✅ آمار wins/losses/draws از قبل درست بود.")
    else:
        print(f"🔧 آمار {changed} بازیکن اصلاح شد (wins/losses/draws از روی جدول matches بازسازی شد).")

    try:
        from elo import recalculate_all_elo, ensure_elo_table
        await ensure_elo_table()
        replayed = await recalculate_all_elo()
        print(f"🔧 Elo همه‌ی بازیکنان از نو ساخته شد (بر اساس {replayed} مسابقه‌ی دارای‌نتیجه).")
    except Exception as e:
        print(f"⚠️ بازسازی Elo با خطا مواجه شد: {e}")


if __name__ == "__main__":
    confirmed = os.getenv("RUN_FIX", "") == "YES" or (len(sys.argv) > 1 and sys.argv[1] == "--confirm")
    if not confirmed:
        print("⚠️  برای اجرای واقعی، متغیر محیطی RUN_FIX=YES رو ست کن (یا --confirm بده).")
        print("این اسکریپت فقط wins/losses/draws رو بازسازی می‌کنه؛ خودِ مسابقات یا بازیکنان حذف/تغییر نمی‌کنن.")
        sys.exit(1)
    asyncio.run(main())
