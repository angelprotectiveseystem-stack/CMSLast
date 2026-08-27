from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import BOT_USERNAME

# ─── Auth ─────────────────────────────────────────────────────
def kb_role_select():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👑 رییس کل", callback_data="role_pishva"),
        InlineKeyboardButton("🏆 مدیر مسابقات", callback_data="role_tournament")],
        [InlineKeyboardButton("🛡️ مدیر امنیتی", callback_data="role_security")],
    ])

def kb_back(target="main"):
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data=f"back_{target}")]])

def kb_back_row(target="main"):
    return [InlineKeyboardButton("🔙 بازگشت", callback_data=f"back_{target}")]

# ─── پنل پیشوا (منوی اصلی کوتاه) ────────────────────────────
def kb_pishva_main():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("♟️ مدیریت مسابقات", callback_data="menu_matches"),
        InlineKeyboardButton("👤 مدیریت بازیکنان", callback_data="menu_players")],
        [InlineKeyboardButton("👑 پنل پیشوا", callback_data="menu_pishva"),
        InlineKeyboardButton("👥 مدیریت مدیران", callback_data="menu_admins")],
        [InlineKeyboardButton("📡 مخابرات", callback_data="menu_comms"),
        InlineKeyboardButton("📋 وظایف", callback_data="menu_tasks")],
        [InlineKeyboardButton("📊 داشبورد پیشوا", callback_data="dashboard_pishva"),
        InlineKeyboardButton("❓ راهنما", callback_data="menu_help")],
        [InlineKeyboardButton("🗄️ وضعیت دیتابیس", callback_data="pishva_dbstatus")],
        [InlineKeyboardButton("🤖 دستیار هوشمند", callback_data="ai_assistant_open")],
        [InlineKeyboardButton("💡 انتقادات و پیشنهادات", callback_data="menu_feedback")],
    ])

# ─── منوی مدیر مسابقات ────────────────────────────────────────
def kb_tournament_manager_main():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("♟️ مدیریت مسابقات", callback_data="menu_matches"),
        InlineKeyboardButton("👤 مدیریت بازیکنان", callback_data="menu_players")],
        [InlineKeyboardButton("📊 داشبورد من", callback_data="dashboard_admin"),
        InlineKeyboardButton("📡 مخابرات", callback_data="menu_comms")],
        [InlineKeyboardButton("📋 وظایف", callback_data="menu_tasks"),
        InlineKeyboardButton("❓ راهنما", callback_data="menu_help")],
        [InlineKeyboardButton("🤖 دستیار هوشمند", callback_data="ai_assistant_open")],
        [InlineKeyboardButton("💡 انتقادات و پیشنهادات", callback_data="menu_feedback")],
    ])

# ─── منوی مدیر امنیتی ─────────────────────────────────────────
def kb_security_manager_main():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 مدیریت بازیکنان", callback_data="menu_players"),
        InlineKeyboardButton("📊 داشبورد من", callback_data="dashboard_admin")],
        [InlineKeyboardButton("📡 مخابرات", callback_data="menu_comms"),
        InlineKeyboardButton("📋 وظایف", callback_data="menu_tasks")],
        [InlineKeyboardButton("❓ راهنما", callback_data="menu_help"),
        InlineKeyboardButton("💡 انتقادات و پیشنهادات", callback_data="menu_feedback")],
        [InlineKeyboardButton("🤖 دستیار هوشمند", callback_data="ai_assistant_open")],
    ])

# ─── مدیریت مسابقات (همه چیز اینجاست) ──────────────────────
def kb_matches_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ ثبت مسابقه جدید", callback_data="match_add"),
        InlineKeyboardButton("🏆 ثبت نتیجه", callback_data="match_result")],
        [InlineKeyboardButton("🔍 تاریخچه مسابقات", callback_data="match_history"),
        InlineKeyboardButton("📊 پنل مدیریت", callback_data="match_panel")],
        [InlineKeyboardButton("🎲 قرعه‌کشی", callback_data="lottery_start"),
        InlineKeyboardButton("🎯 قرعه‌کشی پیشرفته", callback_data="adv_lottery_start")],
        [InlineKeyboardButton("📋 جدول مسابقات", callback_data="match_bracket")],
        [InlineKeyboardButton("🏅 تورنمنت‌ها", callback_data="menu_tournament"),
        InlineKeyboardButton("🏆 تیم‌ها", callback_data="teams_menu")],
        [InlineKeyboardButton("📊 جدول Elo", callback_data="elo_leaderboard"),
        InlineKeyboardButton("👑 قهرمانان", callback_data="champions")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")],
    ])

