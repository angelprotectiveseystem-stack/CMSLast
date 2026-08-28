import logging
from telegram import Update, BotCommand, BotCommandScopeChat
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, filters
)

import database as db
from ai_assistant import ai_assistant_message, ai_assistant_open
from ai_history import (
    ai_exit, ai_menu, ai_menu_close, ai_new_start, ai_hist_list, ai_hist_open,
    ai_admlog_menu, ai_admlog_pick, ai_admlog_range, ai_admlog_view,
)
from config import BOT_TOKEN, PISHVA_ID
from config import (
    ST_ROLE_SELECT, ST_PISHVA_PASSWORD, ST_ADMIN_USERNAME, ST_ADMIN_FULLNAME,
    ST_CLASS_NAME, ST_PLAYER_CLASS_SELECT, ST_PLAYER_NAME,
    ST_TOURNAMENT_NAME, ST_TOURNAMENT_EDIT,
    ST_MATCH_WHITE, ST_MATCH_BLACK, ST_MATCH_DATE, ST_MATCH_DRAW_REASON,
    ST_MATCH_CANCEL_REASON,
    ST_WARNING_REASON, ST_NOTE_TEXT, ST_EDIT_PLAYER_NAME, ST_SEARCH_PLAYER,
    ST_SEARCH_MATCH, ST_SEND_MSG_SELECT_ADMIN, ST_SEND_MSG_TEXT,
    ST_ANNOUNCEMENT_TEXT, ST_ANNOUNCEMENT_FILE, ST_NEWS_TEXT,
    ST_TASK_SELECT_ADMIN, ST_TASK_TITLE, ST_TASK_DESC, ST_TASK_DONE_REASON,
    ST_FEEDBACK_TEXT, ST_FEATURE_DESC,
    ST_PISHVA_NAME_CHANGE, ST_ADMIN_NAME_CHANGE,
    ST_NEW_YEAR_PASSWORD, ST_REPAIR_REASON, ST_GROUP_ID,
    ST_UPDATE_VERSION, ST_UPDATE_DESC, ST_ACCESS_REQUEST_MSG,
    ST_ADMIN_WARNING_REASON, ST_TEAM_NAME, ST_TEAM_SLOGAN, ST_TEAM_MEMBERS,
    ST_TEAM_DATE, ST_TEAM_REQUESTER,
    ST_BULK_REG_TEXT, ST_BULK_REG_PREVIEW, ST_BULK_REG_EDIT_NUM, ST_BULK_REG_EDIT_VALUE,
    ST_CHANNEL_ID,
    ST_ADV_LOTTERY_SCOPE, ST_ADV_LOTTERY_CLASS_A, ST_ADV_LOTTERY_CLASS_B, ST_ADV_LOTTERY_COUNT,
    ST_RESTORE_FILE,
    ST_WORKHOURS_AUTOEND_MINUTES, ST_WORKHOURS_REMINDER_MINUTES,
)

from auth import (
    cmd_start, on_role_select, on_pishva_password, on_admin_username,
    on_admin_fullname, on_access_request_msg, on_approve_request, on_reject_request
)
from navigation import (
    back_main, menu_tournament, menu_players, menu_matches, menu_pishva,
    menu_comms, menu_help, menu_admins, menu_tasks, menu_feedback,
    back_tournament, back_players, back_matches, back_class_manage,
    back_player_list, back_teams_menu,
    refresh_dashboard,
)
from tournament import (
    tourn_menu, tourn_add_start, tourn_add_name, tourn_manage, tourn_select,
    tourn_edit_start, tourn_edit_name, tourn_end, tourn_pause, tourn_delete,
    tourn_setdefault, tourn_default, tourn_details, tourn_deleted
)
from players import (
    class_add_start, class_add_name, class_list, class_select, class_players,
    class_edit, class_perf, player_add_start, player_class_selected, player_add_name,
    player_join_team, player_no_team, player_list, player_list_page, player_view,
    player_warn_start, player_warn_reason, player_kick, player_suspend, player_revive,
    player_note_start, player_note_save, player_elite_set, player_special_set,
    player_editname_start, player_editname_save, player_editclass_start, player_setclass,
    player_search_start, player_search_run, player_continuing, player_eliminated,
    player_list_kicked, player_list_elim, player_elite_list, player_special_list
)
from matches import (
    match_add_start, match_white_selected, match_black_selected,
    match_white_page, match_white_search_text, match_black_page, match_black_search_text,
    match_date_today, match_date_text, match_result_menu, match_result_select,
    match_result_page,
    result_white, result_black, result_draw, draw_reason, draw_reason_text,
    result_cancel_ask, match_cancel_reason_text,
    eliminate_yes, eliminate_no, match_history, match_hist_filter,
    match_hist_search_start, match_hist_search_run, match_full_history,
    match_view, match_delete, match_pin, match_panel,
    lottery_start, lottery_all, lottery_class_select, lottery_class_chosen,
    lottery_confirm, lottery_redo, lottery_manual,
    adv_lottery_start, adv_lottery_scope_chosen, adv_lottery_classA_chosen,
    adv_lottery_classB_chosen, adv_lottery_count_received,
    adv_lottery_confirm, adv_lottery_redo, adv_lottery_cancel
)
from pishva import (
    pishva_status, set_status, pishva_settings, toggle_setting,
    pishva_dbstatus, dbstatus_on, dbstatus_off,
    pishva_logs, show_logs, pishva_requests, pishva_backup,
    backup_period_select, backup_format_select,
    pishva_repair, repair_on, repair_off,
    repair_reason_start, repair_reason_save, pishva_identity,
    identity_pishva_start, identity_pishva_save, identity_admin_start,
    identity_admin_select, identity_admin_save, pishva_newyear,
    newyear_yes, newyear_password, pishva_update, update_sleep,
    update_announce_start, update_version_received, update_desc_received,
    pishva_group, group_id_save, pishva_channel, channel_id_save,
    pishva_broadcast, broadcast_toggle, pishva_vault,
    pishva_auto_backup, auto_backup_toggle, auto_backup_interval_menu,
    auto_backup_set_interval, auto_backup_fmt_toggle, auto_backup_period_toggle,
    pishva_restore_start, restore_file_received, restore_confirm_apply, restore_cancel,
)
from comms import (
    comms_msg_admin_start, comms_msg_target, comms_msg_send,
    comms_msg_pishva_start, comms_msg_other_start, comms_inbox,
    comms_all_msgs, comms_announce_start, comms_announce_text,
    comms_announce_no_file, comms_announce_with_file,
    comms_announce_file_received, comms_ann_history, ann_view, ann_delete,
    comms_news_start, comms_news_send, comms_news_list,
    comms_notifs, comms_reports, msg_ack
)
from misc import (
    task_assign_start, task_to_admin, task_title_received, task_desc_received,
    task_track, task_view, task_ack, task_done, task_fail_start, task_fail_reason,
    task_followup, task_history, task_history_filter,
    admin_view, admin_perms, perm_toggle, admin_warn_start, admin_warn_reason,
    admin_clear_warnings,
    admin_kick, admin_msg_start, admin_task_start,
    cmd_ss, fb_start, fb_text_received, fb_feature_desc, fb_view,
    help_section, teams_menu, teams_list, team_view, team_members_view,
    team_member_actions, team_remove_member, team_captain_start, team_captain_set,
    team_delete, team_warnings_view,
    cmd_panic, cmd_unpanic, cmd_freeze_all, cmd_terminal, cmd_backup_now,
    cmd_override_strike, cmd_help,
)
from workhours import (
    pishva_workhours, workhour_start, workhour_start_minutes_received,
    workhour_end, workhours_autoend_toggle, workhours_reminder_toggle,
    workhours_reminder_minutes_start, workhours_reminder_minutes_received,
    restore_workhours_jobs,
)
from help_center import help_main, help_tutorial
from dashboard import dashboard_pishva, dashboard_admin
from features import (show_elo_leaderboard, show_elo_info, show_player_elo_panel,
    show_prediction_select, show_prediction, show_champions, show_bracket)
