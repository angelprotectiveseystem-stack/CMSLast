"""
اسکریپت ریست کامل دیتابیس Turso.
همه‌ی داده‌های داخل جدول‌ها پاک می‌شه، ولی خودِ جدول‌ها (schema) و اتصال
(TURSO_URL / TURSO_AUTH_TOKEN) دست‌نخورده می‌مونه — یعنی بعد از اجرا نیازی
به init_db() یا هیچ ست‌آپ دیگه‌ای نیست، ربات همون‌طوری که هست بالا میاد
ولی با دیتابیس خالی.

این نسخه برای اجرا از طریق Railway (بدون ترمینال/CLI، فقط با تغییر موقت
startCommand) طراحی شده — چون توی اون حالت ورودی تعاملی (input) امکان‌پذیر
نیست. به‌جاش، برای جلوگیری از اجرای تصادفی، باید متغیر محیطی زیر رو توی
Railway -> Variables ست کنی:

    RUN_RESET = YES

اگه این متغیر نباشه یا مقدارش YES نباشه، اسکریپت هیچ کاری نمی‌کنه و فقط
خطا می‌ده.
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
        print("❌ TURSO_URL و TURSO_AUTH_TOKEN ست نشدن.")
        sys.exit(1)

    async with aiosqlite.connect("") as db:
        for table in TABLES:
            try:
                await db.execute(f"DELETE FROM {table}")
                print(f"✅ خالی شد: {table}")
            except Exception as e:
                print(f"⚠️ رد شد ({table}): {e}")

        try:
            await db.execute("DELETE FROM sqlite_sequence")
            print("✅ شمارنده‌های autoincrement ریست شدن.")
        except Exception:
            pass

        await db.commit()

    print("\n🎉 دیتابیس کاملاً خالی شد. جدول‌ها و اتصال دست‌نخورده موندن.")


if __name__ == "__main__":
    confirmed = os.getenv("RUN_RESET", "") == "YES" or (len(sys.argv) > 1 and sys.argv[1] == "--confirm")
    if not confirmed:
        print("⚠️  برای اجرای واقعی، متغیر محیطی RUN_RESET=YES رو ست کن (یا --confirm بده).")
        print("این کار همه‌ی داده‌های دیتابیس رو برای همیشه پاک می‌کنه — قابل بازگشت نیست.")
        sys.exit(1)
    asyncio.run(reset_all())