# ─── مدیریت بازیکنان ─────────────────────────────────────────
def kb_players_menu(role="pishva"):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ ثبت‌نام بازیکن", callback_data="player_add"),
        InlineKeyboardButton("🏫 مدیریت کلاس‌ها", callback_data="class_manage")],
        [InlineKeyboardButton("📋 ثبت‌نام گروهی", callback_data="bulk_register_start")],
        [InlineKeyboardButton("👁️ مشاهده بازیکنان", callback_data="player_list"),
        InlineKeyboardButton("🔍 جستجو بازیکن", callback_data="player_search")],
        [InlineKeyboardButton("✅ ادامه‌دهندگان", callback_data="player_continuing"),
        InlineKeyboardButton("❌ حذف‌شدگان", callback_data="player_eliminated")],
        [InlineKeyboardButton("🌟 بازیکنان برتر", callback_data="player_elite"),
        InlineKeyboardButton("⚡ نیروهای ویژه", callback_data="player_special")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")],
    ])

# ─── کلاس ────────────────────────────────────────────────────
def kb_class_manage():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ ثبت کلاس جدید", callback_data="class_add"),
        InlineKeyboardButton("👁️ مشاهده کلاس‌ها", callback_data="class_list")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="back_players")],
    ])

def kb_class_list(classes):
    rows = []
    for i in range(0, len(classes), 2):
        row = [InlineKeyboardButton(f"🏫 {c['name']}", callback_data=f"class_select_{c['id']}") for c in classes[i:i+2]]
        rows.append(row)
    rows.append(kb_back_row("class_manage"))
    return InlineKeyboardMarkup(rows)

def kb_class_actions(class_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 بازیکنان کلاس", callback_data=f"class_players_{class_id}"),
        InlineKeyboardButton("✏️ ویرایش نام", callback_data=f"class_edit_{class_id}")],
        [InlineKeyboardButton("📈 عملکرد کلاس", callback_data=f"class_perf_{class_id}"),
        InlineKeyboardButton("🔙 بازگشت", callback_data="class_list")],
    ])

# ─── بازیکنان ─────────────────────────────────────────────────
def kb_player_list(players, page=0, page_size=8):
    start = page * page_size
    chunk = players[start:start+page_size]
    rows = []
    for i in range(0, len(chunk), 2):
        row = []
        for p in chunk[i:i+2]:
            icon = "⛔" if p["status"]=="eliminated" else "🚫" if p["status"]=="suspended" else "❌" if p["status"]=="kicked" else "🟢"
            row.append(InlineKeyboardButton(f"{icon} {p['full_name']}", callback_data=f"player_view_{p['id']}"))
        rows.append(row)
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ قبلی", callback_data=f"player_list_page_{page-1}"))
    if start + page_size < len(players):
        nav.append(InlineKeyboardButton("▶️ بعدی", callback_data=f"player_list_page_{page+1}"))
    if nav:
        rows.append(nav)
    rows.append(kb_back_row("players"))
    return InlineKeyboardMarkup(rows)

def kb_player_select(players, prefix, back="matches", page=0, page_size=8, nav_prefix=None):
    total = len(players)
    start = page * page_size
    page_players = players[start:start + page_size]
    rows = []
    for i in range(0, len(page_players), 2):
        row = [InlineKeyboardButton(
            f"{'⬜' if 'white' in prefix else '⬛' if 'black' in prefix else '👤'} {p['full_name']} [{p['class_name'] if p['class_name'] else ''}]",
            callback_data=f"{prefix}_{p['id']}"
        ) for p in page_players[i:i + 2]]
        rows.append(row)
    if nav_prefix:
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton("◀️ قبلی", callback_data=f"{nav_prefix}page_{page-1}"))
        if start + page_size < total:
            nav_row.append(InlineKeyboardButton("بعدی ▶️", callback_data=f"{nav_prefix}page_{page+1}"))
        if nav_row:
            rows.append(nav_row)
    rows.append(kb_back_row(back))
    return InlineKeyboardMarkup(rows)

def kb_player_actions(player_id, role="pishva"):
    rows = [
        [InlineKeyboardButton("✏️ ویرایش نام", callback_data=f"player_editname_{player_id}"),
        InlineKeyboardButton("🏫 ویرایش کلاس", callback_data=f"player_editclass_{player_id}")],
        [InlineKeyboardButton("⚠️ ثبت اخطار", callback_data=f"player_warn_{player_id}"),
        InlineKeyboardButton("🚫 اخراج", callback_data=f"player_kick_{player_id}")],
        [InlineKeyboardButton("⏸️ تعلیق", callback_data=f"player_suspend_{player_id}"),
        InlineKeyboardButton("📝 یادداشت", callback_data=f"player_note_{player_id}")],
        [InlineKeyboardButton("🔄 احیا", callback_data=f"player_revive_{player_id}"),
        InlineKeyboardButton("🌟 ثبت برتر", callback_data=f"player_elite_{player_id}")],
        [InlineKeyboardButton("📈 امتیاز Elo", callback_data=f"elo_player_{player_id}"),
        InlineKeyboardButton("🔮 پیش‌بینی", callback_data=f"predict_select_{player_id}")],
    ]
    if role == "pishva":
        rows.append([InlineKeyboardButton("⚡ ثبت ویژه", callback_data=f"player_special_{player_id}")])
    rows.append(kb_back_row("player_list"))
    return InlineKeyboardMarkup(rows)

