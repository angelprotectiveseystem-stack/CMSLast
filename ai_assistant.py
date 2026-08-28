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
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import BadRequest

import database as db
from helpers import get_user_role, pishva_display, admin_display
from config import PISHVA_ID, ROLE_PISHVA, ROLE_TOURNAMENT_MANAGER, ROLE_SECURITY_MANAGER
import ai_tools

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
# نکته‌ی مهم: «gemini-flash-latest» یه alias هست که گوگل با هر مدل جدید عوضش می‌کنه؛
# این چند وقت اخیر رفته روی Gemini 3.7 Flash (یه مدل سنگین، برای کدنویسی/ایجنت پیچیده)
# که هم کندتره هم فرمت تنظیمات «تفکر»ش با ۲.۵ فرق داره (پایین‌تر توضیح داده شده).
# توجه: gemini-2.5-flash-lite قبلاً این‌جا اول بود چون سریع‌ترینه، اما در عمل خیلی غیرقابل‌اعتماد
# بود در تشخیص «الان باید تابع صدا بزنم یا نه» (function calling) — همون چیزی که باعث می‌شد
# کاربر چند بار پشت‌سرهم دستور بده تا بالاخره یه بار درست اجرا بشه. gemini-2.5-flash کمی
# کندتره ولی خیلی پایدارتر تصمیم می‌گیره؛ برای یه دستیار اجرایی این مهم‌تر از چند صدم ثانیه سرعته.
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
# اگه مدل اصلی موقتاً شلوغ بود (خطای 503) یا از رده خارج شد (404)، این‌ها رو به‌ترتیب امتحان می‌کنیم.
# flash-lite به‌عنوان فال‌بک آخر نگه داشته شده (سریع ولی کمتر قابل‌اعتماد)، نه انتخاب اول.
FALLBACK_MODELS = ["gemini-2.5-flash", "gemini-3.5-flash-lite", "gemini-3.6-flash", "gemini-2.5-flash-lite"]
if GEMINI_MODEL in FALLBACK_MODELS:
    FALLBACK_MODELS.remove(GEMINI_MODEL)
MODEL_CHAIN = [GEMINI_MODEL] + FALLBACK_MODELS

RETRIES_PER_MODEL = 2
RETRY_DELAY_SECONDS = 1
REQUEST_TIMEOUT_SECONDS = 20   # جمینای معمولاً خیلی زودتر از ۳۰ ثانیه جواب می‌ده؛ تایم‌اوت کوتاه‌تر یعنی فال‌بک سریع‌تر
MAX_OUTPUT_TOKENS = 1024       # جواب‌ها قراره کوتاه و موبایل‌پسند باشن؛ سقف‌گذاری یعنی سرعت بیشتر و هزینه‌ی کمتر

MAX_HISTORY_TURNS = 6          # چند رفت‌وبرگشت آخر رو نگه داریم (کمتر = توکن کمتر = سریع‌تر)
MAX_TOOL_HOPS = 3              # جلوگیری از حلقه‌ی بی‌نهایت اگر مدل پشت‌سرهم تابع صدا بزنه

ROLE_LABELS = {
    ROLE_PISHVA: "پیشوا (بالاترین سطح دسترسی)",
    ROLE_TOURNAMENT_MANAGER: "مدیر مسابقات",
    ROLE_SECURITY_MANAGER: "مدیر امنیتی",
}

ACTIVATE_WORDS = {"دستیار", "دستیار هوشمند", "🤖 دستیار هوشمند"}
DEACTIVATE_WORDS = {"خروج از دستیار", "بستن دستیار", "بسه"}

AI_OFFLINE_MESSAGE = "💤 هوش مصنوعی فعلا در دسترس نیست."

