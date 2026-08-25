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

# ─── پنل مدیر ارشد (منوی اصلی کوتاه) ────────────────────────────
def kb_pishva_main():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("♟️ مدیریت مسابقات", callback_data="menu_matches"),
        InlineKeyboardButton("👤 مدیریت بازیکنان", callback_data="menu_players")],
        [InlineKeyboardButton("👑 پنل مدیر ارشد", callback_data="menu_pishva"),
        InlineKeyboardButton("👥 مدیریت مدیران", callback_data="menu_admins")],
        [InlineKeyboardButton("📡 مخابرات", callback_data="menu_comms"),
        InlineKeyboardButton("📋 وظایف", callback_data="menu_tasks")],
        [InlineKeyboardButton("📊 داشبورد مدیر ارشد", callback_data="dashboard_pishva"),
        InlineKeyboardButton("❓ راهنما", callback_data="menu_help")],
        [InlineKeyboardButton("🗄️ وضعیت دیتابیس", callback_data="pishva_dbstatus")],
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

def kb_player_select(players, prefix, back="matches"):
    rows = []
    for i in range(0, len(players), 2):
        row = [InlineKeyboardButton(
            f"{'⬜' if 'white' in prefix else '⬛' if 'black' in prefix else '👤'} {p['full_name']} [{p['class_name'] if p['class_name'] else ''}]",
            callback_data=f"{prefix}_{p['id']}"
        ) for p in players[i:i+2]]
        rows.append(row)
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

# ─── پنل مدیر ارشد ────────────────────────────────────────────────
def kb_pishva_panel():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚦 مدیریت وضعیت", callback_data="pishva_status"),
        InlineKeyboardButton("⚙️ تنظیمات ربات", callback_data="pishva_settings")],
        [InlineKeyboardButton("🔍 پیگیری اقدامات", callback_data="pishva_logs"),
        InlineKeyboardButton("📥 درخواست‌های دسترسی", callback_data="pishva_requests")],
        [InlineKeyboardButton("💾 دریافت بکاپ", callback_data="pishva_backup"),
        InlineKeyboardButton("🕐 ساعت کاری", callback_data="pishva_workhours")],
        [InlineKeyboardButton("🔧 حالت تعمیر", callback_data="pishva_repair"),
        InlineKeyboardButton("🏦 خزانه مدیر ارشد", callback_data="pishva_vault")],
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
        [InlineKeyboardButton("🔙 بازگشت", callback_data="menu_pishva")],
    ])

def kb_backup_format():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📄 Word", callback_data="backup_fmt_word"),
        InlineKeyboardButton("📊 Excel", callback_data="backup_fmt_excel")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="pishva_backup")],
    ])

def kb_workhours():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🟢 آغاز ساعت کاری", callback_data="wh_start"),
        InlineKeyboardButton("🔴 پایان ساعت کاری", callback_data="wh_end")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="menu_pishva")],
    ])

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
        InlineKeyboardButton("👁️ پروفایل", callback_data=f"admin_profile_{tid}