# ─── تورنمنت ──────────────────────────────────────────────────
def kb_tournament_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ افزودن تورنمنت", callback_data="tourn_add"),
        InlineKeyboardButton("⚙️ مدیریت تورنمنت", callback_data="tourn_manage")],
        [InlineKeyboardButton("📌 تورنمنت پیش‌فرض", callback_data="tourn_default"),
        InlineKeyboardButton("📊 جزئیات فعال", callback_data="tourn_details")],
        [InlineKeyboardButton("🗂️ حذف‌شده‌ها", callback_data="tourn_deleted"),
        InlineKeyboardButton("🔙 بازگشت", callback_data="back_matches")],
    ])

def kb_tournament_actions(tid, is_pishva=False):
    rows = [
        [InlineKeyboardButton("✏️ ویرایش نام", callback_data=f"tourn_edit_{tid}"),
        InlineKeyboardButton("🔴 پایان تورنمنت", callback_data=f"tourn_end_{tid}")],
        [InlineKeyboardButton("⏸️ به تعویق", callback_data=f"tourn_pause_{tid}"),
        InlineKeyboardButton("📌 تنظیم پیش‌فرض", callback_data=f"tourn_setdefault_{tid}")],
    ]
    if is_pishva:
        rows.append([InlineKeyboardButton("🗑️ حذف تورنمنت", callback_data=f"tourn_delete_{tid}")])
    rows.append(kb_back_row("tournament"))
    return InlineKeyboardMarkup(rows)

def kb_tournament_list(tournaments):
    rows = []
    for i in range(0, len(tournaments), 2):
        row = [InlineKeyboardButton(
            f"{'🟢' if t['status']=='active' else '⏸️' if t['status']=='paused' else '🔴'} {t['name']}",
            callback_data=f"tourn_select_{t['id']}"
        ) for t in tournaments[i:i+2]]
        rows.append(row)
    rows.append(kb_back_row("tournament"))
    return InlineKeyboardMarkup(rows)

# ─── مسابقات ──────────────────────────────────────────────────
def kb_match_result_options(match_id, white_name, black_name):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🥇 برد {white_name}", callback_data=f"result_white_{match_id}")],
        [InlineKeyboardButton(f"🥇 برد {black_name}", callback_data=f"result_black_{match_id}")],
        [InlineKeyboardButton("🤝 تساوی", callback_data=f"result_draw_{match_id}")],
        [InlineKeyboardButton("❌ لغو مسابقه", callback_data=f"result_cancel_{match_id}")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="match_result")],
    ])

def kb_draw_reasons(match_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔒 پات", callback_data=f"draw_pat_{match_id}"),
        InlineKeyboardButton("⏱️ اتمام زمان", callback_data=f"draw_time_{match_id}")],
        [InlineKeyboardButton("♾️ حرکات بسیار", callback_data=f"draw_moves_{match_id}"),
        InlineKeyboardButton("🔁 سه تکرار", callback_data=f"draw_repeat_{match_id}")],
        [InlineKeyboardButton("📝 سایر موارد", callback_data=f"draw_other_{match_id}")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="match_result")],
    ])

def kb_eliminate_ask(loser_id, loser_name):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"✅ بله، {loser_name} حذف شود", callback_data=f"eliminate_yes_{loser_id}"),
        InlineKeyboardButton("❌ خیر، ادامه دهد", callback_data=f"eliminate_no_{loser_id}")],
    ])

def kb_match_history_filter():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 امروز", callback_data="mhist_today"),
        InlineKeyboardButton("📆 این هفته", callback_data="mhist_week")],
        [InlineKeyboardButton("🗓️ این ماه", callback_data="mhist_month"),
        InlineKeyboardButton("📚 کل مسابقات", callback_data="mhist_all")],
        [InlineKeyboardButton("🔍 جستجو", callback_data="mhist_search"),
        InlineKeyboardButton("🔙 بازگشت", callback_data="back_matches")],
    ])

def kb_match_list(matches):
    rows = []
    for m in matches[:20]:
        res = {"white": "⬜🥇", "black": "⬛🥇", "draw": "🤝", None: "⏳"}.get(m["result"], "⏳")
        label = f"{res} {m['white_name']} ⚔️ {m['black_name']}"
        rows.append([InlineKeyboardButton(label, callback_data=f"match_view_{m['id']}")])
    rows.append(kb_back_row("match_history"))
    return InlineKeyboardMarkup(rows)

