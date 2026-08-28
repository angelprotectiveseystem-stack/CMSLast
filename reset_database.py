"""
اسکریپت ریست کامل دیتابیس Turso.
همه‌ی داده‌های داخل جدول‌ها پاک می‌شه، ولی خودِ جدول‌ها (schema) و اتصال
(TURSO_URL / TURSO_AUTH_TOKEN) دست‌نخورده می‌مونه — یعنی بعد از اجرا نیازی
به init_db() یا هیچ ست‌آپ دیگه‌ای نیست، ربات همون‌طوری که هست بالا میاد
ولی با دیتابیس خالی.

طرز اجرا (یک‌بار، از همون جایی که TURSO_URL و TURSO_AUTH_TOKEN در دسترسه):
    python reset_database.py
    # ازت تایید می‌گیره، باید دقیقاً بنویسی: RESET

اگه روی Railway اجرا می‌کنی، این متغیرها از قبل توی Environment ست شدن، پس
کافیه از طریق Railway CLI یا یه Shell موقت این فایل رو اجرا کنی.
"""
import asyncio
import os
import sys

import turso_db as aiosqlite

TABLES = [
    "ai_chat_messages",
    "ai_chat_sessions",
    "blocked_users",
    "backups",
    "team_match_boards",
    "team_matches",
    "team_members",
    "teams",
    "access_requests",
    "action_logs",
    "feedback",
    "tasks",
    "news",
    "announcements",
    "messages",
    "warnings_log",
    "matches",
    "tournaments",
    "players",
    "classes",
    "admins",
    "system_settings",
]


async def reset_all():
    if not os.getenv("TURSO_URL") or not os.getenv("TURSO_AUTH_TOKEN"):
        print("❌ TURSO_URL و TURSO_AUTH_TOKEN ست نشدن. این اسکریپت باید همون‌جایی اجرا "
              "بشه که ربات این متغیرها رو داره (مثلاً Railway).")
        sys.exit(1)

    async with aiosqlite.connect("") as db:
        for table in TABLES:
            try:
                await db.execute(f"DELETE FROM {table}")
                print(f"✅ خالی شد: {table}")
            except Exception as e:
                print(f"⚠️ رد شد ({table}): {e}")

        # ریست کردن شمارنده‌ی AUTOINCREMENT (اگه جدول sqlite_sequence وجود داشته باشه)
        try:
            await db.execute("DELETE FROM sqlite_sequence")
            print("✅ شمارنده‌های autoincrement ریست شدن.")
        except Exception:
            pass  # ممکنه اصلاً این جدول وجود نداشته باشه، مشکلی نیست

        await db.commit()

    print("\n🎉 دیتابیس کاملاً خالی شد. جدول‌ها و اتصال دست‌نخورده موندن.")


if __name__ == "__main__":
    print("⚠️  این کار همه‌ی داده‌های دیتابیس (ادمین‌ها، بازیکنان، مسابقات، لاگ‌ها، همه‌چیز) رو "
          "برای همیشه پاک می‌کنه. این عمل قابل بازگشت نیست.")
    confirm = input("برای تایید، دقیقاً بنویس RESET و اینتر بزن: ")
    if confirm.strip() != "RESET":
        print("لغو شد.")
        sys.exit(0)
    asyncio.run(reset_all())