# ────────────────────────────────────────────────────────────────
# اگه پیام کاربر شامل یکی از این کلمه‌ها باشه، یعنی احتمالاً یه کار
# اجرایی می‌خواد (نه صرفاً درددل/سوال). توی این حالت به‌جای اینکه فقط
# امیدوار باشیم مدل خودش تصمیم درست بگیره، با toolConfig مجبورش می‌کنیم
# حتماً یکی از تابع‌های مجازش رو صدا بزنه (mode="ANY") — این همون چیزیه
# که باعث می‌شد قبلاً باید ۱۰-۲۰ بار تکرار می‌کردی تا مدل بالاخره اقدام کنه.
# ────────────────────────────────────────────────────────────────
ACTION_KEYWORDS = [
    "ثبت", "حذف", "پاک کن", "اخطار", "اخراج", "برگردون", "بازگردان", "برگردان",
    "شروع", "پایان", "تموم کن", "تمومش کن", "ارسال", "بفرست", "بیانیه", "خبر",
    "مسدود", "بلاک", "آنبلاک", "غیرفعال", "فعال کن", "تغییر نقش", "تغییر بده",
    "نتیجه", "اصلاح کن", "باز کن", "روشن کن", "خاموش کن", "اجرا کن",
]


def _looks_like_action(text: str) -> bool:
    return any(kw in text for kw in ACTION_KEYWORDS)


