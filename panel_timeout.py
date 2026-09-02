"""
panel_timeout.py — بستن خودکار پنل‌های گروهی بعد از عدم فعالیت

هر پنلی که در گروه/سوپرگروه باز می‌شه (نه پیوی)، اگه صاحبش تا ۳ دقیقه
هیچ دکمه‌ای نزنه، پنل به‌صورت خودکار «بسته» می‌شه (پیام ادیت می‌شه و
دکمه‌ها حذف می‌شن). هر بار که صاحب پنل روی یک دکمه کلیک می‌کنه، این
تایمر ریست می‌شه.

استفاده:
    from panel_timeout import schedule_panel_timeout, reset_panel_timeout

    # وقتی پنل تازه باز/ادیت شد:
    schedule_panel_timeout(ctx, chat_id, message_id, owner_id)

    # وقتی صاحب پنل روی دکمه‌ای کلیک کرد (قبل از پردازش خودِ دکمه):
    reset_panel_timeout(ctx, chat_id, message_id, owner_id)
"""
import logging
from telegram.ext import ContextTypes
from telegram.error import TelegramError

logger = logging.getLogger(__name__)

PANEL_TIMEOUT_SECONDS = 180  # ۳ دقیقه
CLOSED_WELCOME_TIMEOUT_SECONDS = 60  # ۱ دقیقه — پیامِ خوش‌آمدگویی بعد از «بستن»/«خروج»

CLOSED_TEXT = (
    "⏱ *پنل به‌دلیل عدم فعالیت بسته شد.*\n\n"
    "برای باز کردن دوباره، کلمه «پنل» را ارسال کنید."
)


def _job_name(chat_id: int, message_id: int) -> str:
    return f"panel_timeout_{chat_id}_{message_id}"


async def _close_panel_job(ctx: ContextTypes.DEFAULT_TYPE):
    """Job callback: پنل رو می‌بنده (دکمه‌ها رو حذف و متن رو جایگزین می‌کنه)."""
    data = ctx.job.data or {}
    chat_id = data.get("chat_id")
    message_id = data.get("message_id")
    if chat_id is None or message_id is None:
        return
    try:
        await ctx.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=CLOSED_TEXT,
            parse_mode="Markdown",
            reply_markup=None,
        )
    except TelegramError as e:
        # پیام ممکنه از قبل حذف/ادیت شده باشه؛ مشکلی نیست
        logger.debug(f"Could not auto-close panel {chat_id}/{message_id}: {e}")


def _cancel_existing_job(ctx: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int):
    if ctx.job_queue is None:
        return
    for job in ctx.job_queue.get_jobs_by_name(_job_name(chat_id, message_id)):
        job.schedule_removal()


def schedule_panel_timeout(ctx: ContextTypes.DEFAULT_TYPE, chat_id: int,
                            message_id: int, owner_id: int, timeout_seconds: int = None):
    """تایمر بستن خودکار رو برای این پنل (چت+پیام) راه‌اندازی می‌کنه.
    اگه تایمر قبلی برای همین پیام وجود داشته باشه، اول حذفش می‌کنه.
    با timeout_seconds می‌شه بازه‌ی پیش‌فرض (۳ دقیقه) رو برای یک پیامِ
    خاص override کرد؛ مثلاً پیامِ خوش‌آمدگویی بعد از «بستن»/«خروج» که
    باید زودتر (۱ دقیقه) بسته بشه."""
    if ctx.job_queue is None:
        return
    _cancel_existing_job(ctx, chat_id, message_id)
    delay = timeout_seconds if timeout_seconds is not None else PANEL_TIMEOUT_SECONDS
    ctx.job_queue.run_once(
        _close_panel_job,
        when=delay,
        data={"chat_id": chat_id, "message_id": message_id, "owner_id": owner_id},
        name=_job_name(chat_id, message_id),
    )


def reset_panel_timeout(ctx: ContextTypes.DEFAULT_TYPE, chat_id: int,
                         message_id: int, owner_id: int, timeout_seconds: int = None):
    """با هر کلیک صاحب پنل روی یک دکمه، تایمر رو از نو شروع می‌کنه."""
    schedule_panel_timeout(ctx, chat_id, message_id, owner_id, timeout_seconds=timeout_seconds)


def cancel_panel_timeout(ctx: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int):
    """در صورت نیاز (مثلاً پنل با دستور دیگه‌ای بسته/جایگزین شد) تایمر رو کنسل می‌کنه."""
    _cancel_existing_job(ctx, chat_id, message_id)