def kb_match_item_actions(mid):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ ویرایش", callback_data=f"match_edit_{mid}"),
        InlineKeyboardButton("🗑️ حذف", callback_data=f"match_delete_{mid}")],
        [InlineKeyboardButton("📌 پین کردن", callback_data=f"match_pin_{mid}"),
        InlineKeyboardButton("🔙 بازگشت", callback_data="match_history")],
    ])

# ─── پنل پیشوا ────────────────────────────────────────────────
def kb_pishva_panel():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚦 مدیریت وضعیت", callback_data="pishva_status"),
        InlineKeyboardButton("⚙️ تنظیمات ربات", callback_data="pishva_settings")],
        [InlineKeyboardButton("🔍 پیگیری اقدامات", callback_data="pishva_logs"),
        InlineKeyboardButton("📥 درخواست‌های دسترسی", callback_data="pishva_requests")],
        [InlineKeyboardButton("💾 دریافت بکاپ", callback_data="pishva_backup"),
        InlineKeyboardButton("🕐 ساعت کاری", callback_data="pishva_workhours")],
        [InlineKeyboardButton("🔧 حالت تعمیر", callback_data="pishva_repair"),
        InlineKeyboardButton("🏦 خزانه پیشوا", callback_data="pishva_vault")],
        [InlineKeyboardButton("🪪 تغییر هویت", callback_data="pishva_identity"),
        InlineKeyboardButton("🎓 سال تحصیلی جدید", callback_data="pishva_newyear")],
        [InlineKeyboardButton("🔄 آپدیت ربات", callback_data="pishva_update"),
        InlineKeyboardButton("📡 گروه اعلانات", callback_data="pishva_group")],
        [InlineKeyboardButton("⏰ یادآورها", callback_data="pishva_reminders"),
        InlineKeyboardButton("📢 افزودن به کانال", url=f"https://t.me/{BOT_USERNAME}?startchannel&admin=post_messages")],
        [InlineKeyboardButton("🆔 تنظیم کانال اعلانات", callback_data="pishva_channel"),
        InlineKeyboardButton("📡 پخش خودکار", callback_data="pishva_broadcast")],
        [InlineKeyboardButton("🛡️ پنل امنیتی APS", callback_data="security_panel")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")],
    ])

def kb_status_select(current):
    def icon(s): return "✅ " if s == current else ""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{icon('normal')}🟢 نرمال", callback_data="set_status_normal"),
        InlineKeyboardButton(f"{icon('bad')}🟡 بد", callback_data="set_status_bad")],
        [InlineKeyboardButton(f"{icon('danger')}🔴 خطرناک", callback_data="set_status_danger"),
        InlineKeyboardButton(f"{icon('aps')}🪽 APS", callback_data="set_status_aps")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="menu_pishva")],
    ])

def kb_pishva_settings_simple(settings):
    def tog(k): return "✅" if settings.get(k) == "1" else "❌"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🔔 اعلانات {tog('notifications_enabled')}", callback_data="setting_notifications"),
        InlineKeyboardButton(f"📡 مخابرات {tog('communications_enabled')}", callback_data="setting_communications")],
        [InlineKeyboardButton(f"❓ راهنما {tog('help_enabled')}", callback_data="setting_help"),
        InlineKeyboardButton(f"♟️ ثبت مسابقه {tog('match_registration_enabled')}", callback_data="setting_match_reg")],
        [InlineKeyboardButton(f"🚪 ورود ادمین {tog('admin_login_enabled')}", callback_data="setting_admin_login"),
        InlineKeyboardButton(f"💤 خاموش برای ادمین‌ها {tog('bot_active_for_admins')}", callback_data="setting_bot_active")],
        [InlineKeyboardButton(f"🏆 حالت تیمی {tog('team_mode_enabled')}", callback_data="setting_team_mode"),
        InlineKeyboardButton(f"📝 ثبت‌نام با تیم {tog('team_registration_enabled')}", callback_data="setting_team_reg")],
        [InlineKeyboardButton(f"👤 مدیران سازنده تیم {tog('managers_can_create_teams')}", callback_data="setting_mgr_team")],
        [InlineKeyboardButton(f"📊 داشبورد ادمین‌ها {tog('admin_dashboard_enabled')}", callback_data="setting_admin_dashboard")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="menu_pishva")],
    ])

def kb_backup_period():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 امروز", callback_data="backup_period_today"),
        InlineKeyboardButton("📆 این هفته", callback_data="backup_period_week")],
        [InlineKeyboardButton("🗓️ این ماه", callback_data="backup_period_month"),
        InlineKeyboardButton("📚 از ابتدا", callback_data="backup_period_all")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="menu_pishva")],
    ])

