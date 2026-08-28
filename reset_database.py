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

from libsql_client import create_client

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


async def _count(client, table):
    try:
        res = await client.execute(f"SELECT COUNT(*) AS c FROM {table}")
        return res.rows[0][0]
    except Exception as e:
        return f"نامعلوم ({e})"


async def _delete_table(client, table):
    """اول یه DELETE FROM ساده امتحان می‌کنه. اگه به خاطر تعداد زیاد ردیف‌ها
    (مثلاً جدول players که واقعاً پر از داده‌ست، برخلاف بقیه‌ی جدول‌ها که خالی
    بودن) کلاینت Turso روی جواب سرور خطا داد، به‌جای تسلیم شدن، پاک‌کردن رو
    دسته‌دسته (batch) انجام می‌ده تا حتماً کامل خالی بشه."""
    try:
        await client.execute(f"DELETE FROM {table}")
        return True, None
    except Exception as first_err:
        # پاک‌کردن دسته‌ای، برای دور زدن باگ احتمالی توی پارس‌کردن جواب‌های حجیم
        try:
            for _ in range(500):  # سقف ایمنی؛ هر بار حداکثر ۵۰۰ ردیف
                await client.execute(f"DELETE FROM {table} WHERE rowid IN (SELECT rowid FROM {table} LIMIT 200)")
                remaining = await _count(client, table)
                if remaining == 0:
                    return True, None
                if isinstance(remaining, str):  # نتونستیم حتی شمارش کنیم، دیگه ادامه نده
                    break
            return False, first_err
        except Exception as batch_err:
            return False, batch_err


async def reset_all():
    url = os.getenv("TURSO_URL")
    token = os.getenv("TURSO_AUTH_TOKEN")
    if not url or not token:
        print("❌ TURSO_URL و TURSO_AUTH_TOKEN ست نشدن.")
        sys.exit(1)
    if url.startswith("libsql://"):
        url = "https://" + url[len("libsql://"):]

    client = create_client(url=url, auth_token=token)

    failures = []
    for table in TABLES:
        ok, err = await _delete_table(client, table)
        remaining = await _count(client, table)
        if remaining == 0:
            print(f"✅ خالی شد: {table} (ردیف باقی‌مانده: 0)")
        else:
            print(f"❌ هنوز خالی نیست: {table} (ردیف باقی‌مانده: {remaining}) — خطا: {err}")
            failures.append(table)

    try:
        await client.execute("DELETE FROM sqlite_sequence")
        print("✅ شمارنده‌های autoincrement ریست شدن.")
    except Exception:
        pass

    await client.close()

    if failures:
        print(f"\n⚠️ این جدول‌ها کامل خالی نشدن: {', '.join(failures)}")
    else:
        print("\n🎉 دیتابیس کاملاً خالی شد. جدول‌ها و اتصال دست‌نخورده موندن.")


if __name__ == "__main__":
    confirmed = os.getenv("RUN_RESET", "") == "YES" or (len(sys.argv) > 1 and sys.argv[1] == "--confirm")
    if not confirmed:
        print("⚠️  برای اجرای واقعی، متغیر محیطی RUN_RESET=YES رو ست کن (یا --confirm بده).")
        print("این کار همه‌ی داده‌های دیتابیس رو برای همیشه پاک می‌کنه — قابل بازگشت نیست.")
        sys.exit(1)
    asyncio.run(reset_all())