def kb_ai_reply():
    """زیر هر پیام دستیار، همیشه دکمه‌ی خروج و چت جدید/تاریخچه باشد."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🆕 چت جدید", callback_data="ai_menu"),
         InlineKeyboardButton("🚪 خروج از چت", callback_data="ai_exit")],
    ])


def _merge_pending_buttons(ctx: ContextTypes.DEFAULT_TYPE):
    """اگه ابزار open_panel چیزی برای نشون‌دادن آماده کرده، به کیبورد پاسخ اضافه‌ش کن."""
    rows = kb_ai_reply().inline_keyboard
    pending = ctx.user_data.pop("_ai_pending_buttons", None)
    rows = list(rows)
    if pending:
        for label, cb in pending:
            rows.insert(0, [InlineKeyboardButton(label, callback_data=cb)])
    return InlineKeyboardMarkup(rows)


async def _is_ai_online() -> bool:
    return (await db.get_setting("ai_online", "1")) == "1"


async def _can_use_ai(uid: int, role: str) -> bool:
    """پیشوا همیشه اجازه دارد؛ برای ادمین‌ها هم پرمیشن جدا و هم وضعیت امنیتی چک می‌شود."""
    if uid == PISHVA_ID:
        return True
    status = await db.get_setting("system_status", "normal")
    if status in ("danger", "aps"):
        return False
    admin = await db.get_admin(uid)
    if not admin:
        return False
    try:
        perms = json.loads(admin["permissions"])
    except Exception:
        perms = {}
    # پیش‌فرض True تا ادمین‌های ثبت‌شده‌ی قبلی (بدون این کلید در permissions) بلاک نشوند
    return perms.get("ai_access", True)


def _system_prompt(role: str, display_name: str = "") -> str:
    role_label = ROLE_LABELS.get(role, role)
    allowed = [n for n, roles in ai_tools.TOOL_PERMISSIONS.items() if role in roles]
    who = f"«{display_name}» (نقش: {role_label})" if display_name else f"نقشش «{role_label}»"
    return (
        "تو دستیار هوشمند داخلی یک ربات مدیریت مدرسه/آکادمی شطرنج هستی، به فارسی محاوره‌ای و "
        "گرم و دوستانه صحبت می‌کنی — مثل یه همکار باتجربه و قابل‌اعتماد، نه یه ربات رسمی. "
        "می‌تونی درددل بشنوی، تحلیل بدی، گزارش بسازی، و کارها رو با ابزارهایی که در اختیارت "
        "گذاشته شده مستقیم انجام بدی.\n\n"
        f"کاربر فعلی {who} است. می‌دونی داری با همین شخص صحبت می‌کنی — نیازی نیست ازش "
        "بپرسی کیه یا نقشش چیه؛ لحن و خطابت رو متناسب با اسم و نقشش تنظیم کن.\n\n"
        "قوانین مهم:\n"
        "- فقط وقتی کاربر صراحتاً یه کار اجرایی خواست (ثبت، حذف، اخطار، شروع/پایان ساعت کاری، "
        "ارسال بیانیه، ثبت نتیجه‌ی مسابقه و مانند آن) از ابزارها استفاده کن.\n"
        "- اگه اطلاعات لازم کامل بود، همون لحظه‌ی اول با فراخوانی تابع کار رو انجام بده — "
        "فقط حرف نزن که «الان انجامش می‌دم» یا «باشه»، واقعاً تابع رو صدا بزن. کاربر نباید "
        "مجبور بشه دوباره همون درخواست رو تکرار کنه.\n"
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


def _thinking_config_for(model: str) -> dict:
    """
    نسل ۳ جمینای (gemini-3.x) به‌جای «thinkingBudget» از «thinkingLevel» استفاده می‌کنه.
    فرستادن thinkingBudget برای یه مدل نسل ۳ دقیقاً همون خطای
    400 INVALID_ARGUMENT رو می‌ده که داشتی می‌گرفتی — چون فیلدش برای اون مدل معتبر نیست.
    مدل‌های نسل ۳ فلش/فلش‌لایت هم اصلاً امکان «خاموش کامل» تفکر رو ندارن؛
    پایین‌ترین و سریع‌ترین سطح مجاز، 'low' هست.

    برای نسل ۲.۵: قبلاً thinkingBudget=0 (کاملاً خاموش) بود که باعث می‌شد مدل
    بدون فکرکردن مستقیم بره سراغ جواب متنی و تشخیصش برای «کِی باید تابع صدا بزنه»
    خیلی ناپایدار بشه. یه بودجه‌ی کوچیک (نه صفر) بهش اجازه می‌ده قبل از تصمیم
    واقعاً یه لحظه فکر کنه — تاخیر محسوس نیست ولی دقتش خیلی بهتر می‌شه.
    """
    if model.startswith("gemini-3"):
        return {"thinkingLevel": "low"}
    return {"thinkingBudget": 512}


async def _call_gemini(contents: list, tools, tool_config=None):
    headers = {"Content-Type": "application/json", "x-goog-api-key": GEMINI_API_KEY}

    last_error = None
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        for i, model in enumerate(MODEL_CHAIN):
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            is_last_model = (i == len(MODEL_CHAIN) - 1)
            payload = {
                "contents": contents,
                "generationConfig": {
                    "thinkingConfig": _thinking_config_for(model),
                    "maxOutputTokens": MAX_OUTPUT_TOKENS,
                    # دمای پایین‌تر یعنی تصمیم «تابع صدا بزنم یا نه» رو با ثبات بیشتری
                    # می‌گیره؛ برای یه دستیار اجرایی مهم‌تر از تنوع/خلاقیتِ لحنه.
                    "temperature": 0.3,
                },
            }
            if tools:
                payload["tools"] = tools
                if tool_config:
                    payload["toolConfig"] = tool_config
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
                    elif code in (404, 400) and not is_last_model:
                        # مدل موجود نیست (404) یا این مدل خاص یه ایراد تنظیماتی داره (400) —
                        # برو سراغ مدل بعدی؛ تلاش دوباره روی همین مدل بی‌فایده‌ست
                        logger.warning(f"Gemini model {model} failed ({code}), trying next model...")
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
    uid = query.from_user.id
    role = await get_user_role(uid)

    if not await _is_ai_online():
        await query.edit_message_text(AI_OFFLINE_MESSAGE)
        return
    if role and not await _can_use_ai(uid, role):
        await query.edit_message_text("⛔ دسترسی شما به دستیار هوشمند مسدود است.")
        return

    ctx.user_data["ai_mode"] = True
    ctx.user_data["ai_history"] = []
    ctx.user_data["ai_session_id"] = await db.ai_create_session(uid, role or "")
    text = (
        "🤖 دستیار هوشمند فعال شد. هرچی بخوای بگو — می‌تونم کارهات رو انجام بدم، "
        "گزارش بدم یا فقط باهات حرف بزنم."
    )
    try:
        await query.edit_message_text(text, reply_markup=kb_ai_reply())
    except BadRequest:
        await query.message.reply_text(text, reply_markup=kb_ai_reply())


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
        if not await _is_ai_online():
            await update.message.reply_text(AI_OFFLINE_MESSAGE)
            return
        if not await _can_use_ai(uid, role):
            await update.message.reply_text("⛔ دسترسی شما به دستیار هوشمند مسدود است.")
            return
        ctx.user_data["ai_mode"] = True
        ctx.user_data["ai_history"] = []
        ctx.user_data["ai_session_id"] = await db.ai_create_session(uid, role)
        await update.message.reply_text(
            "🤖 دستیار هوشمند فعال شد. هرچی بخوای بگو — می‌تونم کارهات رو انجام بدم، "
            "گزارش بدم یا فقط باهات حرف بزنم.",
            reply_markup=kb_ai_reply()
        )
        return

    if not ctx.user_data.get("ai_mode"):
        return  # حالت دستیار فعال نیست — به بقیه‌ی هندلرها بسپار

    if text in DEACTIVATE_WORDS:
        ctx.user_data["ai_mode"] = False
        ctx.user_data.pop("ai_history", None)
        ctx.user_data.pop("ai_session_id", None)
        await update.message.reply_text("👋 از حالت دستیار خارج شدی.")
        return

    # چک دوباره در طول مکالمه — اگه پیشوا در همین حین خاموشش کرده یا دسترسی رو گرفته
    if not await _is_ai_online():
        ctx.user_data["ai_mode"] = False
        await update.message.reply_text(AI_OFFLINE_MESSAGE)
        return
    if not await _can_use_ai(uid, role):
        ctx.user_data["ai_mode"] = False
        await update.message.reply_text("⛔ دسترسی شما به دستیار هوشمند مسدود شد.")
        return

    if not GEMINI_API_KEY:
        await update.message.reply_text("⚠️ کلید Gemini تنظیم نشده (GEMINI_API_KEY خالیه).")
        return

    session_id = ctx.user_data.get("ai_session_id")
    if not session_id:
        session_id = await db.ai_create_session(uid, role)
        ctx.user_data["ai_session_id"] = session_id

    await db.ai_add_message(session_id, "user", text)

    history = ctx.user_data.setdefault("ai_history", [])
    history.append({"role": "user", "parts": [{"text": text}]})

    if role == ROLE_PISHVA:
        display_name = await pishva_display()
    else:
        display_name = await admin_display(await db.get_admin(uid))
    system_prompt = _system_prompt(role, display_name)
    contents = [{"role": "user", "parts": [{"text": system_prompt}]},
                {"role": "model", "parts": [{"text": "باشه، آماده‌ام کمک کنم."}]}] + history

    tools = _tools_for_role(role)

    # فقط دور اول رو مجبور می‌کنیم حتماً یه تابع صدا بزنه (اگه پیام بوی «اقدام» بده)؛
    # از دور دوم به بعد اجازه می‌دیم آزاد باشه، وگرنه ممکنه بین صدازدن تابع‌ها گیر کنه.
    force_action = bool(tools) and _looks_like_action(text)
    executed_actions = []  # برای گزارش سیستم زیر پیام نهایی

    await update.message.chat.send_action("typing")

    try:
        for _hop in range(MAX_TOOL_HOPS):
            tool_config = {"functionCallingConfig": {"mode": "ANY"}} if (force_action and _hop == 0) else None
            data = await _call_gemini(contents, tools, tool_config)
            parts = _extract_parts(data)
            if not parts:
                await update.message.reply_text("⚠️ پاسخی از مدل دریافت نشد، دوباره امتحان کن.")
                return

            fn_call = next((p["functionCall"] for p in parts if "functionCall" in p), None)

            if fn_call:
                fname = fn_call["name"]
                fargs = fn_call.get("args", {})
                result_text = await ai_tools.dispatch(fname, fargs, uid, role, ctx)
                await db.ai_add_message(session_id, "tool", f"🔧 {fname}({fargs}) → {result_text}")
                if fname in ai_tools.ACTION_TOOL_NAMES:
                    executed_actions.append((fname, fargs, result_text))

                # نکته‌ی مهم: باید همون «parts»ی که خود مدل برگردونده رو عیناً پس بفرستیم،
                # نه اینکه فقط functionCall رو دستی بازسازی کنیم. مدل‌های نسل ۳ جمینای یه
                # فیلد «thoughtSignature» کنار functionCall برمی‌گردونن که برگردوندنش الزامیه؛
                # اگه حذفش کنیم (مثل قبل) دور بعدی با 400 INVALID_ARGUMENT رد می‌شه.
                contents.append({"role": "model", "parts": parts})
                contents.append({
                    "role": "user",
                    "parts": [{"functionResponse": {"name": fname, "response": {"result": result_text}}}],
                })
                continue  # یه دور دیگه بزن تا مدل جواب نهایی رو بر اساس نتیجه بسازه

            # پاسخ متنی نهایی
            reply_text = "".join(p.get("text", "") for p in parts).strip() or "باشه."
            if executed_actions:
                # گزارش سیستم — تأیید صریح که واقعاً چه اقدامی انجام شد، مستقل از لحن مدل.
                report_lines = [f"— {fn}: {res}" for fn, _fargs, res in executed_actions]
                reply_text += "\n\n📋 گزارش سیستم:\n" + "\n".join(report_lines)
            history.append({"role": "model", "parts": [{"text": reply_text}]})
            ctx.user_data["ai_history"] = history[-(MAX_HISTORY_TURNS * 2):]
            await db.ai_add_message(session_id, "ai", reply_text)
            sess = await db.ai_get_session(session_id)
            if sess and not sess["title"]:
                await db.ai_set_session_title(session_id, text)
            await update.message.reply_text(reply_text, reply_markup=_merge_pending_buttons(ctx))
            return

        fallback = "⚠️ این درخواست خیلی پیچیده شد؛ لطفاً واضح‌تر یا مرحله‌به‌مرحله بگو."
        if executed_actions:
            report_lines = [f"— {fn}: {res}" for fn, _fargs, res in executed_actions]
            fallback += "\n\n📋 گزارش سیستم (کارهایی که تا اینجا واقعاً انجام شد):\n" + "\n".join(report_lines)
        await update.message.reply_text(fallback, reply_markup=_merge_pending_buttons(ctx))

    except httpx.HTTPStatusError as e:
        body = e.response.text[:500]
        logger.error(f"Gemini API error {e.response.status_code}: {body}")
        msg = "⚠️ ارتباط با هوش مصنوعی موقتاً مشکل داشت، چند لحظه دیگه امتحان کن."
        if role == ROLE_PISHVA:
            msg += f"\n\n🔧 جزئیات فنی (فقط برای پیشوا):\nکد: {e.response.status_code}\n{body}"
        await update.message.reply_text(msg, reply_markup=kb_ai_reply())
    except Exception as e:
        logger.exception("AI assistant failed")
        msg = "⚠️ یه خطای غیرمنتظره پیش اومد."
        if role == ROLE_PISHVA:
            msg += f"\n\n🔧 جزئیات فنی: {type(e).__name__}: {e}"
        await update.message.reply_text(msg, reply_markup=kb_ai_reply())