def kb_backup_main():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 امروز", callback_data="backup_period_today"),
        InlineKeyboardButton("📆 این هفته", callback_data="backup_period_week")],
        [InlineKeyboardButton("🗓️ این ماه", callback_data="backup_period_month"),
        InlineKeyboardButton("📚 از ابتدا", callback_data="backup_period_all")],
        [InlineKeyboardButton("🔄 تنظیمات بکاپ خودکار", callback_data="pishva_auto_backup")],
        [InlineKeyboardButton("📥 بازگردانی از فایل", callback_data="pishva_restore")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="menu_pishva")],
    ])

def kb_backup_format():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📄 Word", callback_data="backup_fmt_word"),
        InlineKeyboardButton("📊 Excel", callback_data="backup_fmt_excel")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="pishva_backup")],
    ])

def kb_restore_confirm():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ تایید و اعمال", callback_data="restore_apply"),
        InlineKeyboardButton("❌ انصراف", callback_data="restore_cancel")],
    ])

def kb_workhours(autoend_on: bool = False, reminder_on: bool = False, reminder_minutes: int = 60):
    rows = [
        [InlineKeyboardButton("🟢 آغاز ساعت کاری", callback_data="wh_start"),
        InlineKeyboardButton("🔴 پایان ساعت کاری", callback_data="wh_end")],
        [InlineKeyboardButton(
            f"⏱ پایان خودکار: {'✅ روشن' if autoend_on else '❌ خاموش'}",
            callback_data="wh_autoend_toggle"
        )],
    ]
    if not autoend_on:
        rows.append([InlineKeyboardButton(
            f"⏰ یادآور عدم پایان: {'✅ روشن' if reminder_on else '❌ خاموش'}",
            callback_data="wh_reminder_toggle"
        )])
        if reminder_on:
            rows.append([InlineKeyboardButton(
                f"✏️ دقیقهٔ یادآور (فعلی: {reminder_minutes})",
                callback_data="wh_reminder_set_minutes"
            )])
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="menu_pishva")])
    return InlineKeyboardMarkup(rows)

def kb_repair_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔧 فعال‌سازی تعمیر", callback_data="repair_on"),
        InlineKeyboardButton("✅ غیرفعال‌سازی تعمیر", callback_data="repair_off")],
        [InlineKeyboardButton("📝 ثبت دلیل تعمیر", callback_data="repair_reason")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="menu_pishva")],
    ])

def kb_logs_filter():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 امروز", callback_data="logs_today"),
        InlineKeyboardButton("📆 این هفته", callback_data="logs_week")],
        [InlineKeyboardButton("🗓️ این ماه", callback_data="logs_month"),
        InlineKeyboardButton("📚 کل اقدامات", callback_data="logs_all")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="menu_pishva")],
    ])

# ─── مدیران ───────────────────────────────────────────────────
def kb_admin_list(admins):
    rows = []
    for i in range(0, len(admins), 2):
        row = [InlineKeyboardButton(
            f"{'🟢' if a['is_active'] else '🔴'} {a['display_name'] or a['full_name']}",
            callback_data=f"admin_view_{a['telegram_id']}"
        ) for a in admins[i:i+2]]
        rows.append(row)
    rows.append(kb_back_row("main"))
    return InlineKeyboardMarkup(rows)

def kb_admin_actions(tid):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬆️ دسترسی‌ها", callback_data=f"admin_perms_{tid}"),
        InlineKeyboardButton("⚠️ ثبت اخطار", callback_data=f"admin_warn_{tid}")],
        [InlineKeyboardButton("🚫 اخراج", callback_data=f"admin_kick_{tid}"),
        InlineKeyboardButton("💬 ارسال پیام", callback_data=f"admin_msg_{tid}")],
        [InlineKeyboardButton("📋 اعطای وظیفه", callback_data=f"admin_task_{tid}"),
        InlineKeyboardButton("👁️ پروفایل", callback_data=f"admin_profile_{tid}")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="menu_admins")],
    ])

