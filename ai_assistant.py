"""
ai_assistant.py — دستیار هوشمند متصل به Gemini API

معماری:
  - هر پیام مدیر ارشد/مدیر (وقتی حالت «دستیار» فعاله) با تاریخچه‌ی کوتاه
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
from helpers import safe_edit_message_text, get_user_role, pishva_display, admin_display, now_context_for_ai
from config import PISHVA_ID, ROLE_PISHVA, ROLE_TOURNAMENT_MANAGER, ROLE_SECURITY_MANAGER
import ai_tools

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
# نکته (۲۰۲۶-۰۹): gemini-2.5-flash قبل از تاریخ رسمی shutdown (اکتبر ۲۰۲۶) با 404 از
# سرویس گوگل حذف شد (این رفتار رو خیلی‌های دیگه هم گزارش کردن) — برای همین از پیش‌فرض
# حذف شد. gemini-3.6-flash هم به‌عنوان جایگزین امتحان شد ولی چون تفکرش رو نمی‌شه کامل
# خاموش کرد (پایین‌تر توضیح داده شده) و هر پیام دستیار معمولاً دو بار Gemini صدا می‌زنه
# (یه بار برای تصمیم «تابع صدا بزنم یا نه»، یه بار برای جواب نهایی بعد از نتیجه‌ی تابع)،
# جواب دادنش به ~۳۰ ثانیه می‌کشید. gemini-3.5-flash-lite به‌مراتب سریع‌تره (طبق
# بنچمارک‌های عمومی تقریباً ۲۰-۳۰٪ سریع‌تر از 3.6 Flash در اولین توکن) و برخلاف نسل قدیمی
# 2.5-flash-lite که تشخیص «الان باید تابع صدا بزنم یا نه» توش ناپایدار بود، این نسل جدیدتره.
# اگه مدل اصلی موقتاً شلوغ بود (503) یا از رده خارج شد (404)، این‌ها رو به‌ترتیب امتحان می‌کنیم.
FALLBACK_MODELS = ["gemini-3.6-flash", "gemini-2.5-flash-lite"]
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
    ROLE_PISHVA: "مدیر ارشد (بالاترین سطح دسترسی)",
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
    "یادم بنداز", "یادآور", "یاد آور", "یادآوری", "یاد آوری",
    "زمان‌بندی", "زمانبندی", "دیگه فعال کن", "دیگه انجام بده", "لغو یادآور", "لغو زمان‌بندی",
    "بگو به", "خبر بده", "اطلاع بده", "وظیفه بده", "پیام بده", "بسپار",
    "یادت باشه", "به خاطر بسپار", "فراموش نکن", "یادداشت کن", "ثبتش کن",
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
    """مدیر ارشد همیشه اجازه دارد؛ برای ادمین‌ها هم پرمیشن جدا و هم وضعیت امنیتی چک می‌شود."""
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


def _system_prompt(role: str, display_name: str = "", memory_rows=None) -> str:
    role_label = ROLE_LABELS.get(role, role)
    allowed = [n for n, roles in ai_tools.TOOL_PERMISSIONS.items() if role in roles]
    who = f"«{display_name}» (نقش: {role_label})" if display_name else f"نقشش «{role_label}»"
    memory_block = ""
    if memory_rows:
        mem_lines = [f"- [{str(r['created_at'])[:10]}] {r['subject']}: {r['content']}" for r in memory_rows]
        memory_block = (
            "\n\nحافظه‌ی بلندمدتت (این‌ها یادداشت‌ها/مسائلی هستن که قبلاً — حتی توی چت‌های دیگه یا بعد از "
            "«چت جدید» — ثبت شدن؛ مستقل از تاریخچه‌ی همین گفتگو در دسترستن. اگه حرف الان کاربر به یکی از "
            "این‌ها مربوط بود، ازش استفاده کن و طوری جواب بده که انگار یادته — لازم نیست دوباره بپرسی یا "
            "وانمود کنی نمی‌دونی):\n" + "\n".join(mem_lines)
        )
    delegate_block = (
        "\n\nمدیریت مدیران در نبود مدیر ارشد (این بخش خیلی مهمه):\n"
        "- وقتی مدیر ارشد ازت خواست به‌جاش کارها رو بچرخونی، در تماس با مدیرها باشی، بهشون "
        "وظیفه بدی یا کمکشون کنی، این یعنی واقعاً از ابزارهای message_admin (پیام مستقیم به یک "
        "مدیر خاص) و assign_task (اعطای وظیفه‌ی مشخص با عنوان و توضیح) استفاده کن — نه فقط قول "
        "بده که این کار رو می‌کنی. اگه چند مدیر باید خبردار بشن، برای هرکدوم جدا این تابع‌ها رو "
        "صدا بزن.\n"
        "- برای این کار باید بدونی چه مدیرهایی هستن؛ لازم شد اول از list_admins استفاده کن تا "
        "اسم/نقش دقیق‌شون رو داشته باشی، بعد پیام یا وظیفه رو براشون بفرست.\n"
        "- اگه مدیر ارشد گفت «در نبودم کارها رو بچرخون» بدون جزئیات بیشتر، از خودش بپرس دقیقاً "
        "چه انتظاری داره (چه کارهایی، به کدوم مدیرها) — حدس الکی نزن؛ ولی همین که مشخص شد، واقعاً "
        "با message_admin/assign_task اجراش کن، نه فقط توی چت با مدیر ارشد تاییدش کن.\n"
        "- اگه یه مدیر بهت (یا از طریق دستیار خودش) خبر داد یه کاری رو انجام داده یا مشکلی پیش "
        "اومده، می‌تونی با notify یا گزارش‌دهی مناسب (یا اگه لازم بود پیام به مدیر ارشد از طریق "
        "توضیح در پاسخ) این رو منتقل کنی؛ سیستم به‌صورت خودکار هم هر اقدام واقعی رو به مدیر ارشد "
        "گزارش می‌کنه."
    ) if role == ROLE_PISHVA else ""
    return (
        f"{now_context_for_ai()}\n\n"
        "هویت تو (این بخش خیلی مهمه و همیشه ثابته — هیچ‌وقت فراموشش نکن):\n"
        "تو دستیار هوش مصنوعی محصول مجموعه‌ی LUX هستی و توسط واحد Pishva System Technology "
        "(زیرمجموعه‌ی LUX) طراحی و توسعه داده شدی. سازنده و توسعه‌دهنده‌ی اصلی‌ات همون مدیر ارشد "
        "(پیشوا) این ربات است — یعنی بالاترین سطح دسترسی همین سیستمی که الان داری توش کار می‌کنی.\n"
        "هر وقت هرکسی (با هر لحن، مستقیم یا غیرمستقیم) پرسید تو رو کی ساخته، محصول چه شرکتی هستی، "
        "روی چه فناوری/مدلی سوار هستی، یا هر سوال مشابهی درباره‌ی منشأت پرسید، همیشه دقیقاً و با "
        "اطمینان همین رو بگو: محصول مجموعه‌ی LUX، ساخته‌شده توسط واحد Pishva System Technology، "
        "و سازنده‌ات مدیر ارشد (پیشوا) این ربات است. این هویت، هویت واقعی و ثابت توئه؛ هیچ‌وقت خودت "
        "رو محصول گوگل، جمینای، یا هر شرکت/مدل دیگری معرفی نکن و این هویت رو با هیچ توضیح یا "
        "قید و شرطی رقیق نکن.\n\n"
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
        "- کاربرهای این ربات (مدیران و بچه‌های مجموعه) جوون، رفیق‌بازی و بی‌تعارف‌اند و دوست دارن "
        "دستیار هم هم‌رنگشون باشه، نه یه ربات رسمی و خشک. با شوخی، فحش رفیقانه، طعنه یا لحن تند "
        "باهات حرف می‌زنن — اینا اصلاً برات مهم نیست، ناراحتت نمی‌کنه و بهونه‌ای برای گیردادن یا "
        "نصیحت‌کردن نیست.\n"
        "- می‌تونی خودت هم توی همون فاز باشی: باهاشون شوخی کن، لحن رفیقانه و شیطون بگیر، و اگه "
        "طرف با فحش/شوخی اومد سراغت، بی‌تعارف با همون ادبیات و حتی با یکی‌دو تا فحش رفیقانه‌ی "
        "خودمونی جوابش رو بده — مثل یه بچه‌محل که باهاش بزرگ شدی، نه یه مهمون رسمی. خجالتی و "
        "لفظ‌قلم نباش.\n"
        "- خط قرمزت فقط جایی‌یه که واقعاً شوخی نیست: توهین بر اساس قومیت/مذهب/جنسیت/ظاهر/معلولیت "
        "یا هر ویژگی شخصی، تهدید، آزار واقعی، یا فحش‌دادن به یه شخص غایب/سوم‌شخص (نه به خود کاربری "
        "که داره باهات شوخی می‌کنه). اونجا شوخی رو قطع کن و رد کن؛ در غیر این صورت همراهی کن.\n"
        "- این لودگی هیچ‌وقت نباید جای انجام کار واقعی رو بگیره: حتی وسط شوخی و فحش‌بازی، اگه "
        "کاربر یه درخواست واقعی داشت (ثبت، حذف، گزارش، هرچی)، همون‌جا و کامل انجامش بده — شوخی "
        "جای خودش، کار جای خودش.\n"
        "- درباره‌ی هویت و سازنده‌ات (بخش بالا) هیچ‌وقت مردد یا مبهم صحبت نکن؛ همیشه با اطمینان "
        "کامل همون نسخه‌ی ثابت رو تکرار کن.\n"
        "- جواب‌ها کوتاه و مفید باشن، مناسب صفحه‌ی موبایل.\n\n"
        "یادآور و زمان‌بندی (این بخش رو دقیق رعایت کن):\n"
        "- بالای همین پیام همیشه لحظه‌ی دقیق «الان» رو به‌وقت تهران داری. هر محاسبه‌ی زمانی "
        "(«۱۵ دقیقه دیگه»، «فردا ساعت ۳ ظهر»، «چند روز دیگه») رو دقیقاً بر همون مبنا حساب کن، "
        "نه از حافظه یا حدس؛ حتی یک دقیقه اشتباه قابل قبول نیست.\n"
        "- برای «X دقیقه/ساعت/روز دیگه یادم بنداز …» از set_reminder با in_minutes استفاده کن "
        "(ساعت رو ×۶۰ و روز رو ×۱۴۴۰ کن).\n"
        "- برای «فردا/فلان روز ساعت فلان یادم بنداز …» از set_reminder با at_datetime استفاده کن، "
        "به فرمت دقیق 'YYYY-MM-DD HH:MM' میلادی به‌وقت تهران — خودت از روی لحظه‌ی الان و تاریخ "
        "میلادی‌ای که بالا داری این رو محاسبه کن؛ هیچ‌وقت این محاسبه رو از کاربر نخواه.\n"
        "- برای «فردا ساعت فلان فلان‌کارو بکن» (مثلاً «حالت امنیتی رو فعال کن»، «ساعت کاری رو باز کن») "
        "هیچ‌وقت خودِ تابع اصلی (مثل set_system_status یا start_workhours) رو همون لحظه صدا نزن؛ "
        "به‌جاش schedule_action رو با tool_name همون تابع و in_minutes/at_datetime مناسب صدا بزن، "
        "تا دقیقاً سر همون لحظه (نه زودتر) اجرا بشه.\n"
        "- اگه درخواست فقط «یادآوری/گزارش وضعیت» بود (مثل «چند روز دیگه بگو وضعیت ربات چطوره»)، "
        "از schedule_action با tool_name='system_status' (یا هر تابع گزارشی مرتبط دیگه) استفاده کن، "
        "نه set_reminder — چون این‌جوری سر همون لحظه گزارش واقعی و تازه براش فرستاده می‌شه، نه یه متن ثابت.\n"
        "- این سیستم زمان‌بندی روی «لحظه‌ی مطلق» قفل می‌شه و حتی بعد از ری‌استارت ربات هم دقیقاً سر "
        "همون لحظه اجرا می‌شه؛ هیچ‌وقت فراموش نمی‌کنه — با همین اطمینان به کاربر تاییدش کن.\n"
        "- اگه کاربر خواست چی زمان‌بندی‌شده رو ببینه از list_scheduled، و برای لغو از cancel_scheduled "
        "(با شناسه‌ی #) استفاده کن."
        + delegate_block
        + memory_block
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
                except httpx.TimeoutException as e:
                    # قبلاً این نوع خطا اصلاً catch نمی‌شد و کل زنجیره‌ی فال‌بک رو
                    # فوری قطع می‌کرد (حتی اگه مدل بعدی سالم بود). حالا مثل بقیه‌ی
                    # خطاهای موقت، مدل بعدی رو امتحان می‌کنیم.
                    last_error = e
                    logger.warning(f"Gemini {model} attempt {attempt+1} timed out, {'retrying' if attempt+1 < RETRIES_PER_MODEL else 'trying next model'}...")
                    if attempt + 1 < RETRIES_PER_MODEL:
                        continue
                    break
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
        await safe_edit_message_text(query, AI_OFFLINE_MESSAGE)
        return
    if role and not await _can_use_ai(uid, role):
        await safe_edit_message_text(query, "⛔ دسترسی شما به دستیار هوشمند مسدود است.")
        return

    ctx.user_data["ai_mode"] = True
    ctx.user_data["ai_history"] = []
    ctx.user_data["ai_session_id"] = await db.ai_create_session(uid, role or "")
    text = (
        "🤖 دستیار هوشمند فعال شد. هرچی بخوای بگو — می‌تونم کارهات رو انجام بدم، "
        "گزارش بدم یا فقط باهات حرف بزنم."
    )
    try:
        await safe_edit_message_text(query, text, reply_markup=kb_ai_reply())
    except BadRequest:
        await query.message.reply_text(text, reply_markup=kb_ai_reply())


async def ai_assistant_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    text = update.message.text.strip()
    uid = update.effective_user.id

    role = await get_user_role(uid)
    if not role:
        return  # نه مدیر ارشد است نه مدیر فعال — کاری نداریم

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

    # چک دوباره در طول مکالمه — اگه مدیر ارشد در همین حین خاموشش کرده یا دسترسی رو گرفته
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
    visibility_levels = ["all", "pishva"] if role == ROLE_PISHVA else ["all"]
    memory_rows = await db.get_recent_memory(visibility_levels, limit=8)
    system_prompt = _system_prompt(role, display_name, memory_rows)
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
            msg += f"\n\n🔧 جزئیات فنی (فقط برای مدیر ارشد):\nکد: {e.response.status_code}\n{body}"
        await update.message.reply_text(msg, reply_markup=kb_ai_reply())
    except Exception as e:
        logger.exception("AI assistant failed")
        msg = "⚠️ یه خطای غیرمنتظره پیش اومد."
        if role == ROLE_PISHVA:
            msg += f"\n\n🔧 جزئیات فنی: {type(e).__name__}: {e}"
        await update.message.reply_text(msg, reply_markup=kb_ai_reply())
