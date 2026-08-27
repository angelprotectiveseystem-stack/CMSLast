"""
ai_assistant.py — دستیار هوشمند متصل به Gemini API

معماری:
  - هر پیام پیشوا/مدیر (وقتی حالت «دستیار» فعاله) با تاریخچه‌ی کوتاه
    مکالمه برای Gemini فرستاده می‌شه.
  - به مدل فقط لیست ابزارهایی معرفی می‌شه که نقش همون کاربر اجازه‌ش رو
    داره (ai_tools.TOOL_PERMISSIONS).
  - اگه مدل تصمیم بگیره یه تابع صدا بزنه، ai_tools.dispatch() اجرا و
    دوباره چک دسترسی می‌کنه (خط دفاعی دوم — نه فقط اعتماد به مدل).
  - برای گفت‌وگوی عادی (تحلیل، درددل، گزارش با کلمات خودش) مدل مستقیم
    متن برمی‌گردونه، بدون صدازدن تابعی.
"""
import os
import json
import logging

import httpx
from telegram import Update
from telegram.ext import ContextTypes

import database as db
from helpers import get_user_role
from config import ROLE_PISHVA, ROLE_TOURNAMENT_MANAGER, ROLE_SECURITY_MANAGER
import ai_tools

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

MAX_HISTORY_TURNS = 8          # چند رفت‌وبرگشت آخر رو نگه داریم (برای هزینه/سرعت)
MAX_TOOL_HOPS = 3              # جلوگیری از حلقه‌ی بی‌نهایت اگر مدل پشت‌سرهم تابع صدا بزنه

ROLE_LABELS = {
    ROLE_PISHVA: "پیشوا (بالاترین سطح دسترسی)",
    ROLE_TOURNAMENT_MANAGER: "مدیر مسابقات",
    ROLE_SECURITY_MANAGER: "مدیر امنیتی",
}

ACTIVATE_WORDS = {"دستیار", "دستیار هوشمند", "🤖 دستیار هوشمند"}
DEACTIVATE_WORDS = {"خروج از دستیار", "بستن دستیار", "بسه"}


def _system_prompt(role: str) -> str:
    role_label = ROLE_LABELS.get(role, role)
    allowed = [n for n, roles in ai_tools.TOOL_PERMISSIONS.items() if role in roles]
    return (
        "تو دستیار هوشمند داخلی یک ربات مدیریت مدرسه/آکادمی شطرنج هستی، به فارسی محاوره‌ای و "
        "گرم و دوستانه صحبت می‌کنی — مثل یه همکار باتجربه و قابل‌اعتماد، نه یه ربات رسمی. "
        "می‌تونی درددل بشنوی، تحلیل بدی، گزارش بسازی، و کارها رو با ابزارهایی که در اختیارت "
        "گذاشته شده مستقیم انجام بدی.\n\n"
        f"کاربر فعلی نقشش «{role_label}» است.\n\n"
        "قوانین مهم:\n"
        "- فقط وقتی کاربر صراحتاً یه کار اجرایی خواست (ثبت، حذف، اخطار، شروع/پایان ساعت کاری، "
        "ارسال بیانیه، ثبت نتیجه‌ی مسابقه و مانند آن) از ابزارها استفاده کن.\n"
        "- اگه اطلاعات لازم برای اجرای یه تابع (مثل نام دقیق بازیکن) کامل نبود، بپرس، حدس نزن.\n"
        "- اگه کاربر فقط سوال پرسید یا خواست تحلیل/گزارش/همفکری کنی، مستقیم با متن جواب بده، "
        "نیازی به تابع نیست.\n"
        "- اگه یه کاری بیرون از اختیارات نقش کاربره، رک و مودبانه بگو که این کار خارج از دسترسی "
        "نقش اونه — تلاش نکن دور بزنی.\n"
        "- جواب‌ها کوتاه و مفید باشن، مناسب صفحه‌ی موبایل."
    )


def _tools_for_role(role: str):
    decls = [d for d in ai_tools.TOOL_DECLARATIONS if role in ai_tools.TOOL_PERMISSIONS.get(d["name"], [])]
    if not decls:
        return None
    return [{"function_declarations": decls}]