def kb_admin_permissions(tid, perms):
    def tog(k): return "✅" if perms.get(k, False) else "❌"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🔔 اعلان {tog('notifications')}", callback_data=f"perm_{tid}_notifications"),
        InlineKeyboardButton(f"📰 اخبار {tog('news')}", callback_data=f"perm_{tid}_news")],
        [InlineKeyboardButton(f"♟️ مسابقات {tog('match_management')}", callback_data=f"perm_{tid}_match_management"),
        InlineKeyboardButton(f"👥 بازیکنان {tog('view_players')}", callback_data=f"perm_{tid}_view_players")],
        [InlineKeyboardButton(f"⚠️ اخطار {tog('issue_warning')}", callback_data=f"perm_{tid}_issue_warning"),
        InlineKeyboardButton(f"🚫 درخواست اخراج {tog('request_ban')}", callback_data=f"perm_{tid}_request_ban")],
        [InlineKeyboardButton(f"❌ اخراج مستقیم {tog('direct_ban')}", callback_data=f"perm_{tid}_direct_ban"),
        InlineKeyboardButton(f"📋 وظیفه {tog('assign_task')}", callback_data=f"perm_{tid}_assign_task")],
        [InlineKeyboardButton(f"🚨 گزارش {tog('report')}", callback_data=f"perm_{tid}_report"),
        InlineKeyboardButton(f"💤 ربات فعال {tog('bot_active')}", callback_data=f"perm_{tid}_bot_active")],
        [InlineKeyboardButton(f"⚙️ تنظیمات {tog('settings_access')}", callback_data=f"perm_{tid}_settings_access"),
        InlineKeyboardButton(f"🌟 ارشد {tog('senior_admin')}", callback_data=f"perm_{tid}_senior_admin")],
        [InlineKeyboardButton(f"✏️ ویرایش مسابقه {tog('edit_delete_match')}", callback_data=f"perm_{tid}_edit_delete_match"),
        InlineKeyboardButton(f"📡 مخابرات {tog('communications')}", callback_data=f"perm_{tid}_communications")],
        [InlineKeyboardButton("✅ ذخیره و بازگشت", callback_data=f"admin_view_{tid}")],
    ])

# ─── مخابرات ──────────────────────────────────────────────────
def kb_comms_pishva():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 پیام به ادمین", callback_data="comms_msg_admin"),
        InlineKeyboardButton("📢 ارسال بیانیه", callback_data="comms_announce")],
        [InlineKeyboardButton("📨 پیام‌های دریافتی", callback_data="comms_inbox"),
        InlineKeyboardButton("🔔 اعلانات اخیر", callback_data="comms_notifs")],
        [InlineKeyboardButton("👁️ پیام ادمین‌ها", callback_data="comms_all_msgs"),
        InlineKeyboardButton("📰 ارسال خبر", callback_data="comms_news")],
        [InlineKeyboardButton("📊 گزارشات", callback_data="comms_reports"),
        InlineKeyboardButton("📜 تاریخچه بیانیات", callback_data="comms_ann_history")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")],
    ])

def kb_comms_admin():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 پیام به پیشوا", callback_data="comms_msg_pishva"),
        InlineKeyboardButton("💬 پیام به ادمین", callback_data="comms_msg_other")],
        [InlineKeyboardButton("📨 پیام‌های دریافتی", callback_data="comms_inbox"),
        InlineKeyboardButton("📜 بیانیات", callback_data="comms_ann_history")],
        [InlineKeyboardButton("📰 اخبار", callback_data="comms_news_list"),
        InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")],
    ])

def kb_announce_file():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📎 بله، پیوست کن", callback_data="ann_with_file"),
        InlineKeyboardButton("➡️ خیر، فقط متن", callback_data="ann_no_file")],
    ])

# ─── وظایف ────────────────────────────────────────────────────
def kb_tasks_pishva():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 اعطای وظیفه", callback_data="task_assign"),
        InlineKeyboardButton("📜 تاریخچه وظایف", callback_data="task_history")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")],
    ])

def kb_tasks_admin():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📌 پیگیری وظایف", callback_data="task_track"),
        InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")],
    ])

def kb_task_status(task_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ انجام شد", callback_data=f"task_done_{task_id}"),
        InlineKeyboardButton("❌ انجام نشد", callback_data=f"task_fail_{task_id}")],
    ])

def kb_task_history_filter():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 امروز", callback_data="thistory_today"),
        InlineKeyboardButton("📆 این هفته", callback_data="thistory_week")],
        [InlineKeyboardButton("✅ انجام‌شده", callback_data="thistory_done"),
        InlineKeyboardButton("❌ انجام‌نشده", callback_data="thistory_pending")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="menu_tasks")],
    ])

# ─── فیدبک ────────────────────────────────────────────────────
def kb_feedback_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 انتقاد", callback_data="fb_critique"),
        InlineKeyboardButton("💡 پیشنهاد", callback_data="fb_suggestion")],
        [InlineKeyboardButton("🏆 تقدیر", callback_data="fb_praise"),
        InlineKeyboardButton("🔧 درخواست قابلیت", callback_data="fb_feature")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")],
    ])

def kb_feedback_pishva():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 انتقادات", callback_data="fb_view_critique"),
        InlineKeyboardButton("💡 پیشنهادات", callback_data="fb_view_suggestion")],
        [InlineKeyboardButton("🏆 تقدیرها", callback_data="fb_view_praise"),
        InlineKeyboardButton("🔧 قابلیت‌ها", callback_data="fb_view_feature")],
        [InlineKeyboardButton("📋 همه موارد", callback_data="fb_view_all"),
        InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")],
    ])