from teams_add import (
    teams_add_start, team_name_received, team_skip_slogan, team_slogan_received,
    team_toggle_member, team_skip_members, team_confirm_members,
    team_date_today, team_date_text, team_requester_received, teams_settings
)
from bulk_register import (
    bulk_register_start, bulk_register_text_received, bulk_confirm,
    bulk_cancel, bulk_edit_start, bulk_edit_num_received, bulk_edit_value_received
)
from reminders import (
    reminder_job, pishva_reminders, reminder_toggle,
    reminder_interval_menu, reminder_set_interval
)
from keyword_commands import handle_keyword_command, kw_announce_start, kw_news_start, panel_ownership_guard, open_panel_here
from security import (
    security_panel, security_queue_list, security_queue_item,
    request_to_queue, queue_approve, queue_release, queue_block_ask,
    request_block_ask, block_confirm, security_blocked_list,
    security_blocked_item, unblock_action, block_gate,
)

logging.basicConfig(
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ─── Shared ConversationHandler kwargs ───────────────────────
CONV_KWARGS = dict(
    allow_reentry=True,
    per_message=False,
    per_chat=True,
    per_user=True,
)


async def post_init(application: Application) -> None:
    await db.init_db()
    logger.info("Database initialized.")

    try:
        from elo import ensure_elo_table
        await ensure_elo_table()
        logger.info("Elo tables ready.")
    except Exception as e:
        logger.warning(f"Elo init failed: {e}")

    # Set bot commands
    pishva_cmds = [
        BotCommand("start", "🏠 شروع — منوی اصلی"),
        BotCommand("help", "❓ راهنمای دستورات"),
        BotCommand("panic", "🔴 وضعیت خطرناک اضطراری"),
        BotCommand("unpanic", "🟢 بازگشت به وضعیت نرمال"),
        BotCommand("freeze_all", "🪽 فعال‌سازی حالت APS"),
        BotCommand("terminal", "🖥️ تله‌متری سیستم"),
        BotCommand("backup_now", "💾 بکاپ اضطراری"),
        BotCommand("ss", "📋 اعطای سریع وظیفه"),
        BotCommand("open", "🟢 آغاز ساعت کاری"),
        BotCommand("close", "🔴 پایان ساعت کاری"),
    ]
    admin_cmds = [
        BotCommand("start", "🏠 شروع — منوی اصلی"),
        BotCommand("help", "❓ راهنمای دستورات"),
    ]
    try:
        await application.bot.set_my_commands(
            pishva_cmds,
            scope=BotCommandScopeChat(chat_id=PISHVA_ID)
        )
        await application.bot.set_my_commands(admin_cmds)
        logger.info("Bot commands set.")
    except Exception as e:
        logger.warning(f"Could not set commands: {e}")

    # Schedule weekly champion announcement — دقیقاً هر دوشنبه ساعت ۹ صبح
    # به‌وقت تهران، با precise_scheduler روی یک لحظهٔ مطلق (نه run_repeating
    # نسبی که با هر ری‌استارت رایلوی جابه‌جا می‌شد و انحراف جمع می‌کرد)
    try:
        from features import weekly_champion_wrapper, next_monday_9am
        import precise_scheduler as sched
        from datetime import datetime
        from helpers import TEHRAN_TZ
        existing, _ = await sched.load_target("weekly_champion")
        if existing is None:
            target = next_monday_9am(datetime.now(TEHRAN_TZ))
            await sched.schedule_persistent(application.job_queue, weekly_champion_wrapper, target, "weekly_champion")
            logger.info(f"Weekly champion job scheduled for {target}")
        else:
            await sched.restore_pending(application.job_queue, weekly_champion_wrapper, "weekly_champion")
            logger.info("Weekly champion job restored from previous schedule")
    except Exception as e:
        logger.warning(f'Could not schedule weekly champion: {e}')

    # Restore working-hours auto-end / reminder jobs (survives Railway restarts)
    try:
        from workhours import restore_workhours_jobs
        await restore_workhours_jobs(application)
        logger.info("Working-hours precise jobs restored.")
    except Exception as e:
        logger.warning(f"Could not restore working-hours jobs: {e}")

    # Schedule auto-backup if enabled
    try:
        enabled = await db.get_setting("auto_backup_enabled", "0")
        if enabled == "1":
            interval = int(await db.get_setting("auto_backup_interval", "24"))
            from backup_utils import schedule_auto_backup
            schedule_auto_backup(application, interval)
            logger.info(f"Auto-backup scheduled every {interval}h")
    except Exception as e:
        logger.warning(f"Could not schedule auto-backup: {e}")

    # Schedule hourly reminder checks
    try:
        application.job_queue.run_repeating(
            reminder_job,
            interval=timedelta(hours=1),
            first=timedelta(minutes=5),
            name="reminder_checks"
        )
        logger.info("Reminder checks scheduled every 1h.")
    except Exception as e:
        logger.warning(f"Could not schedule reminder checks: {e}")


async def _noop_callback(update: Update, ctx) -> None:
    await update.callback_query.answer()


async def global_error_handler(update, context) -> None:
    """هر خطای مدیریت‌نشده‌ای که توی هر هندلری رخ بده، اینجا گیر می‌افته.
    به‌جای اینکه فقط توی لاگ Railway گم بشه، هم به مدیر ارشد اطلاع می‌ده هم به کاربر.

    نکته‌ی مهم: خود این هندلر نباید هیچ‌وقت بترکه. قبلاً گزارش به مدیر ارشد با
    parse_mode="Markdown" و بدون escape کردن نام کاربر/متن خطا فرستاده می‌شد؛
    اگه اسم کاربر یا متن خطا یه '_' یا '`' یا '*' فرد داشت، همین ارسالِ گزارشِ
    خطا خودش با «Can't parse entities» رد می‌شد. الان escape می‌کنیم و اگه
    بازم Markdown رد بشه، به‌صورت متن ساده می‌فرستیم — پس هیچ‌وقت گزارش گم نمی‌شه.
    """
    import traceback

    tb_string = "".join(
        traceback.format_exception(None, context.error, context.error.__traceback__)
    )
    logger.error(f"Unhandled exception: {context.error}\n{tb_string}")

    # اطلاع به کاربر: فقط اگه از یه پیام/دکمه‌ی واقعی اومده باشه
    try:
        if isinstance(update, Update):
            if update.callback_query:
                await update.callback_query.answer(
                    "⚠️ خطایی رخ داد. به مدیر ارشد اطلاع داده شد.", show_alert=True
                )
            elif update.effective_message:
                await update.effective_message.reply_text(
                    "⚠️ متاسفانه یک خطا رخ داد. این مشکل به‌طور خودکار به مدیر ارشد گزارش شد."
                )
    except Exception:
        pass

    # اطلاع به مدیر ارشد: خلاصه‌ی خطا + آخرین فریمِ مربوط به کد خودمون (نه کتابخانه‌ی
    # تلگرام) تا واقعاً معلوم باشه خطا توی کدوم فایل/تابع رخ داده، نه فقط اینکه
    # کتابخانه‌ی تلگرام کجا BadRequest رو raise کرده.
    try:
        from helpers import escape_md_legacy, safe_send_message

        error_summary = escape_md_legacy(str(context.error)[:300])
        tb_frames = traceback.extract_tb(context.error.__traceback__)
        app_frames = [f for f in tb_frames if "site-packages" not in f.filename and "/telegram/" not in f.filename]
        origin = app_frames[-1] if app_frames else (tb_frames[-1] if tb_frames else None)
        origin_line = (
            f"📍 محل خطا: `{origin.filename.split('/')[-1]}:{origin.lineno}` در `{origin.name}`\n\n"
            if origin else ""
        )
        last_tb_lines = escape_md_legacy("\n".join(tb_string.strip().splitlines()[-6:]))
        user_info = ""
        if isinstance(update, Update) and update.effective_user:
            u = update.effective_user
            user_info = f"👤 کاربر: {escape_md_legacy(u.full_name)} (`{u.id}`)\n"
        text = (
            "🚨 *خطای مدیریت‌نشده در ربات*\n\n"
            f"{user_info}"
            f"❗️ خطا: `{error_summary}`\n\n"
            f"{origin_line}"
            f"```\n{last_tb_lines}\n```"
        )
        await safe_send_message(context.bot, PISHVA_ID, text)
    except Exception as notify_err:
        logger.error(f"Could not notify PISHVA about error: {notify_err}")


# ─── دروازه‌ی عمومی دکمه‌های «بازگشت» ──────────────────────────
# خیلی از صفحه‌های زیرمجموعه (وضعیت سیستم/امنیت، بکاپ، تعمیر، هویت،
# آپدیت، مدیران، وظایف، فیدبک، مخابرات، تیم‌ها، کلاس‌ها، تاریخچه‌ی
# مسابقات و ...) دکمه‌ی «🔙 بازگشت» خودشون رو با kb.kb_back("...")
# می‌سازن، ولی برای خیلی از این مقصدها هیچ‌وقت هندلر جداگانه‌ای ثبت
# نشده بود؛ در نتیجه با زدنشون هیچ اتفاقی نمی‌افتاد.
# این هندلر عمومی، تمام "back_..."هایی که هندلر اختصاصی ندارن رو
# می‌گیره و به همون صفحه‌ی مقصد (که نسخه‌ی بدون "back_" آن از قبل
# ثبت شده) هدایت می‌کنه. چون هندلرهای اختصاصی (back_main, back_matches,
# back_players, back_player_list, back_teams_menu, back_tournament)
# زودتر ثبت می‌شن، این هندلر فقط برای بقیه‌ی موارد اجرا می‌شه.
_BACK_TARGET_HANDLERS = {}


def _register_back_targets():
    """نگاشت مقصد → تابع صفحه‌ی مقصد. فقط یک‌بار پر می‌شود."""
    if _BACK_TARGET_HANDLERS:
        return
    _BACK_TARGET_HANDLERS.update({
        "pishva_panel": menu_pishva,
        "pishva_status": pishva_status,
        "pishva_backup": pishva_backup,
        "pishva_repair": pishva_repair,
        "pishva_identity": pishva_identity,
        "pishva_update": pishva_update,
        "menu_admins": menu_admins,
        "menu_tasks": menu_tasks,
        "menu_feedback": menu_feedback,
        "tasks": menu_tasks,
        "task_track": task_track,
        "comms": menu_comms,
        "comms_pishva": menu_comms,
        "comms_admin": menu_comms,
        "class_list": class_list,
        "teams_list": teams_list,
        "match_history": match_history,
    })


async def universal_back_router(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    _register_back_targets()
    query = update.callback_query
    if not query or not query.data:
        return
    target = query.data[len("back_"):]

    handler = _BACK_TARGET_HANDLERS.get(target)
    if handler is None:
        if target.startswith("class_select_"):
            handler = class_select
        elif target.startswith("team_view_"):
            handler = team_view
        elif target.startswith("team_members_"):
            handler = team_members_view

    if handler is None:
        # مقصد ناشناخته → به‌جای هیچ‌کاری، به‌عنوان آخرین راه‌حل به منوی اصلی برگرد
        # تا دکمه هیچ‌وقت کاملاً «مرده» به نظر نرسه.
        handler = back_main

    await handler(update, ctx)


def build_application():
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    # 🚨 هندلر سراسری خطا — باید همیشه ثبت بشه تا خطاها گم نشن
    app.add_error_handler(global_error_handler)

    # 🛡️ دروازه‌ی امنیتی APS — باید همیشه قبل از همه‌چیز اجرا شود
    app.add_handler(MessageHandler(filters.ALL, block_gate), group=-1)
    app.add_handler(CallbackQueryHandler(block_gate, pattern=".*"), group=-1)

    # 🔒 محافظ مالکیت پنل در گروه — قبل از همه‌ی CallbackQueryHandler‌ها
    app.add_handler(CallbackQueryHandler(panel_ownership_guard, pattern=".*"), group=-2)
    app.add_handler(CallbackQueryHandler(open_panel_here, pattern="^open_panel_here_"), group=0)


    # Auth
    auth_conv = ConversationHandler(
        entry_points=[CommandHandler("start", cmd_start)],
        states={
            ST_ROLE_SELECT: [
                CallbackQueryHandler(on_role_select, pattern="^role_")
            ],
            ST_PISHVA_PASSWORD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, on_pishva_password)
            ],
            ST_ADMIN_USERNAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, on_admin_username)
            ],
            ST_ADMIN_FULLNAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, on_admin_fullname)
            ],
            ST_ACCESS_REQUEST_MSG: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, on_access_request_msg),
                CommandHandler("skip", on_access_request_msg),
            ],
        },
        fallbacks=[CommandHandler("start", cmd_start)],
        **CONV_KWARGS
    )

    # Tournament
    tourn_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(tourn_add_start, pattern="^tourn_add$"),
            CallbackQueryHandler(tourn_edit_start, pattern="^tourn_edit_"),
        ],
        states={
            ST_TOURNAMENT_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, tourn_add_name)
            ],
            ST_TOURNAMENT_EDIT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, tourn_edit_name)
            ],
        },
        fallbacks=[CallbackQueryHandler(back_tournament, pattern="^back_tournament$")],
        **CONV_KWARGS
    )

    # Player
    player_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(player_add_start, pattern="^player_add$"),
            CallbackQueryHandler(class_add_start, pattern="^class_add$"),
            CallbackQueryHandler(class_edit, pattern="^class_edit_"),
            CallbackQueryHandler(player_warn_start, pattern="^player_warn_"),
            CallbackQueryHandler(player_note_start, pattern="^player_note_"),
            CallbackQueryHandler(player_editname_start, pattern="^player_editname_"),
            CallbackQueryHandler(player_editclass_start,pattern="^player_editclass_"),
            CallbackQueryHandler(player_search_start, pattern="^player_search$"),
            CallbackQueryHandler(bulk_register_start, pattern="^bulk_register_start$"),
        ],
        states={
            ST_CLASS_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, class_add_name)
            ],
            ST_PLAYER_CLASS_SELECT: [
                CallbackQueryHandler(player_class_selected, pattern="^pclass_")
            ],
            ST_PLAYER_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, player_add_name)
            ],
            ST_WARNING_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, player_warn_reason)
            ],
            ST_NOTE_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, player_note_save)
            ],
            ST_EDIT_PLAYER_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, player_editname_save)
            ],
            ST_SEARCH_PLAYER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, player_search_run)
            ],
            ST_BULK_REG_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, bulk_register_text_received)
            ],
            ST_BULK_REG_PREVIEW: [
                CallbackQueryHandler(bulk_confirm, pattern="^bulk_confirm$"),
                CallbackQueryHandler(bulk_edit_start, pattern="^bulk_edit$"),
                CallbackQueryHandler(bulk_cancel, pattern="^bulk_cancel$"),
            ],
            ST_BULK_REG_EDIT_NUM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, bulk_edit_num_received)
            ],
            ST_BULK_REG_EDIT_VALUE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, bulk_edit_value_received)
            ],
        },
        fallbacks=[CallbackQueryHandler(back_players, pattern="^back_players$")],
        **CONV_KWARGS
    )

    # Match — مهم‌ترین
    match_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(match_add_start, pattern="^match_add$"),
            CallbackQueryHandler(lottery_manual, pattern="^lottery_manual$"),
            CallbackQueryHandler(lottery_confirm, pattern="^lottery_confirm_"),
            CallbackQueryHandler(match_hist_search_start, pattern="^mhist_search$"),
            CallbackQueryHandler(adv_lottery_start, pattern="^adv_lottery_start$"),
            CallbackQueryHandler(result_cancel_ask, pattern="^result_cancel_"),
        ],
        states={
            ST_MATCH_WHITE: [
                CallbackQueryHandler(match_white_page, pattern="^mwpage_"),
                CallbackQueryHandler(match_white_selected, pattern="^mwhite_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, match_white_search_text),
            ],
            ST_MATCH_BLACK: [
                CallbackQueryHandler(match_black_page, pattern="^mbpage_"),
                CallbackQueryHandler(match_black_selected, pattern="^mblack_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, match_black_search_text),
            ],
            ST_MATCH_DATE: [
                CallbackQueryHandler(match_date_today, pattern="^mdate_today$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, match_date_text),
            ],
            ST_MATCH_DRAW_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, draw_reason_text)
            ],
            ST_MATCH_CANCEL_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, match_cancel_reason_text)
            ],
            ST_SEARCH_MATCH: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, match_hist_search_run)
            ],
            ST_ADV_LOTTERY_SCOPE: [
                CallbackQueryHandler(adv_lottery_scope_chosen, pattern="^adv_scope_")
            ],
            ST_ADV_LOTTERY_CLASS_A: [
                CallbackQueryHandler(adv_lottery_classA_chosen, pattern="^adv_class_same_"),
                CallbackQueryHandler(adv_lottery_classA_chosen, pattern="^adv_classA_"),
            ],
            ST_ADV_LOTTERY_CLASS_B: [
                CallbackQueryHandler(adv_lottery_classB_chosen, pattern="^adv_classB_")
            ],
            ST_ADV_LOTTERY_COUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, adv_lottery_count_received)
            ],
        },
        fallbacks=[
            CallbackQueryHandler(back_matches, pattern="^back_matches$"),
            CommandHandler("start", cmd_start),
        ],
        **CONV_KWARGS
    )

    # Comms
    comms_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(comms_msg_admin_start, pattern="^comms_msg_admin$"),
            CallbackQueryHandler(comms_msg_pishva_start, pattern="^comms_msg_pishva$"),
            CallbackQueryHandler(comms_msg_other_start, pattern="^comms_msg_other$"),
            CallbackQueryHandler(comms_announce_start, pattern="^comms_announce$"),
            CallbackQueryHandler(comms_news_start, pattern="^comms_news$"),
            MessageHandler(filters.Regex(r"^بیانیه$"), kw_announce_start),
            MessageHandler(filters.Regex(r"^خبر$"), kw_news_start),
        ],
        states={
            ST_SEND_MSG_SELECT_ADMIN: [
                CallbackQueryHandler(comms_msg_target, pattern="^cmsg_")
            ],
            ST_SEND_MSG_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, comms_msg_send)
            ],
            ST_ANNOUNCEMENT_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, comms_announce_text)
            ],
            ST_ANNOUNCEMENT_FILE: [
                CallbackQueryHandler(comms_announce_no_file, pattern="^ann_no_file$"),
                CallbackQueryHandler(comms_announce_with_file, pattern="^ann_with_file$"),
                MessageHandler(
                    filters.PHOTO | filters.Document.ALL | filters.VIDEO |
                    filters.AUDIO | filters.VOICE,
                    comms_announce_file_received
                ),
            ],
            ST_NEWS_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, comms_news_send)
            ],
        },
        fallbacks=[CallbackQueryHandler(menu_comms, pattern="^menu_comms$")],
        **CONV_KWARGS
    )

    # Task
    task_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(task_assign_start, pattern="^task_assign$"),
            CallbackQueryHandler(admin_task_start, pattern="^admin_task_"),
            CallbackQueryHandler(task_fail_start, pattern="^task_fail_"),
            CommandHandler("ss", cmd_ss),
        ],
        states={
            ST_TASK_SELECT_ADMIN: [
                CallbackQueryHandler(task_to_admin, pattern="^task_to_")
            ],
            ST_TASK_TITLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, task_title_received)
            ],
            ST_TASK_DESC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, task_desc_received)
            ],
            ST_TASK_DONE_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, task_fail_reason)
            ],
        },
        fallbacks=[CallbackQueryHandler(menu_tasks, pattern="^menu_tasks$")],
        **CONV_KWARGS
    )

    # Feedback
    feedback_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(fb_start, pattern="^fb_(critique|suggestion|praise|feature)$"),
        ],
        states={
            ST_FEEDBACK_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, fb_text_received)
            ],
            ST_FEATURE_DESC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, fb_feature_desc)
            ],
        },
        fallbacks=[CallbackQueryHandler(menu_feedback, pattern="^menu_feedback$")],
        **CONV_KWARGS
    )

    # Pishva multi-step
    pishva_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(identity_pishva_start, pattern="^identity_pishva$"),
            CallbackQueryHandler(identity_admin_select, pattern="^identity_set_"),
            CallbackQueryHandler(newyear_yes, pattern="^newyear_yes$"),
            CallbackQueryHandler(repair_reason_start, pattern="^repair_reason$"),
            CallbackQueryHandler(pishva_group, pattern="^pishva_group$"),
            CallbackQueryHandler(pishva_channel, pattern="^pishva_channel$"),
            CallbackQueryHandler(update_announce_start, pattern="^update_announce$"),
            CallbackQueryHandler(admin_warn_start, pattern="^admin_warn_"),
            CallbackQueryHandler(admin_msg_start, pattern="^admin_msg_"),
        ],
        states={
            ST_PISHVA_NAME_CHANGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, identity_pishva_save)
            ],
            ST_ADMIN_NAME_CHANGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, identity_admin_save)
            ],
            ST_NEW_YEAR_PASSWORD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, newyear_password)
            ],
            ST_REPAIR_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, repair_reason_save)
            ],
            ST_GROUP_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, group_id_save)
            ],
            ST_CHANNEL_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, channel_id_save)
            ],
            ST_UPDATE_VERSION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, update_version_received)
            ],
            ST_UPDATE_DESC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, update_desc_received)
            ],
            ST_ADMIN_WARNING_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_warn_reason)
            ],
            ST_SEND_MSG_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, comms_msg_send)
            ],
        },
        fallbacks=[CallbackQueryHandler(menu_pishva, pattern="^menu_pishva$")],
        **CONV_KWARGS
    )

    # Restore (بازگردانی بکاپ)
    restore_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(pishva_restore_start, pattern="^pishva_restore$"),
        ],
        states={
            ST_RESTORE_FILE: [
                CallbackQueryHandler(restore_confirm_apply, pattern="^restore_apply$"),
                CallbackQueryHandler(restore_cancel, pattern="^restore_cancel$"),
                MessageHandler(filters.Document.ALL, restore_file_received),
            ],
        },
        fallbacks=[CallbackQueryHandler(pishva_backup, pattern="^pishva_backup$")],
        **CONV_KWARGS
    )

    # Team
    team_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(teams_add_start, pattern="^teams_add$")],
        states={
            ST_TEAM_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, team_name_received)
            ],
            ST_TEAM_SLOGAN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, team_slogan_received),
                CallbackQueryHandler(team_skip_slogan, pattern="^team_skip_slogan$"),
            ],
            ST_TEAM_MEMBERS: [
                CallbackQueryHandler(team_toggle_member, pattern="^tselect_"),
                CallbackQueryHandler(team_skip_members, pattern="^team_skip_members$"),
                CallbackQueryHandler(team_confirm_members, pattern="^team_confirm_members$"),
            ],
            ST_TEAM_DATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, team_date_text),
                CallbackQueryHandler(team_date_today, pattern="^team_date_today$"),
            ],
            ST_TEAM_REQUESTER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, team_requester_received)
            ],
        },
        fallbacks=[CallbackQueryHandler(teams_list, pattern="^teams_list$")],
        **CONV_KWARGS
    )

    # ساعت کاری: /open و دکمهٔ wh_start ممکنه (اگه پایان خودکار روشن باشه)
    # یه عدد دقیقه از مدیر ارشد بخوان، پس باید Conversation باشن نه هندلر ساده.
    workhours_conv = ConversationHandler(
        entry_points=[
            CommandHandler("open", workhour_start),
            CallbackQueryHandler(workhour_start, pattern="^wh_start$"),
            CallbackQueryHandler(workhours_reminder_minutes_start, pattern="^wh_reminder_set_minutes$"),
        ],
        states={
            ST_WORKHOURS_AUTOEND_MINUTES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, workhour_start_minutes_received)
            ],
            ST_WORKHOURS_REMINDER_MINUTES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, workhours_reminder_minutes_received)
            ],
        },
        fallbacks=[CallbackQueryHandler(pishva_workhours, pattern="^pishva_workhours$"),
                   CallbackQueryHandler(menu_pishva, pattern="^menu_pishva$")],
        **CONV_KWARGS
    )

    # ─── Add all ConversationHandlers first ───────────────────
    for conv in [auth_conv, tourn_conv, player_conv, match_conv,
                 comms_conv, task_conv, feedback_conv, pishva_conv, restore_conv, team_conv,
                 workhours_conv]:
        app.add_handler(conv)

    # ══════════════════════════════════════════
    # SLASH COMMANDS
    # ══════════════════════════════════════════
    app.add_handler(CommandHandler("panic", cmd_panic))
    app.add_handler(CommandHandler("unpanic", cmd_unpanic))
    app.add_handler(CommandHandler("freeze_all", cmd_freeze_all))
    app.add_handler(CommandHandler("terminal", cmd_terminal))
    app.add_handler(CommandHandler("backup_now", cmd_backup_now))
    app.add_handler(CommandHandler("override_strike", cmd_override_strike))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("close", workhour_end))

    # ══════════════════════════════════════════
    # GLOBAL CALLBACK HANDLERS
    # ══════════════════════════════════════════

    # Dashboard
    app.add_handler(CallbackQueryHandler(dashboard_pishva, pattern="^dashboard_pishva$"))
    app.add_handler(CallbackQueryHandler(dashboard_admin, pattern="^dashboard_admin$"))

    # Access requests
    app.add_handler(CallbackQueryHandler(on_approve_request, pattern="^req_approve_"))
    app.add_handler(CallbackQueryHandler(on_reject_request, pattern="^req_reject_"))

    # Navigation
    app.add_handler(CallbackQueryHandler(back_main, pattern="^back_main$"))
    app.add_handler(CallbackQueryHandler(refresh_dashboard, pattern="^refresh_dashboard$"))
    app.add_handler(CallbackQueryHandler(menu_tournament, pattern="^menu_tournament$"))
    app.add_handler(CallbackQueryHandler(menu_players, pattern="^menu_players$"))
    app.add_handler(CallbackQueryHandler(menu_matches, pattern="^menu_matches$"))
    app.add_handler(CallbackQueryHandler(menu_pishva, pattern="^menu_pishva$"))
    app.add_handler(CallbackQueryHandler(menu_comms, pattern="^menu_comms$"))
    app.add_handler(CallbackQueryHandler(menu_help, pattern="^menu_help$"))
    app.add_handler(CallbackQueryHandler(menu_admins, pattern="^menu_admins$"))
    app.add_handler(CallbackQueryHandler(menu_tasks, pattern="^menu_tasks$"))
    app.add_handler(CallbackQueryHandler(menu_feedback, pattern="^menu_feedback$"))
    app.add_handler(CallbackQueryHandler(back_tournament, pattern="^back_tournament$"))
    app.add_handler(CallbackQueryHandler(back_players, pattern="^back_players$"))
    app.add_handler(CallbackQueryHandler(back_matches, pattern="^back_matches$"))
    app.add_handler(CallbackQueryHandler(back_class_manage,pattern="^class_manage$"))
    app.add_handler(CallbackQueryHandler(back_player_list, pattern="^back_player_list$"))
    app.add_handler(CallbackQueryHandler(back_teams_menu, pattern="^back_teams_menu$"))

    # Tournament
    app.add_handler(CallbackQueryHandler(tourn_menu, pattern="^tourn_menu$"))
    app.add_handler(CallbackQueryHandler(tourn_manage, pattern="^tourn_manage$"))
    app.add_handler(CallbackQueryHandler(tourn_select, pattern="^tourn_select_"))
    app.add_handler(CallbackQueryHandler(tourn_end, pattern="^tourn_end_"))
    app.add_handler(CallbackQueryHandler(tourn_pause, pattern="^tourn_pause_"))
    app.add_handler(CallbackQueryHandler(tourn_delete, pattern="^tourn_delete_"))
    app.add_handler(CallbackQueryHandler(tourn_setdefault,pattern="^tourn_setdefault_"))
    app.add_handler(CallbackQueryHandler(tourn_default, pattern="^tourn_default$"))
    app.add_handler(CallbackQueryHandler(tourn_details, pattern="^tourn_details$"))
    app.add_handler(CallbackQueryHandler(tourn_deleted, pattern="^tourn_deleted$"))

    # Classes
    app.add_handler(CallbackQueryHandler(class_list, pattern="^class_list$"))
    app.add_handler(CallbackQueryHandler(class_select, pattern="^class_select_"))
    app.add_handler(CallbackQueryHandler(class_players, pattern="^class_players_"))
    app.add_handler(CallbackQueryHandler(class_perf, pattern="^class_perf_"))

    # Players
    app.add_handler(CallbackQueryHandler(player_list, pattern="^player_list$"))
    app.add_handler(CallbackQueryHandler(player_list_page, pattern="^player_list_page_"))
    app.add_handler(CallbackQueryHandler(player_view, pattern="^player_view_"))
    app.add_handler(CallbackQueryHandler(player_kick, pattern="^player_kick_"))
    app.add_handler(CallbackQueryHandler(player_suspend, pattern="^player_suspend_"))
    app.add_handler(CallbackQueryHandler(player_revive, pattern="^player_revive_"))
    app.add_handler(CallbackQueryHandler(player_elite_set, pattern="^player_elite_"))
    app.add_handler(CallbackQueryHandler(player_special_set,pattern="^player_special_"))
    app.add_handler(CallbackQueryHandler(player_setclass, pattern="^setclass_"))
    app.add_handler(CallbackQueryHandler(player_continuing, pattern="^player_continuing$"))
    app.add_handler(CallbackQueryHandler(player_eliminated, pattern="^player_eliminated$"))
    app.add_handler(CallbackQueryHandler(player_list_kicked,pattern="^player_list_kicked$"))
    app.add_handler(CallbackQueryHandler(player_list_elim, pattern="^player_list_elim$"))
    app.add_handler(CallbackQueryHandler(player_elite_list, pattern="^player_elite$"))
    app.add_handler(CallbackQueryHandler(player_special_list,pattern="^player_special$"))
    app.add_handler(CallbackQueryHandler(player_join_team, pattern="^player_jointeam_"))
    app.add_handler(CallbackQueryHandler(player_no_team, pattern="^player_noteam_"))

    # Matches (non-conversation)
    app.add_handler(CallbackQueryHandler(match_result_menu, pattern="^match_result$"))
    app.add_handler(CallbackQueryHandler(match_result_page, pattern="^mrpage_"))
    app.add_handler(CallbackQueryHandler(match_result_select,pattern="^result_select_"))
    app.add_handler(CallbackQueryHandler(result_white, pattern="^result_white_"))
    app.add_handler(CallbackQueryHandler(result_black, pattern="^result_black_"))
    app.add_handler(CallbackQueryHandler(result_draw, pattern="^result_draw_"))
    app.add_handler(CallbackQueryHandler(draw_reason, pattern="^draw_(pat|time|moves|repeat|other)_"))
    app.add_handler(CallbackQueryHandler(eliminate_yes, pattern="^eliminate_yes_"))
    app.add_handler(CallbackQueryHandler(eliminate_no, pattern="^eliminate_no_"))
    app.add_handler(CallbackQueryHandler(match_history, pattern="^match_history$"))
    app.add_handler(CallbackQueryHandler(match_hist_filter, pattern="^mhist_(today|week|month|all)$"))
    app.add_handler(CallbackQueryHandler(match_full_history, pattern="^match_full_history$"))
    app.add_handler(CallbackQueryHandler(match_view, pattern="^match_view_"))
    app.add_handler(CallbackQueryHandler(match_delete, pattern="^match_delete_"))
    app.add_handler(CallbackQueryHandler(match_pin, pattern="^match_pin_"))
    app.add_handler(CallbackQueryHandler(match_panel, pattern="^match_panel$"))
    app.add_handler(CallbackQueryHandler(lottery_start, pattern="^lottery_start$"))
    app.add_handler(CallbackQueryHandler(lottery_all, pattern="^lottery_all$"))
    app.add_handler(CallbackQueryHandler(lottery_class_select,pattern="^lottery_class$"))
    app.add_handler(CallbackQueryHandler(lottery_class_chosen,pattern="^lclass_"))
    app.add_handler(CallbackQueryHandler(lottery_redo, pattern="^lottery_redo$"))
    app.add_handler(CallbackQueryHandler(adv_lottery_confirm, pattern="^adv_lottery_confirm$"))
    app.add_handler(CallbackQueryHandler(adv_lottery_redo, pattern="^adv_lottery_redo$"))
    app.add_handler(CallbackQueryHandler(adv_lottery_cancel, pattern="^adv_lottery_cancel$"))

    # Pishva panel
    app.add_handler(CallbackQueryHandler(pishva_status, pattern="^pishva_status$"))
    app.add_handler(CallbackQueryHandler(pishva_dbstatus, pattern="^pishva_dbstatus$"))
    app.add_handler(CallbackQueryHandler(dbstatus_on, pattern="^dbstatus_on$"))
    app.add_handler(CallbackQueryHandler(dbstatus_off, pattern="^dbstatus_off$"))
    app.add_handler(CallbackQueryHandler(set_status, pattern="^set_status_"))
    app.add_handler(CallbackQueryHandler(pishva_settings, pattern="^pishva_settings$"))
    app.add_handler(CallbackQueryHandler(toggle_setting, pattern="^setting_"))
    app.add_handler(CallbackQueryHandler(pishva_logs, pattern="^pishva_logs$"))
    app.add_handler(CallbackQueryHandler(show_logs, pattern="^logs_(today|week|month|all)$"))
    app.add_handler(CallbackQueryHandler(pishva_requests, pattern="^pishva_requests$"))
    app.add_handler(CallbackQueryHandler(pishva_backup, pattern="^pishva_backup$"))
    app.add_handler(CallbackQueryHandler(backup_period_select,pattern="^backup_period_"))
    app.add_handler(CallbackQueryHandler(backup_format_select,pattern="^backup_fmt_"))
    app.add_handler(CallbackQueryHandler(pishva_workhours, pattern="^pishva_workhours$"))
    app.add_handler(CallbackQueryHandler(workhour_end, pattern="^wh_end$"))
    app.add_handler(CallbackQueryHandler(workhours_autoend_toggle, pattern="^wh_autoend_toggle$"))
    app.add_handler(CallbackQueryHandler(workhours_reminder_toggle, pattern="^wh_reminder_toggle$"))
    # wh_start و wh_reminder_set_minutes به‌عنوان entry_points توی workhours_conv ثبت شدن
    app.add_handler(CallbackQueryHandler(pishva_repair, pattern="^pishva_repair$"))
    app.add_handler(CallbackQueryHandler(repair_on, pattern="^repair_on$"))
    app.add_handler(CallbackQueryHandler(repair_off, pattern="^repair_off$"))
    app.add_handler(CallbackQueryHandler(pishva_identity, pattern="^pishva_identity$"))
    app.add_handler(CallbackQueryHandler(identity_admin_start,pattern="^identity_admin$"))
    app.add_handler(CallbackQueryHandler(pishva_newyear, pattern="^pishva_newyear$"))
    app.add_handler(CallbackQueryHandler(pishva_update, pattern="^pishva_update$"))
    app.add_handler(CallbackQueryHandler(update_sleep, pattern="^update_sleep$"))
    app.add_handler(CallbackQueryHandler(pishva_vault, pattern="^pishva_vault$"))
    app.add_handler(CallbackQueryHandler(security_panel, pattern="^security_panel$"))
    app.add_handler(CallbackQueryHandler(security_queue_list, pattern="^security_queue$"))
    app.add_handler(CallbackQueryHandler(security_queue_item, pattern="^queueview_"))
    app.add_handler(CallbackQueryHandler(request_to_queue, pattern="^req_queue_"))
    app.add_handler(CallbackQueryHandler(queue_approve, pattern="^queueapprove_"))
    app.add_handler(CallbackQueryHandler(queue_release, pattern="^queuerelease_"))
    app.add_handler(CallbackQueryHandler(queue_block_ask, pattern="^queueblockask_"))
    app.add_handler(CallbackQueryHandler(request_block_ask, pattern="^req_blockask_"))
    app.add_handler(CallbackQueryHandler(block_confirm, pattern="^blockconfirm_"))
    app.add_handler(CallbackQueryHandler(security_blocked_list, pattern="^security_blocked$"))
    app.add_handler(CallbackQueryHandler(security_blocked_item, pattern="^blockedview_"))
    app.add_handler(CallbackQueryHandler(unblock_action, pattern="^unblock_"))
    app.add_handler(CallbackQueryHandler(pishva_reminders, pattern="^pishva_reminders$"))
    app.add_handler(CallbackQueryHandler(reminder_toggle, pattern="^reminder_toggle_"))
    app.add_handler(CallbackQueryHandler(reminder_interval_menu, pattern="^reminder_interval_"))
    app.add_handler(CallbackQueryHandler(reminder_set_interval, pattern="^reminder_set_"))
    app.add_handler(CallbackQueryHandler(pishva_broadcast, pattern="^pishva_broadcast$"))
    app.add_handler(CallbackQueryHandler(broadcast_toggle, pattern="^broadcast_toggle_"))
    app.add_handler(CallbackQueryHandler(_noop_callback, pattern="^noop_label$"))

    # Comms
    app.add_handler(CallbackQueryHandler(comms_inbox, pattern="^comms_inbox$"))
    app.add_handler(CallbackQueryHandler(comms_all_msgs, pattern="^comms_all_msgs$"))
    app.add_handler(CallbackQueryHandler(comms_ann_history, pattern="^comms_ann_history$"))
    app.add_handler(CallbackQueryHandler(ann_view, pattern="^ann_view_"))
    app.add_handler(CallbackQueryHandler(ann_delete, pattern="^ann_delete_"))
    app.add_handler(CallbackQueryHandler(comms_news_list, pattern="^comms_news_list$"))
    app.add_handler(CallbackQueryHandler(comms_notifs, pattern="^comms_notifs$"))
    app.add_handler(CallbackQueryHandler(comms_reports, pattern="^comms_reports$"))
    app.add_handler(CallbackQueryHandler(msg_ack, pattern="^msg_ack$"))

    # Tasks
    app.add_handler(CallbackQueryHandler(task_track, pattern="^task_track$"))
    app.add_handler(CallbackQueryHandler(task_view, pattern="^task_view_"))
    app.add_handler(CallbackQueryHandler(task_ack, pattern="^task_ack_"))
    app.add_handler(CallbackQueryHandler(task_done, pattern="^task_done_"))
    app.add_handler(CallbackQueryHandler(task_followup, pattern="^task_followup_"))
    app.add_handler(CallbackQueryHandler(task_history, pattern="^task_history$"))
    app.add_handler(CallbackQueryHandler(task_history_filter,pattern="^thistory_"))

    # Admin management
    app.add_handler(CallbackQueryHandler(admin_view, pattern="^admin_view_"))
    app.add_handler(CallbackQueryHandler(admin_perms, pattern="^admin_perms_"))
    app.add_handler(CallbackQueryHandler(perm_toggle, pattern="^perm_"))
    app.add_handler(CallbackQueryHandler(admin_kick, pattern="^admin_kick_"))
    app.add_handler(CallbackQueryHandler(admin_clear_warnings, pattern="^admin_clearwarn_"))

    # Feedback
    app.add_handler(CallbackQueryHandler(fb_view, pattern="^fb_view_"))

    # Help center
    app.add_handler(CallbackQueryHandler(help_main, pattern="^menu_help$"))
    app.add_handler(CallbackQueryHandler(help_tutorial, pattern="^htut_"))

    # New features — Elo, Champions, Bracket, Prediction
    app.add_handler(CallbackQueryHandler(show_elo_leaderboard, pattern="^elo_leaderboard$"))
    app.add_handler(CallbackQueryHandler(show_elo_info, pattern="^elo_info$"))
    app.add_handler(CallbackQueryHandler(show_player_elo_panel, pattern="^elo_player_"))
    app.add_handler(CallbackQueryHandler(show_prediction_select, pattern="^predict_select_"))
    app.add_handler(CallbackQueryHandler(show_prediction, pattern="^predict_[0-9]+_[0-9]+$"))
    app.add_handler(CallbackQueryHandler(show_champions, pattern="^champions$"))
    app.add_handler(CallbackQueryHandler(show_bracket, pattern="^match_bracket$"))

    # Auto-backup
    app.add_handler(CallbackQueryHandler(pishva_auto_backup, pattern="^pishva_auto_backup$"))
    app.add_handler(CallbackQueryHandler(auto_backup_toggle, pattern="^abk_toggle$"))
    app.add_handler(CallbackQueryHandler(auto_backup_interval_menu, pattern="^abk_interval$"))
    app.add_handler(CallbackQueryHandler(auto_backup_set_interval, pattern="^abk_set_interval_"))
    app.add_handler(CallbackQueryHandler(auto_backup_fmt_toggle, pattern="^abk_fmt$"))
    app.add_handler(CallbackQueryHandler(auto_backup_period_toggle, pattern="^abk_period$"))

    # Teams
    app.add_handler(CallbackQueryHandler(teams_menu, pattern="^teams_menu$"))
    app.add_handler(CallbackQueryHandler(teams_menu, pattern="^team_matches_menu$"))
    app.add_handler(CallbackQueryHandler(teams_list, pattern="^teams_list$"))
    app.add_handler(CallbackQueryHandler(team_view, pattern="^team_view_"))
    app.add_handler(CallbackQueryHandler(team_members_view, pattern="^team_members_"))
    app.add_handler(CallbackQueryHandler(team_member_actions,pattern="^tmember_"))
    app.add_handler(CallbackQueryHandler(team_remove_member, pattern="^tremove_"))
    app.add_handler(CallbackQueryHandler(team_captain_start, pattern="^team_captain_[0-9]+$"))
    app.add_handler(CallbackQueryHandler(team_captain_set, pattern="^tcaptain_set_"))
    app.add_handler(CallbackQueryHandler(team_delete, pattern="^team_delete_"))
    app.add_handler(CallbackQueryHandler(team_warnings_view, pattern="^team_warnings_"))
    app.add_handler(CallbackQueryHandler(teams_settings, pattern="^teams_settings$"))

    # ══════════════════════════════════════════
    # کلمات کلیدی — قبل از ConversationHandlerها اجرا می‌شود
    # ══════════════════════════════════════════
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_keyword_command),
        group=-2
    )

    # ══════════════════════════════════════════
    # دستیار هوشمند (Gemini)
    # ══════════════════════════════════════════
    app.add_handler(CallbackQueryHandler(ai_assistant_open, pattern="^ai_assistant_open$"))
    app.add_handler(CallbackQueryHandler(ai_exit, pattern="^ai_exit$"))
    app.add_handler(CallbackQueryHandler(ai_menu_close, pattern="^ai_menu_close$"))
    app.add_handler(CallbackQueryHandler(ai_menu, pattern="^ai_menu$"))
    app.add_handler(CallbackQueryHandler(ai_new_start, pattern="^ai_new_start$"))
    app.add_handler(CallbackQueryHandler(ai_hist_list, pattern="^ai_hist_list$"))
    app.add_handler(CallbackQueryHandler(ai_hist_open, pattern="^ai_hist_open_"))
    app.add_handler(CallbackQueryHandler(ai_admlog_menu, pattern="^ai_admlog_menu$"))
    app.add_handler(CallbackQueryHandler(ai_admlog_pick, pattern="^ai_admlog_pick_"))
    app.add_handler(CallbackQueryHandler(ai_admlog_range, pattern="^ai_admlog_range_"))
    app.add_handler(CallbackQueryHandler(ai_admlog_view, pattern="^ai_admlog_view_"))
    # بعد از همه‌ی هندلرهای دیگر (کلمات کلیدی، مکالمه‌ها) بررسی می‌شود
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, ai_assistant_message),
        group=1
    )

    # 🔙 دروازه‌ی عمومی «بازگشت» — عمداً آخرین ثبت‌شونده در group=0 است
    # تا فقط برای back_... هایی اجرا بشه که هندلر اختصاصی‌شون بالاتر
    # پیدا نشده (اولویت با هندلرهای اختصاصی‌ست).
    app.add_handler(CallbackQueryHandler(universal_back_router, pattern="^back_"))

    return app


def main():
    app = build_application()
    logger.info("Starting bot polling...")
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