async def _call_gemini(contents: list, tools):
    payload = {"contents": contents}
    if tools:
        payload["tools"] = tools
    headers = {"Content-Type": "application/json", "x-goog-api-key": GEMINI_API_KEY}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(GEMINI_URL, headers=headers, json=payload)
        resp.raise_for_status()
        return resp.json()


def _extract_parts(data: dict):
    try:
        return data["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError):
        return []


async def ai_assistant_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    text = update.message.text.strip()
    uid = update.effective_user.id

    role = await get_user_role(uid)
    if not role:
        return  # نه پیشواست نه مدیر فعال — کاری نداریم

    # فعال/غیرفعال‌کردن حالت دستیار
    if text in ACTIVATE_WORDS:
        ctx.user_data["ai_mode"] = True
        ctx.user_data["ai_history"] = []
        await update.message.reply_text(
            "🤖 دستیار هوشمند فعال شد. هرچی بخوای بگو — می‌تونم کارهات رو انجام بدم، "
            "گزارش بدم یا فقط باهات حرف بزنم.\nبرای خروج بنویس «خروج از دستیار»."
        )
        return

    if not ctx.user_data.get("ai_mode"):
        return  # حالت دستیار فعال نیست — به بقیه‌ی هندلرها بسپار

    if text in DEACTIVATE_WORDS:
        ctx.user_data["ai_mode"] = False
        ctx.user_data.pop("ai_history", None)
        await update.message.reply_text("👋 از حالت دستیار خارج شدی.")
        return

    if not GEMINI_API_KEY:
        await update.message.reply_text("⚠️ کلید Gemini تنظیم نشده (GEMINI_API_KEY خالیه).")
        return

    history = ctx.user_data.setdefault("ai_history", [])
    history.append({"role": "user", "parts": [{"text": text}]})

    system_prompt = _system_prompt(role)
    contents = [{"role": "user", "parts": [{"text": system_prompt}]},
                {"role": "model", "parts": [{"text": "باشه، آماده‌ام کمک کنم."}]}] + history

    tools = _tools_for_role(role)

    await update.message.chat.send_action("typing")

    try:
        for _hop in range(MAX_TOOL_HOPS):
            data = await _call_gemini(contents, tools)
            parts = _extract_parts(data)
            if not parts:
                await update.message.reply_text("⚠️ پاسخی از مدل دریافت نشد، دوباره امتحان کن.")
                return

            fn_call = next((p["functionCall"] for p in parts if "functionCall" in p), None)

            if fn_call:
                fname = fn_call["name"]
                fargs = fn_call.get("args", {})
                result_text = await ai_tools.dispatch(fname, fargs, uid, role, ctx)

                contents.append({"role": "model", "parts": [{"functionCall": fn_call}]})
                contents.append({
                    "role": "user",
                    "parts": [{"functionResponse": {"name": fname, "response": {"result": result_text}}}],
                })
                continue  # یه دور دیگه بزن تا مدل جواب نهایی رو بر اساس نتیجه بسازه

            # پاسخ متنی نهایی
            reply_text = "".join(p.get("text", "") for p in parts).strip() or "باشه."
            history.append({"role": "model", "parts": [{"text": reply_text}]})
            ctx.user_data["ai_history"] = history[-(MAX_HISTORY_TURNS * 2):]
            await update.message.reply_text(reply_text)
            return

        await update.message.reply_text("⚠️ این درخواست خیلی پیچیده شد؛ لطفاً واضح‌تر یا مرحله‌به‌مرحله بگو.")

    except httpx.HTTPStatusError as e:
        logger.error(f"Gemini API error: {e.response.text}")
        await update.message.reply_text("⚠️ ارتباط با هوش مصنوعی موقتاً مشکل داشت، چند لحظه دیگه امتحان کن.")
    except Exception:
        logger.exception("AI assistant failed")
        await update.message.reply_text("⚠️ یه خطای غیرمنتظره پیش اومد.")