# ─── راهنما ───────────────────────────────────────────────────
def kb_help_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏅 تورنمنت", callback_data="help_tournament"),
        InlineKeyboardButton("👤 بازیکنان", callback_data="help_players")],
        [InlineKeyboardButton("♟️ مسابقات", callback_data="help_matches"),
        InlineKeyboardButton("📡 مخابرات", callback_data="help_comms")],
        [InlineKeyboardButton("⚠️ اخطار", callback_data="help_warnings"),
        InlineKeyboardButton("📋 وظایف", callback_data="help_tasks")],
        [InlineKeyboardButton("❓ سوالات متداول", callback_data="help_faq"),
        InlineKeyboardButton("🛠️ خطاهای احتمالی", callback_data="help_errors")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")],
    ])

# ─── تیم‌ها ───────────────────────────────────────────────────
def kb_teams_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 تیم‌ها", callback_data="teams_list"),
        InlineKeyboardButton("➕ افزودن تیم", callback_data="teams_add")],
        [InlineKeyboardButton("⚙️ تنظیمات تیم", callback_data="teams_settings"),
        InlineKeyboardButton("🔙 بازگشت", callback_data="back_matches")],
    ])

def kb_team_list(teams):
    rows = []
    for i in range(0, len(teams), 2):
        row = [InlineKeyboardButton(f"🏆 {t['name']}", callback_data=f"team_view_{t['id']}") for t in teams[i:i+2]]
        rows.append(row)
    rows.append(kb_back_row("teams_menu"))
    return InlineKeyboardMarkup(rows)

def kb_team_actions(team_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 بازیکنان تیم", callback_data=f"team_members_{team_id}"),
        InlineKeyboardButton("👑 تنظیم سرگروه", callback_data=f"team_captain_{team_id}")],
        [InlineKeyboardButton("⚠️ اخطارهای تیم", callback_data=f"team_warnings_{team_id}"),
        InlineKeyboardButton("🗑️ حذف تیم", callback_data=f"team_delete_{team_id}")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="teams_list")],
    ])

def kb_confirm(yes_cb, no_cb, yes_label="✅ بله", no_label="❌ خیر"):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(yes_label, callback_data=yes_cb),
        InlineKeyboardButton(no_label, callback_data=no_cb)],
    ])

def kb_access_request(req_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ تأیید", callback_data=f"req_approve_{req_id}"),
        InlineKeyboardButton("❌ رد", callback_data=f"req_reject_{req_id}")],
        [InlineKeyboardButton("⏳ صف انتظار", callback_data=f"req_queue_{req_id}"),
        InlineKeyboardButton("🚫 بلاک دائم", callback_data=f"req_blockask_{req_id}")],
    ])

def kb_lottery_scope():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏫 فقط از یک کلاس", callback_data="lottery_class"),
        InlineKeyboardButton("🌐 از همه کلاس‌ها", callback_data="lottery_all")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="back_matches")],
    ])

def kb_identity():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🪪 تغییر نام پیشوا", callback_data="identity_pishva"),
        InlineKeyboardButton("👥 تغییر نام مدیران", callback_data="identity_admin")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="menu_pishva")],
    ])

def kb_newyear_confirm():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ بله، ادامه بده", callback_data="newyear_yes"),
        InlineKeyboardButton("❌ انصراف", callback_data="menu_pishva")],
    ])

def kb_update_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💤 خاموشی موقت برای آپدیت", callback_data="update_sleep"),
        InlineKeyboardButton("📢 اعلام آپدیت", callback_data="update_announce")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="menu_pishva")],
    ])

# ─── داشبورد ──────────────────────────────────────────────────
def kb_dashboard_pishva():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 به‌روزرسانی", callback_data="dashboard_pishva"),
        InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")],
    ])

def kb_dashboard_admin():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 به‌روزرسانی", callback_data="dashboard_admin"),
        InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")],
    ])

# ─── Auto Backup ──────────────────────────────────────────────
def kb_auto_backup_settings(enabled, interval, fmt, period):
    e_icon = "✅" if enabled == "1" else "❌"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🔄 بکاپ خودکار {e_icon}", callback_data="abk_toggle")],
        [InlineKeyboardButton(f"⏰ هر {interval} ساعت", callback_data="abk_interval"),
        InlineKeyboardButton(f"📁 {fmt}", callback_data="abk_fmt")],
        [InlineKeyboardButton(f"📊 بازه: {period}", callback_data="abk_period")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="pishva_backup")],
    ])

def kb_auto_backup_interval():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⏰ هر ۶ ساعت", callback_data="abk_set_interval_6"),
        InlineKeyboardButton("⏰ هر ۱۲ ساعت", callback_data="abk_set_interval_12")],
        [InlineKeyboardButton("⏰ هر ۲۴ ساعت", callback_data="abk_set_interval_24"),
        InlineKeyboardButton("⏰ هر ۴۸ ساعت", callback_data="abk_set_interval_48")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="pishva_auto_backup")],
    ])

