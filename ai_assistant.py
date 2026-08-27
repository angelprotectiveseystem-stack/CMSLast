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
import asyncio
import os
import json
import logging

import httpx
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import BadRequest

import database as db
from helpers import get_user_role
from config import ROLE_PISHVA, ROLE_TOURNAMENT_MANAGER, ROLE_SECURITY_MANAGER
import ai_tools

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")
# اگه مدل اصلی موقتاً شلوغ بود (خطای 503) یا از رده خارج شد (404)، این‌ها رو به‌ترتیب امتحان می‌کنیم
FALLBACK_MODELS = ["gemini-flash-latest", "gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.5-flash"]
if GEMINI_MODEL in FALLBACK_MODELS:
    FALLBACK_MODELS.remove(GEMINI_MODEL)
MODEL_CHAIN = [GEMINI_MODEL] + FALLBACK_MODELS

RETRIES_PER_MODEL = 2
RETRY_DELAY_SECONDS = 1

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
    payload = {
        "contents": contents,
        "generationConfig": {
            "thinkingConfig": {"thinkingBudget": 0}  # خاموش‌کردن «تفکر» برای سرعت بیشتر
        },
    }
    if tools:
        payload["tools"] = tools
    headers = {"Content-Type": "application/json", "x-goog-api-key": GEMINI_API_KEY}

    last_error = None
    async with httpx.AsyncClient(timeout=30) as client:
        for i, model in enumerate(MODEL_CHAIN):
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            is_last_model = (i == len(MODEL_CHAIN) - 1)
            for attempt in range(RETRIES_PER_MODEL):
                try:
                    resp = await client.post(url, headers=headers, json=payload)
                    resp.raise_for_status()
                    return resp.json()
                except httpx.HTTPStatusError as e:
                    last_error = e
                    code = e.response.status_code
                    if code in (503, 429):
                        # شلوغی موقت سرور یا محدودیت نرخ — همین مدل رو دوباره امتحان کن
                        logger.warning(f"Gemini {model} attempt {attempt+1} failed ({code}), retrying...")
                        await asyncio.sleep(RETRY_DELAY_SECONDS)
                        continue
                    elif code == 404 and not is_last_model:
                        # این مدل دیگه در دسترس نیست — برو سراغ مدل بعدی، تلاش دوباره روی همین بی‌فایده‌ست
                        logger.warning(f"Gemini model {model} not found (404), trying next model...")
                        break
                    else:
                        raise  # خطای دیگه (کلید نامعتبر و ...) یا آخرین مدل هم بود — دیگه فایده‌ای نداره
            # اگه به اینجا رسیدیم یعنی این مدل بعد از چند تلاش/یا 404 جواب نداد؛ برو مدل بعدی
    raise last_error


def _extract_parts(data: dict):
    try:
        return data["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError):
        return []


async def ai_assistant_open(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """وقتی کاربر دکمه‌ی «🤖 دستیار هوشمند» رو توی منو می‌زنه."""
    query = update.callback_query
    await query.answer()
    ctx.user_data["ai_mode"] = True
    ctx.user_data["ai_history"] = []
    try:
        await query.edit_message_text(
            "🤖 دستیار هوشمند فعال شد. هرچی بخوای بگو — می‌تونم کارهات رو انجام بدم، "
            "گزارش بدم یا فقط باهات حرف بزنم.\nبرای خروج بنویس «خروج از دستیار»."
        )
    except BadRequest:
        await query.message.reply_text(
            "🤖 دستیار هوشمند فعال شد. هرچی بخوای بگو — می‌تونم کارهات رو انجام بدم، "
            "گزارش بدم یا فقط باهات حرف بزنم.\nبرای خروج بنویس «خروج از دستیار»."
        )


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
        body = e.response.text[:500]
        logger.error(f"Gemini API error {e.response.status_code}: {body}")
        msg = "⚠️ ارتباط با هوش مصنوعی موقتاً مشکل داشت، چند لحظه دیگه امتحان کن."
        if role == ROLE_PISHVA:
            msg += f"\n\n🔧 جزئیات فنی (فقط برای پیشوا):\nکد: {e.response.status_code}\n{body}"
        await update.message.reply_text(msg)
    except Exception as e:
        logger.exception("AI assistant failed")
        msg = "⚠️ یه خطای غیرمنتظره پیش اومد."
        if role == ROLE_PISHVA:
            msg += f"\n\n🔧 جزئیات فنی: {type(e).__name__}: {e}"
        await update.message.reply_text(msg)