def kb_dbstatus_menu(current):
    label = "⚠️ تغییر به غیرفعال" if current == "1" else "🔗 فعال"
    action = "dbstatus_off" if current == "1" else "dbstatus_on"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(label, callback_data=action)],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="menu_pishva")],
    ])

# ─── ثبت‌نام گروهی ────────────────────────────────────────────
def kb_bulk_preview():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ ثبت و تایید", callback_data="bulk_confirm")],
        [InlineKeyboardButton("✏️ ویرایش", callback_data="bulk_edit"),
        InlineKeyboardButton("❌ لغو", callback_data="bulk_cancel")],
    ])

# ─── یادآورها ─────────────────────────────────────────────────
def kb_reminders_menu(master_on, items):
    rows = [[InlineKeyboardButton(
        f"{'✅' if master_on else '❌'} فعال‌سازی کلی یادآورها",
        callback_data="reminder_toggle_master"
    )]]
    for rtype, label, enabled, interval in items:
        icon = "✅" if enabled else "❌"
        rows.append([
            InlineKeyboardButton(f"{icon} {label}", callback_data=f"reminder_toggle_{rtype}"),
            InlineKeyboardButton(f"⏰ هر {interval} ساعت", callback_data=f"reminder_interval_{rtype}"),
        ])
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="menu_pishva")])
    return InlineKeyboardMarkup(rows)


def kb_reminder_interval_options(rtype):
    hours_options = [1, 3, 6, 12, 24, 48]
    rows = []
    row = []
    for h in hours_options:
        row.append(InlineKeyboardButton(f"⏰ هر {h} ساعت", callback_data=f"reminder_set_{rtype}_{h}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="pishva_reminders")])
    return InlineKeyboardMarkup(rows)


# ─── پخش خودکار به گروه/کانال ─────────────────────────────────
def kb_broadcast_menu(items):
    rows = []
    for key, label, group_key, g_on, channel_key, c_on in items:
        rows.append([InlineKeyboardButton(f"— {label} —", callback_data="noop_label")])
        g_icon = "✅" if g_on else "❌"
        c_icon = "✅" if c_on else "❌"
        rows.append([
            InlineKeyboardButton(f"{g_icon} گروه", callback_data=f"broadcast_toggle_{group_key}"),
            InlineKeyboardButton(f"{c_icon} کانال", callback_data=f"broadcast_toggle_{channel_key}"),
        ])
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="menu_pishva")])
    return InlineKeyboardMarkup(rows)


# ─── قرعه‌کشی پیشرفته ─────────────────────────────────────────
# ─── امنیت APS (صف انتظار و بلاک) ──────────────────────────────
def kb_security_panel():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⏳ صف انتظار", callback_data="security_queue"),
        InlineKeyboardButton("🚫 بلاک‌شده‌ها", callback_data="security_blocked")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="menu_pishva")],
    ])

def kb_queue_list(queued):
    rows = []
    for i in range(0, len(queued), 2):
        row = [InlineKeyboardButton(
            f"⏳ {r['full_name'] or r['telegram_id']}",
            callback_data=f"queueview_{r['id']}"
        ) for r in queued[i:i+2]]
        rows.append(row)
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="security_panel")])
    return InlineKeyboardMarkup(rows)

def kb_queue_item_actions(req_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ تأیید و عضویت", callback_data=f"queueapprove_{req_id}")],
        [InlineKeyboardButton("🔓 خروج از صف بدون تأیید", callback_data=f"queuerelease_{req_id}")],
        [InlineKeyboardButton("🚫 بلاک دائم", callback_data=f"queueblockask_{req_id}")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="security_queue")],
    ])

def kb_block_confirm(token, back_cb="security_panel"):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚫 بله، بلاک کن", callback_data=f"blockconfirm_{token}"),
        InlineKeyboardButton("❌ انصراف", callback_data=back_cb)],
    ])

def kb_blocked_list(blocked):
    rows = []
    for i in range(0, len(blocked), 2):
        row = [InlineKeyboardButton(
            f"🚫 {b['full_name'] or b['telegram_id']}",
            callback_data=f"blockedview_{b['telegram_id']}"
        ) for b in blocked[i:i+2]]
        rows.append(row)
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="security_panel")])
    return InlineKeyboardMarkup(rows)

def kb_blocked_item_actions(tid):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔓 آنبلاک", callback_data=f"unblock_{tid}")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="security_blocked")],
    ])

def kb_adv_lottery_scope():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎯 هر دو طرف از یک کلاس", callback_data="adv_scope_same")],
        [InlineKeyboardButton("🔀 هرکدام از یک کلاس متفاوت", callback_data="adv_scope_diff")],
        [InlineKeyboardButton("🌐 از همه کلاس‌ها (آزاد)", callback_data="adv_scope_open")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="back_matches")],
    ])
