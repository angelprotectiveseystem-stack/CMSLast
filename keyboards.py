import json
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import BOT_USERNAME

# ─── Auth ─────────────────────────────────────────────────────
def kb_role_select():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👑 رییس کل", callback_data="role_pishva", style="primary"),
        InlineKeyboardButton("🏆 مدیر مسابقات", callback_data="role_tournament", style="primary")],
        [InlineKeyboardButton("🛡️ مدیر امنیتی", callback_data="role_security", style="primary")],
    ])

def kb_back(target="main"):
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data=f"back_{target}", style="danger")]])

def kb_back_row(target="main"):
    return [InlineKeyboardButton("🔙 بازگشت", callback_data=f"back_{target}", style="danger")]

# ─── صفحه‌ی خلاصه بعد از «بستن»/«خروج» — فقط خوش‌آمدگویی + ۲ دکمه ───
def kb_panel_closed_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 لاگ‌ها", callback_data="pishva_logs", style="primary"),
        InlineKeyboardButton("🔓 ورود به پنل", callback_data="back_main", style="primary")],
    ])

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
        [InlineKeyboardButton("♟️ شطرنج زنده", callback_data="chess_menu")],
        [InlineKeyboardButton("🤖 دستیار هوشمند", callback_data="ai_assistant_open"),
        InlineKeyboardButton("🧑‍💻 مدیریت دستیار", callback_data="ai_manage_menu_main")],
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
        [InlineKeyboardButton("♟️ شطرنج زنده", callback_data="chess_menu")],
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
        [InlineKeyboardButton("♟️ شطرنج زنده", callback_data="chess_menu")],
        [InlineKeyboardButton("🤖 دستیار هوشمند", callback_data="ai_assistant_open")],
    ])

# ─── مدیریت مسابقات (همه چیز اینجاست) ──────────────────────
def kb_matches_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ ثبت مسابقه جدید", callback_data="match_add", style="success"),
        InlineKeyboardButton("🏆 ثبت نتیجه", callback_data="match_result", style="success")],
        [InlineKeyboardButton("🔍 تاریخچه مسابقات", callback_data="match_history", style="primary"),
        InlineKeyboardButton("📊 پنل مدیریت", callback_data="match_panel", style="primary")],
        [InlineKeyboardButton("🎲 قرعه‌کشی", callback_data="lottery_start", style="primary"),
        InlineKeyboardButton("🎯 قرعه‌کشی پیشرفته", callback_data="adv_lottery_start", style="primary")],
        [InlineKeyboardButton("📋 جدول مسابقات", callback_data="match_bracket", style="primary")],
        [InlineKeyboardButton("🏅 تورنمنت‌ها", callback_data="menu_tournament", style="primary"),
        InlineKeyboardButton("🏆 تیم‌ها", callback_data="teams_menu", style="primary")],
        [InlineKeyboardButton("📊 جدول Elo", callback_data="elo_leaderboard", style="primary"),
        InlineKeyboardButton("👑 قهرمانان", callback_data="champions", style="primary")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="back_main", style="danger")],
    ])

# ─── مدیریت بازیکنان ─────────────────────────────────────────
def kb_players_menu(role="pishva"):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ ثبت‌نام بازیکن", callback_data="player_add", style="success"),
        InlineKeyboardButton("🏫 مدیریت کلاس‌ها", callback_data="class_manage", style="primary")],
        [InlineKeyboardButton("📋 ثبت‌نام گروهی", callback_data="bulk_register_start", style="success")],
        [InlineKeyboardButton("👁️ مشاهده بازیکنان", callback_data="player_list", style="primary"),
        InlineKeyboardButton("🔍 جستجو بازیکن", callback_data="player_search", style="primary")],
        [InlineKeyboardButton("✅ ادامه‌دهندگان", callback_data="player_continuing", style="success"),
        InlineKeyboardButton("❌ حذف‌شدگان", callback_data="player_eliminated", style="danger")],
        [InlineKeyboardButton("🌟 بازیکنان برتر", callback_data="player_elite", style="primary"),
        InlineKeyboardButton("⚡ نیروهای ویژه", callback_data="player_special", style="primary")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="back_main", style="danger")],
    ])

# ─── کلاس ────────────────────────────────────────────────────
def kb_class_manage():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ ثبت کلاس جدید", callback_data="class_add", style="success"),
        InlineKeyboardButton("👁️ مشاهده کلاس‌ها", callback_data="class_list", style="primary")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="back_players", style="danger")],
    ])

def kb_class_list(classes):
    rows = []
    for i in range(0, len(classes), 2):
        row = [InlineKeyboardButton(f"🏫 {c['name']}", callback_data=f"class_select_{c['id']}", style="primary") for c in classes[i:i+2]]
        rows.append(row)
    rows.append(kb_back_row("class_manage"))
    return InlineKeyboardMarkup(rows)

def kb_class_actions(class_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 بازیکنان کلاس", callback_data=f"class_players_{class_id}", style="primary"),
        InlineKeyboardButton("✏️ ویرایش نام", callback_data=f"class_edit_{class_id}", style="primary")],
        [InlineKeyboardButton("📈 عملکرد کلاس", callback_data=f"class_perf_{class_id}", style="primary"),
        InlineKeyboardButton("🔙 بازگشت", callback_data="class_list", style="danger")],
    ])

# ─── بازیکنان ─────────────────────────────────────────────────
def kb_player_list(players, page=0, page_size=8, context="all"):
    """FIX: قبلاً دکمه‌های صفحه‌بندی («بعدی»/«قبلی») و جستجو، مستقل از این‌که
    کاربر توی کدوم لیست بود (همه‌ی بازیکنان، ادامه‌دهنده‌ها، اخراجی‌ها و...)
    فقط "player_list_page_N" یا "player_search" رو صدا می‌زدن؛ این باعث می‌شد
    مثلاً توی لیست «ادامه‌دهنده‌ها» با زدن صفحه‌ی بعد یا جستجو، کاربر عملاً وارد
    لیست کل بازیکنان بشه. حالا context (all/continuing/kicked/elim/elite/special)
    توی callback_data صفحه‌بندی و جستجو نگه داشته می‌شه تا همون لیست حفظ بشه.
    """
    start = page * page_size
    chunk = players[start:start+page_size]
    rows = []
    for i in range(0, len(chunk), 2):
        row = []
        for p in chunk[i:i+2]:
            status = p["status"]
            icon = "⛔" if status == "eliminated" else "🚫" if status == "suspended" else "❌" if status == "kicked" else "🟢"
            # FIX: قبلاً استایل دکمه همیشه "primary" بود و فقط ایموجی فرق می‌کرد؛
            # بازیکنِ اخراج/تعلیق/حذف‌شده هم رنگش با بازیکن فعال یکی بود.
            # حالا بازیکنی که دیگه ادامه‌دهنده نیست، دکمه‌ش قرمز (danger) می‌شه.
            style = "danger" if status != "active" else "primary"
            row.append(InlineKeyboardButton(f"{icon} {p['full_name']}", callback_data=f"player_view_{p['id']}", style=style))
        rows.append(row)
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ قبلی", callback_data=f"player_list_page_{context}_{page-1}", style="primary"))
    if start + page_size < len(players):
        nav.append(InlineKeyboardButton("▶️ بعدی", callback_data=f"player_list_page_{context}_{page+1}", style="primary"))
    if nav:
        rows.append(nav)
    # FIX: توی لیستِ بازیکنان دکمه‌ی جستجو نبود — کاربر مجبور بود اول با
    # «بازگشت» به منوی بازیکنان برگرده تا به جستجو برسه.
    rows.append([InlineKeyboardButton("🔍 جستجو بازیکن", callback_data=f"player_search_ctx_{context}", style="primary")])
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
        , style="primary") for p in page_players[i:i + 2]]
        rows.append(row)
    if nav_prefix:
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton("◀️ قبلی", callback_data=f"{nav_prefix}page_{page-1}", style="primary"))
        if start + page_size < total:
            nav_row.append(InlineKeyboardButton("بعدی ▶️", callback_data=f"{nav_prefix}page_{page+1}", style="primary"))
        if nav_row:
            rows.append(nav_row)
    rows.append(kb_back_row(back))
    return InlineKeyboardMarkup(rows)

def kb_player_actions(player_id, role="pishva", status="active"):
    """FIX: قبلاً دکمه‌های اخراج/تعلیق/احیا بدون توجه به وضعیت فعلیِ بازیکن
    همیشه با هم نشون داده می‌شدن — یعنی حتی بعد از اخراج یه بازیکن، دوباره
    که پنلش رو باز می‌کردی دکمه‌ی «🚫 اخراج» جلوت بود (روی بازیکنی که از قبل
    اخراج شده!). حالا: اگه بازیکن فعاله، اخراج/تعلیق نشون داده می‌شه؛ اگه
    از قبل اخراج/تعلیق/حذف شده، به‌جاش فقط دکمه‌ی «🔄 احیا» نشون داده می‌شه."""
    is_active = status == "active"
    action_buttons = [
        InlineKeyboardButton("✏️ ویرایش نام", callback_data=f"player_editname_{player_id}", style="primary"),
        InlineKeyboardButton("🏫 ویرایش کلاس", callback_data=f"player_editclass_{player_id}", style="primary"),
        InlineKeyboardButton("⚠️ ثبت اخطار", callback_data=f"player_warn_{player_id}", style="danger"),
    ]
    if is_active:
        action_buttons.append(InlineKeyboardButton("🚫 اخراج", callback_data=f"player_kick_{player_id}", style="danger"))
        action_buttons.append(InlineKeyboardButton("⏸️ تعلیق", callback_data=f"player_suspend_{player_id}", style="danger"))
    else:
        action_buttons.append(InlineKeyboardButton("🔄 احیا", callback_data=f"player_revive_{player_id}", style="success"))
    action_buttons.append(InlineKeyboardButton("📝 یادداشت", callback_data=f"player_note_{player_id}", style="primary"))
    action_buttons.append(InlineKeyboardButton("🌟 ثبت برتر", callback_data=f"player_elite_{player_id}", style="success"))
    action_buttons.append(InlineKeyboardButton("📈 امتیاز Elo", callback_data=f"elo_player_{player_id}", style="primary"))
    action_buttons.append(InlineKeyboardButton("🔮 پیش‌بینی", callback_data=f"predict_select_{player_id}", style="primary"))
    if role == "pishva":
        action_buttons.append(InlineKeyboardButton("⚡ ثبت ویژه", callback_data=f"player_special_{player_id}", style="success"))

    rows = [action_buttons[i:i + 2] for i in range(0, len(action_buttons), 2)]
    rows.append(kb_back_row("player_list"))
    return InlineKeyboardMarkup(rows)

# ─── تورنمنت ──────────────────────────────────────────────────
def kb_tournament_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ افزودن تورنمنت", callback_data="tourn_add", style="success"),
        InlineKeyboardButton("⚙️ مدیریت تورنمنت", callback_data="tourn_manage", style="primary")],
        [InlineKeyboardButton("📌 تورنمنت پیش‌فرض", callback_data="tourn_default", style="primary"),
        InlineKeyboardButton("📊 جزئیات فعال", callback_data="tourn_details", style="primary")],
        [InlineKeyboardButton("🗂️ حذف‌شده‌ها", callback_data="tourn_deleted", style="danger"),
        InlineKeyboardButton("🔙 بازگشت", callback_data="back_matches", style="danger")],
    ])

def kb_tournament_actions(tid, is_pishva=False):
    rows = [
        [InlineKeyboardButton("✏️ ویرایش نام", callback_data=f"tourn_edit_{tid}", style="primary"),
        InlineKeyboardButton("🔴 پایان تورنمنت", callback_data=f"tourn_end_{tid}", style="danger")],
        [InlineKeyboardButton("⏸️ به تعویق", callback_data=f"tourn_pause_{tid}", style="primary"),
        InlineKeyboardButton("📌 تنظیم پیش‌فرض", callback_data=f"tourn_setdefault_{tid}", style="primary")],
    ]
    if is_pishva:
        rows.append([InlineKeyboardButton("🗑️ حذف تورنمنت", callback_data=f"tourn_delete_{tid}", style="danger")])
    rows.append(kb_back_row("tournament"))
    return InlineKeyboardMarkup(rows)

def kb_tournament_list(tournaments):
    rows = []
    for i in range(0, len(tournaments), 2):
        row = [InlineKeyboardButton(
            f"{'🟢' if t['status']=='active' else '⏸️' if t['status']=='paused' else '🔴'} {t['name']}",
            callback_data=f"tourn_select_{t['id']}"
        , style="primary") for t in tournaments[i:i+2]]
        rows.append(row)
    rows.append(kb_back_row("tournament"))
    return InlineKeyboardMarkup(rows)

# ─── مسابقات ──────────────────────────────────────────────────
def kb_match_result_options(match_id, white_name, black_name):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🥇 برد {white_name}", callback_data=f"result_white_{match_id}", style="success")],
        [InlineKeyboardButton(f"🥇 برد {black_name}", callback_data=f"result_black_{match_id}", style="success")],
        [InlineKeyboardButton("🤝 تساوی", callback_data=f"result_draw_{match_id}", style="primary")],
        [InlineKeyboardButton("❌ لغو مسابقه", callback_data=f"result_cancel_{match_id}", style="danger")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="match_result", style="danger")],
    ])

def kb_draw_reasons(match_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔒 پات", callback_data=f"draw_pat_{match_id}", style="primary"),
        InlineKeyboardButton("⏱️ اتمام زمان", callback_data=f"draw_time_{match_id}", style="primary")],
        [InlineKeyboardButton("♾️ حرکات بسیار", callback_data=f"draw_moves_{match_id}", style="primary"),
        InlineKeyboardButton("🔁 سه تکرار", callback_data=f"draw_repeat_{match_id}", style="primary")],
        [InlineKeyboardButton("📝 سایر موارد", callback_data=f"draw_other_{match_id}", style="primary")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="match_result", style="danger")],
    ])

def kb_eliminate_ask(loser_id, loser_name):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"✅ بله، {loser_name} حذف شود", callback_data=f"eliminate_yes_{loser_id}", style="danger"),
        InlineKeyboardButton("❌ خیر، ادامه دهد", callback_data=f"eliminate_no_{loser_id}", style="danger")],
    ])

def kb_match_history_filter():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 امروز", callback_data="mhist_today", style="primary"),
        InlineKeyboardButton("📆 این هفته", callback_data="mhist_week", style="primary")],
        [InlineKeyboardButton("🗓️ این ماه", callback_data="mhist_month", style="primary"),
        InlineKeyboardButton("📚 کل مسابقات", callback_data="mhist_all", style="primary")],
        [InlineKeyboardButton("🔍 جستجو", callback_data="mhist_search", style="primary"),
        InlineKeyboardButton("🔙 بازگشت", callback_data="back_matches", style="danger")],
    ])

def kb_match_list(matches):
    rows = []
    for m in matches[:20]:
        res = {"white": "⬜🥇", "black": "⬛🥇", "draw": "🤝", None: "⏳"}.get(m["result"], "⏳")
        label = f"{res} {m['white_name']} ⚔️ {m['black_name']}"
        rows.append([InlineKeyboardButton(label, callback_data=f"match_view_{m['id']}", style="primary")])
    rows.append(kb_back_row("match_history"))
    return InlineKeyboardMarkup(rows)

def kb_match_item_actions(mid):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ ویرایش", callback_data=f"match_edit_{mid}", style="primary"),
        InlineKeyboardButton("🗑️ حذف", callback_data=f"match_delete_{mid}", style="danger")],
        [InlineKeyboardButton("📌 پین کردن", callback_data=f"match_pin_{mid}", style="primary"),
        InlineKeyboardButton("🔙 بازگشت", callback_data="match_history", style="danger")],
    ])

# ─── پنل مدیر ارشد ────────────────────────────────────────────────
def kb_pishva_panel():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚦 مدیریت وضعیت", callback_data="pishva_status"),
        InlineKeyboardButton("⚙️ تنظیمات ربات", callback_data="pishva_settings")],
        [InlineKeyboardButton("🔍 پیگیری اقدامات", callback_data="pishva_logs"),
        InlineKeyboardButton("📥 درخواست‌های دسترسی", callback_data="pishva_requests")],
        [InlineKeyboardButton("♟️ بازی‌های مدیران", callback_data="pishva_chess_games"),
        InlineKeyboardButton("💾 دریافت بکاپ", callback_data="pishva_backup")],
        [InlineKeyboardButton("🕐 ساعت کاری", callback_data="pishva_workhours"),
        InlineKeyboardButton("🔧 حالت تعمیر", callback_data="pishva_repair")],
        [InlineKeyboardButton("🏦 خزانه مدیر ارشد", callback_data="pishva_vault"),
        InlineKeyboardButton("🪪 تغییر هویت", callback_data="pishva_identity")],
        [InlineKeyboardButton("🎓 سال تحصیلی جدید", callback_data="pishva_newyear"),
        InlineKeyboardButton("🔄 آپدیت ربات", callback_data="pishva_update")],
        [InlineKeyboardButton("📡 گروه اعلانات", callback_data="pishva_group"),
        InlineKeyboardButton("📢 افزودن به کانال", url=f"https://t.me/{BOT_USERNAME}?startchannel&admin=post_messages")],
        [InlineKeyboardButton("🆔 تنظیم کانال اعلانات", callback_data="pishva_channel"),
        InlineKeyboardButton("📡 پخش خودکار", callback_data="pishva_broadcast")],
        [InlineKeyboardButton("🛡️ پنل امنیتی APS", callback_data="security_panel"),
        InlineKeyboardButton("🧑‍💻 مدیریت دستیار", callback_data="ai_manage_menu")],
        [InlineKeyboardButton("⏰ یادآورها", callback_data="pishva_reminders"),
        InlineKeyboardButton("🤖 کارهای دستیار", callback_data="pishva_ai_scheduled")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="back_main", style="danger")],
    ])

# ─── کارهای زمان‌بندی‌شدهٔ دستیار هوشمند ───────────────────────────
def kb_ai_scheduled_list(rows):
    """rows: لیستی از دیکشنری‌های {id, label} برای هر یادآور/اقدام در انتظار.
    زیر هر ردیف (دکمهٔ شیشه‌ای غیرفعال/برچسب) یک دکمهٔ «لغو» جدا قرار می‌گیرد."""
    kb_rows = []
    if not rows:
        kb_rows.append([InlineKeyboardButton("📭 چیزی زمان‌بندی نشده", callback_data="noop_label", style="primary")])
    else:
        for r in rows:
            kb_rows.append([InlineKeyboardButton(r["label"], callback_data="noop_label", style="primary")])
            kb_rows.append([InlineKeyboardButton("❌ لغو", callback_data=f"aischedcancel_{r['id']}", style="danger")])
    kb_rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="menu_pishva", style="danger")])
    return InlineKeyboardMarkup(kb_rows)


# ─── مدیریت دستیار (قابل بازشدن هم از پنل اصلی، هم از پنل مدیر ارشد) ─
def kb_ai_manage_menu(ai_online: str = "1", back_target: str = "menu_pishva"):
    """back_target: کجا برگرده وقتی رو «بازگشت» بزنه — بسته به اینکه از
    کجا باز شده (پنل اصلی/خوش‌آمدگویی یا پنل مدیر ارشد)، در ai_manage.py
    تعیین و اینجا فقط رندر می‌شه."""
    tog = "✅" if ai_online == "1" else "❌"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🗂️ سوابق چت‌های دستیار", callback_data="ai_admlog_menu", style="primary")],
        [InlineKeyboardButton("🛠️ اختیارات دستیار", callback_data="ai_perms_menu", style="primary")],
        [InlineKeyboardButton(f"🔌 هوش مصنوعی {tog}", callback_data="ai_manage_toggle_online", style="primary")],
        [InlineKeyboardButton("🔕 خاموشی برای ادمین خاص", callback_data="ai_admtg_menu", style="danger")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data=back_target, style="danger")],
    ])


def kb_ai_perms_menu(states: dict):
    """states: دیکشنریِ کلیدِ دسته -> "1"/"0"، از ai_tools.get_category_states()."""
    from ai_tools import AI_PERMISSION_CATEGORIES
    rows = []
    for key, label, _tools in AI_PERMISSION_CATEGORIES:
        icon = "✅" if states.get(key, "1") == "1" else "❌"
        rows.append([InlineKeyboardButton(f"{icon} {label}", callback_data=f"aiperm_toggle_{key}", style="primary")])
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="ai_manage_menu_return", style="danger")])
    return InlineKeyboardMarkup(rows)


def kb_ai_admin_toggle_list(admins):
    """لیستِ مدیران برای انتخاب و خاموش/روشن‌کردنِ دسترسیِ هوش مصنوعی —
    وضعیتِ فعلی (🟢/🔴) مستقیماً از همون فیلدِ permissions روی ردیفِ ادمین
    خونده می‌شه (دیگه نیازی به کوئریِ جدا برای هرکدوم نیست)."""
    rows = []
    for i in range(0, len(admins), 2):
        row = []
        for a in admins[i:i + 2]:
            try:
                perms = json.loads(a["permissions"] or "{}")
            except Exception:
                perms = {}
            on = perms.get("ai_access", True)
            icon = "🟢" if on else "🔴"
            row.append(InlineKeyboardButton(
                f"{icon} {a['display_name'] or a['full_name']}",
                callback_data=f"ai_admtg_pick_{a['telegram_id']}", style="primary"))
        rows.append(row)
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="ai_manage_menu_return", style="danger")])
    return InlineKeyboardMarkup(rows)


def kb_ai_admin_toggle_pick(tid, is_on: bool):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🟢 روشن باشه", callback_data=f"ai_admtg_set_{tid}_on", style="success"),
        InlineKeyboardButton("🔴 خاموش باشه", callback_data=f"ai_admtg_set_{tid}_off", style="danger")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="ai_admtg_menu", style="danger")],
    ])


def kb_status_select(current):
    def icon(s): return "✅ " if s == current else ""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{icon('normal')}🟢 نرمال", callback_data="set_status_normal", style="success"),
        InlineKeyboardButton(f"{icon('bad')}🟡 بد", callback_data="set_status_bad", style="danger")],
        [InlineKeyboardButton(f"{icon('danger')}🔴 خطرناک", callback_data="set_status_danger", style="danger"),
        InlineKeyboardButton(f"{icon('aps')}🪽 APS", callback_data="set_status_aps", style="primary")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="menu_pishva", style="danger")],
    ])

def kb_pishva_settings_simple(settings):
    def tog(k): return "✅" if settings.get(k) == "1" else "❌"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🔔 اعلانات {tog('notifications_enabled')}", callback_data="setting_notifications", style="primary"),
        InlineKeyboardButton(f"📡 مخابرات {tog('communications_enabled')}", callback_data="setting_communications", style="primary")],
        [InlineKeyboardButton(f"❓ راهنما {tog('help_enabled')}", callback_data="setting_help", style="primary"),
        InlineKeyboardButton(f"♟️ ثبت مسابقه {tog('match_registration_enabled')}", callback_data="setting_match_reg", style="success")],
        [InlineKeyboardButton(f"🚪 ورود ادمین {tog('admin_login_enabled')}", callback_data="setting_admin_login", style="primary"),
        InlineKeyboardButton(f"💤 خاموش برای ادمین‌ها {tog('bot_active_for_admins')}", callback_data="setting_bot_active", style="danger")],
        [InlineKeyboardButton(f"🏆 حالت تیمی {tog('team_mode_enabled')}", callback_data="setting_team_mode", style="primary"),
        InlineKeyboardButton(f"📝 ثبت‌نام با تیم {tog('team_registration_enabled')}", callback_data="setting_team_reg", style="success")],
        [InlineKeyboardButton(f"👤 مدیران سازنده تیم {tog('managers_can_create_teams')}", callback_data="setting_mgr_team", style="primary")],
        [InlineKeyboardButton(f"📊 داشبورد ادمین‌ها {tog('admin_dashboard_enabled')}", callback_data="setting_admin_dashboard", style="primary")],
        [InlineKeyboardButton(f"🤖 هوش مصنوعی {tog('ai_online')}", callback_data="setting_ai_online", style="primary")],
        [InlineKeyboardButton(f"♟️ شطرنج زنده {tog('live_chess_enabled')}", callback_data="setting_live_chess", style="primary")],
        [InlineKeyboardButton(f"🚨 گزارش باگ به مدیر ارشد {tog('bug_report_to_pishva_enabled')}", callback_data="setting_bug_report", style="primary")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="menu_pishva", style="danger")],
    ])

def kb_backup_period():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 امروز", callback_data="backup_period_today", style="primary"),
        InlineKeyboardButton("📆 این هفته", callback_data="backup_period_week", style="primary")],
        [InlineKeyboardButton("🗓️ این ماه", callback_data="backup_period_month", style="primary"),
        InlineKeyboardButton("📚 از ابتدا", callback_data="backup_period_all", style="primary")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="menu_pishva", style="danger")],
    ])

def kb_backup_main():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 امروز", callback_data="backup_period_today", style="primary"),
        InlineKeyboardButton("📆 این هفته", callback_data="backup_period_week", style="primary")],
        [InlineKeyboardButton("🗓️ این ماه", callback_data="backup_period_month", style="primary"),
        InlineKeyboardButton("📚 از ابتدا", callback_data="backup_period_all", style="primary")],
        [InlineKeyboardButton("🔄 تنظیمات بکاپ خودکار", callback_data="pishva_auto_backup", style="primary")],
        [InlineKeyboardButton("📥 بازگردانی از فایل", callback_data="pishva_restore", style="primary")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="menu_pishva", style="danger")],
    ])

def kb_backup_format():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📄 Word", callback_data="backup_fmt_word", style="primary"),
        InlineKeyboardButton("📊 Excel", callback_data="backup_fmt_excel", style="primary")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="pishva_backup", style="danger")],
    ])

def kb_restore_confirm():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ تایید و اعمال", callback_data="restore_apply", style="success"),
        InlineKeyboardButton("❌ انصراف", callback_data="restore_cancel", style="danger")],
    ])

def kb_workhours(autoend_on: bool = False, reminder_on: bool = False, reminder_minutes: int = 60):
    rows = [
        [InlineKeyboardButton("🟢 آغاز ساعت کاری", callback_data="wh_start", style="success"),
        InlineKeyboardButton("🔴 پایان ساعت کاری", callback_data="wh_end", style="danger")],
        [InlineKeyboardButton(
            f"⏱ پایان خودکار: {'✅ روشن' if autoend_on else '❌ خاموش'}",
            callback_data="wh_autoend_toggle", style="danger")],
    ]
    if not autoend_on:
        rows.append([InlineKeyboardButton(
            f"⏰ یادآور عدم پایان: {'✅ روشن' if reminder_on else '❌ خاموش'}",
            callback_data="wh_reminder_toggle", style="danger")])
        if reminder_on:
            rows.append([InlineKeyboardButton(
                f"✏️ دقیقهٔ یادآور (فعلی: {reminder_minutes})",
                callback_data="wh_reminder_set_minutes"
            , style="primary")])
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="menu_pishva", style="danger")])
    return InlineKeyboardMarkup(rows)

def kb_repair_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔧 فعال‌سازی تعمیر", callback_data="repair_on", style="success"),
        InlineKeyboardButton("✅ غیرفعال‌سازی تعمیر", callback_data="repair_off", style="success")],
        [InlineKeyboardButton("📝 ثبت دلیل تعمیر", callback_data="repair_reason", style="success")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="menu_pishva", style="danger")],
    ])

def kb_logs_filter():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 امروز", callback_data="logs_today", style="primary"),
        InlineKeyboardButton("📆 این هفته", callback_data="logs_week", style="primary")],
        [InlineKeyboardButton("🗓️ این ماه", callback_data="logs_month", style="primary"),
        InlineKeyboardButton("📚 کل تاریخ", callback_data="logs_all", style="primary")],
        [InlineKeyboardButton("🔍 جستجو", callback_data="logs_search", style="primary")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="menu_pishva", style="danger")],
    ])

def kb_logs_list(period, page, total_pages):
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ قبلی", callback_data=f"logspage_{period}_{page-1}", style="primary"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("بعدی ▶️", callback_data=f"logspage_{period}_{page+1}", style="primary"))
    nav.append(InlineKeyboardButton("🔍 جستجو", callback_data="logs_search", style="primary"))
    rows = [nav]
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="pishva_logs", style="danger")])
    return InlineKeyboardMarkup(rows)

def kb_logs_search_list(page, total_pages):
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ قبلی", callback_data=f"logssearchpage_{page-1}", style="primary"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("بعدی ▶️", callback_data=f"logssearchpage_{page+1}", style="primary"))
    rows = []
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton("🔍 جستجوی جدید", callback_data="logs_search", style="primary")])
    rows.append([InlineKeyboardButton("🔙 بازگشت به فیلتر", callback_data="pishva_logs", style="danger")])
    return InlineKeyboardMarkup(rows)

def kb_logs_search_skip_term():
    """قدمِ اول جستجو: عبارت. به‌جای نوشتن «-»، دکمه‌ی رد شدن → می‌ره سراغ بازه."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⏭️ رد شدن — برو به تنظیم بازه", callback_data="logs_search_skip_term", style="danger")],
    ])

def kb_logs_search_skip_range():
    """قدمِ دوم جستجو: بازه‌ی ساعت. دکمه‌ی رد شدن → بدون فیلتر ساعت جستجو کن."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⏭️ رد شدن — بدون فیلتر ساعت", callback_data="logs_search_skip_range", style="danger")],
    ])

# ─── پیگیریِ اقدامات مخصوص یک مدیر (از پروفایل همون مدیر) ────────
def kb_admin_logs_filter(tid):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 امروز", callback_data=f"adminlogsperiod_{tid}_today", style="primary"),
        InlineKeyboardButton("📆 این هفته", callback_data=f"adminlogsperiod_{tid}_week", style="primary")],
        [InlineKeyboardButton("🗓️ این ماه", callback_data=f"adminlogsperiod_{tid}_month", style="primary"),
        InlineKeyboardButton("📚 کل تاریخ", callback_data=f"adminlogsperiod_{tid}_all", style="primary")],
        [InlineKeyboardButton("🔍 جستجو", callback_data=f"adminlogssearch_{tid}", style="primary")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data=f"admin_view_{tid}", style="danger")],
    ])

def kb_admin_logs_list(tid, period, page, total_pages):
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ قبلی", callback_data=f"adminlogspg_{tid}_{period}_{page-1}", style="primary"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("بعدی ▶️", callback_data=f"adminlogspg_{tid}_{period}_{page+1}", style="primary"))
    nav.append(InlineKeyboardButton("🔍 جستجو", callback_data=f"adminlogssearch_{tid}", style="primary"))
    rows = [nav]
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data=f"adminlogsmenu_{tid}", style="danger")])
    return InlineKeyboardMarkup(rows)

def kb_admin_logs_search_list(tid, page, total_pages):
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ قبلی", callback_data=f"adminlogssearchpg_{tid}_{page-1}", style="primary"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("بعدی ▶️", callback_data=f"adminlogssearchpg_{tid}_{page+1}", style="primary"))
    rows = []
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton("🔍 جستجوی جدید", callback_data=f"adminlogssearch_{tid}", style="primary")])
    rows.append([InlineKeyboardButton("🔙 بازگشت به فیلتر", callback_data=f"adminlogsmenu_{tid}", style="danger")])
    return InlineKeyboardMarkup(rows)

def kb_chess_games_filter():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 امروز", callback_data="chessgames_today", style="primary"),
        InlineKeyboardButton("📆 این هفته", callback_data="chessgames_week", style="primary")],
        [InlineKeyboardButton("🗓️ این ماه", callback_data="chessgames_month", style="primary"),
        InlineKeyboardButton("📚 کل بازی‌ها", callback_data="chessgames_all", style="primary")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="menu_pishva", style="danger")],
    ])

# ─── مدیران ───────────────────────────────────────────────────
def kb_admin_list(admins):
    rows = []
    for i in range(0, len(admins), 2):
        row = [InlineKeyboardButton(
            f"{'🟢' if a['is_active'] else '🔴'} {a['display_name'] or a['full_name']}",
            callback_data=f"admin_view_{a['telegram_id']}"
        , style="primary") for a in admins[i:i+2]]
        rows.append(row)
    rows.append(kb_back_row("main"))
    return InlineKeyboardMarkup(rows)

def kb_admin_actions(tid, is_active=True):
    """FIX: قبلاً دکمه‌ی «🚫 اخراج» بدون توجه به وضعیتِ فعلیِ مدیر همیشه
    نشون داده می‌شد و هیچ دکمه‌ای برای برگردوندنِ مدیرِ اخراج‌شده نبود.
    حالا: اگه مدیر فعاله «🚫 اخراج» نشون داده می‌شه، وگرنه «🔄 احیا»."""
    kick_or_revive = (
        InlineKeyboardButton("🚫 اخراج", callback_data=f"admin_kick_{tid}", style="danger")
        if is_active else
        InlineKeyboardButton("🔄 احیا", callback_data=f"admin_revive_{tid}", style="success")
    )
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬆️ دسترسی‌ها", callback_data=f"admin_perms_{tid}", style="primary"),
        InlineKeyboardButton("⚠️ ثبت اخطار", callback_data=f"admin_warn_{tid}", style="danger")],
        [InlineKeyboardButton("🧹 پاک‌کردن اخطارها", callback_data=f"admin_clearwarn_{tid}", style="danger"),
        kick_or_revive],
        [InlineKeyboardButton("💬 ارسال پیام", callback_data=f"admin_msg_{tid}", style="success"),
        InlineKeyboardButton("📋 اعطای وظیفه", callback_data=f"admin_task_{tid}", style="primary")],
        [InlineKeyboardButton("🔍 پیگیری اقدامات", callback_data=f"adminlogsmenu_{tid}", style="primary"),
        InlineKeyboardButton("👁️ پروفایل", callback_data=f"admin_profile_{tid}", style="primary")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="menu_admins", style="danger")],
    ])

def kb_admin_permissions(tid, perms):
    def tog(k): return "✅" if perms.get(k, False) else "❌"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🔔 اعلان {tog('notifications')}", callback_data=f"perm_{tid}_notifications", style="primary"),
        InlineKeyboardButton(f"📰 اخبار {tog('news')}", callback_data=f"perm_{tid}_news", style="primary")],
        [InlineKeyboardButton(f"♟️ مسابقات {tog('match_management')}", callback_data=f"perm_{tid}_match_management", style="primary"),
        InlineKeyboardButton(f"👥 بازیکنان {tog('view_players')}", callback_data=f"perm_{tid}_view_players", style="primary")],
        [InlineKeyboardButton(f"⚠️ اخطار {tog('issue_warning')}", callback_data=f"perm_{tid}_issue_warning", style="danger"),
        InlineKeyboardButton(f"🚫 درخواست اخراج {tog('request_ban')}", callback_data=f"perm_{tid}_request_ban", style="danger")],
        [InlineKeyboardButton(f"❌ اخراج مستقیم {tog('direct_ban')}", callback_data=f"perm_{tid}_direct_ban", style="danger"),
        InlineKeyboardButton(f"📋 وظیفه {tog('assign_task')}", callback_data=f"perm_{tid}_assign_task", style="primary")],
        [InlineKeyboardButton(f"🚨 گزارش {tog('report')}", callback_data=f"perm_{tid}_report", style="primary"),
        InlineKeyboardButton(f"💤 ربات فعال {tog('bot_active')}", callback_data=f"perm_{tid}_bot_active", style="primary")],
        [InlineKeyboardButton(f"⚙️ تنظیمات {tog('settings_access')}", callback_data=f"perm_{tid}_settings_access", style="primary"),
        InlineKeyboardButton(f"🌟 ارشد {tog('senior_admin')}", callback_data=f"perm_{tid}_senior_admin", style="primary")],
        [InlineKeyboardButton(f"✏️ ویرایش مسابقه {tog('edit_delete_match')}", callback_data=f"perm_{tid}_edit_delete_match", style="primary"),
        InlineKeyboardButton(f"📡 مخابرات {tog('communications')}", callback_data=f"perm_{tid}_communications", style="primary")],
        [InlineKeyboardButton(f"🤖 دسترسی هوش مصنوعی {tog('ai_access')}", callback_data=f"perm_{tid}_ai_access", style="primary")],
        [InlineKeyboardButton(f"♟️ شطرنج زنده {tog('chess_access')}", callback_data=f"perm_{tid}_chess_access", style="primary")],
        [InlineKeyboardButton("✅ ذخیره و بازگشت", callback_data=f"admin_view_{tid}", style="danger")],
    ])

# ─── مخابرات ──────────────────────────────────────────────────
def kb_comms_pishva():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 پیام به ادمین", callback_data="comms_msg_admin", style="primary"),
        InlineKeyboardButton("📢 ارسال بیانیه", callback_data="comms_announce", style="success")],
        [InlineKeyboardButton("📨 پیام‌های دریافتی", callback_data="comms_inbox", style="primary"),
        InlineKeyboardButton("🔔 اعلانات اخیر", callback_data="comms_notifs", style="primary")],
        [InlineKeyboardButton("👁️ پیام ادمین‌ها", callback_data="comms_all_msgs", style="primary"),
        InlineKeyboardButton("📰 ارسال خبر", callback_data="comms_news", style="success")],
        [InlineKeyboardButton("📊 گزارشات", callback_data="comms_reports", style="primary"),
        InlineKeyboardButton("📜 تاریخچه بیانیات", callback_data="comms_ann_history", style="primary")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="back_main", style="danger")],
    ])

def kb_comms_admin():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 پیام به مدیر ارشد", callback_data="comms_msg_pishva", style="primary"),
        InlineKeyboardButton("💬 پیام به ادمین", callback_data="comms_msg_other", style="primary")],
        [InlineKeyboardButton("📨 پیام‌های دریافتی", callback_data="comms_inbox", style="primary"),
        InlineKeyboardButton("📜 بیانیات", callback_data="comms_ann_history", style="primary")],
        [InlineKeyboardButton("📰 اخبار", callback_data="comms_news_list", style="primary"),
        InlineKeyboardButton("🔙 بازگشت", callback_data="back_main", style="danger")],
    ])

def kb_announce_file():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📎 بله، پیوست کن", callback_data="ann_with_file", style="success"),
        InlineKeyboardButton("➡️ خیر، فقط متن", callback_data="ann_no_file", style="danger")],
    ])

# ─── وظایف ────────────────────────────────────────────────────
def kb_tasks_pishva():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 اعطای وظیفه", callback_data="task_assign", style="primary"),
        InlineKeyboardButton("📜 تاریخچه وظایف", callback_data="task_history", style="primary")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="back_main", style="danger")],
    ])

def kb_tasks_admin():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📌 پیگیری وظایف", callback_data="task_track", style="primary"),
        InlineKeyboardButton("🔙 بازگشت", callback_data="back_main", style="danger")],
    ])

def kb_task_status(task_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ انجام شد", callback_data=f"task_done_{task_id}", style="success"),
        InlineKeyboardButton("❌ انجام نشد", callback_data=f"task_fail_{task_id}", style="danger")],
    ])

def kb_task_history_filter():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 امروز", callback_data="thistory_today", style="primary"),
        InlineKeyboardButton("📆 این هفته", callback_data="thistory_week", style="primary")],
        [InlineKeyboardButton("✅ انجام‌شده", callback_data="thistory_done", style="success"),
        InlineKeyboardButton("❌ انجام‌نشده", callback_data="thistory_pending", style="danger")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="menu_tasks", style="danger")],
    ])

# ─── فیدبک ────────────────────────────────────────────────────
def kb_feedback_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 انتقاد", callback_data="fb_critique", style="primary"),
        InlineKeyboardButton("💡 پیشنهاد", callback_data="fb_suggestion", style="primary")],
        [InlineKeyboardButton("🏆 تقدیر", callback_data="fb_praise", style="primary"),
        InlineKeyboardButton("🔧 درخواست قابلیت", callback_data="fb_feature", style="primary")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="back_main", style="danger")],
    ])

def kb_feedback_pishva():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 انتقادات", callback_data="fb_view_critique", style="primary"),
        InlineKeyboardButton("💡 پیشنهادات", callback_data="fb_view_suggestion", style="primary")],
        [InlineKeyboardButton("🏆 تقدیرها", callback_data="fb_view_praise", style="primary"),
        InlineKeyboardButton("🔧 قابلیت‌ها", callback_data="fb_view_feature", style="primary")],
        [InlineKeyboardButton("📋 همه موارد", callback_data="fb_view_all", style="primary"),
        InlineKeyboardButton("🔙 بازگشت", callback_data="back_main", style="danger")],
    ])

# ─── راهنما ───────────────────────────────────────────────────
def kb_help_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏅 تورنمنت", callback_data="help_tournament", style="primary"),
        InlineKeyboardButton("👤 بازیکنان", callback_data="help_players", style="primary")],
        [InlineKeyboardButton("♟️ مسابقات", callback_data="help_matches", style="primary"),
        InlineKeyboardButton("📡 مخابرات", callback_data="help_comms", style="primary")],
        [InlineKeyboardButton("⚠️ اخطار", callback_data="help_warnings", style="danger"),
        InlineKeyboardButton("📋 وظایف", callback_data="help_tasks", style="primary")],
        [InlineKeyboardButton("❓ سوالات متداول", callback_data="help_faq", style="primary"),
        InlineKeyboardButton("🛠️ خطاهای احتمالی", callback_data="help_errors", style="primary")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="back_main", style="danger")],
    ])

# ─── تیم‌ها ───────────────────────────────────────────────────
def kb_teams_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 تیم‌ها", callback_data="teams_list", style="primary"),
        InlineKeyboardButton("➕ افزودن تیم", callback_data="teams_add", style="success")],
        [InlineKeyboardButton("⚙️ تنظیمات تیم", callback_data="teams_settings", style="primary"),
        InlineKeyboardButton("🔙 بازگشت", callback_data="back_matches", style="danger")],
    ])

def kb_team_list(teams):
    rows = []
    for i in range(0, len(teams), 2):
        row = [InlineKeyboardButton(f"🏆 {t['name']}", callback_data=f"team_view_{t['id']}", style="primary") for t in teams[i:i+2]]
        rows.append(row)
    rows.append(kb_back_row("teams_menu"))
    return InlineKeyboardMarkup(rows)

def kb_team_actions(team_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 بازیکنان تیم", callback_data=f"team_members_{team_id}", style="primary"),
        InlineKeyboardButton("👑 تنظیم سرگروه", callback_data=f"team_captain_{team_id}", style="primary")],
        [InlineKeyboardButton("⚠️ اخطارهای تیم", callback_data=f"team_warnings_{team_id}", style="danger"),
        InlineKeyboardButton("🗑️ حذف تیم", callback_data=f"team_delete_{team_id}", style="danger")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="teams_list", style="danger")],
    ])

def kb_confirm(yes_cb, no_cb, yes_label="✅ بله", no_label="❌ خیر"):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(yes_label, callback_data=yes_cb, style="primary"),
        InlineKeyboardButton(no_label, callback_data=no_cb, style="primary")],
    ])

def kb_access_request(req_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ تأیید", callback_data=f"req_approve_{req_id}", style="success"),
        InlineKeyboardButton("❌ رد", callback_data=f"req_reject_{req_id}", style="danger")],
        [InlineKeyboardButton("⏳ صف انتظار", callback_data=f"req_queue_{req_id}", style="primary"),
        InlineKeyboardButton("🚫 بلاک دائم", callback_data=f"req_blockask_{req_id}", style="danger")],
    ])

def kb_lottery_scope():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏫 فقط از یک کلاس", callback_data="lottery_class", style="primary"),
        InlineKeyboardButton("🌐 از همه کلاس‌ها", callback_data="lottery_all", style="primary")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="back_matches", style="danger")],
    ])

def kb_identity():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🪪 تغییر نام مدیر ارشد", callback_data="identity_pishva", style="primary"),
        InlineKeyboardButton("👥 تغییر نام مدیران", callback_data="identity_admin", style="primary")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="menu_pishva", style="danger")],
    ])

def kb_newyear_confirm():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ بله، ادامه بده", callback_data="newyear_yes", style="success"),
        InlineKeyboardButton("❌ انصراف", callback_data="menu_pishva", style="danger")],
    ])

def kb_update_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💤 خاموشی موقت برای آپدیت", callback_data="update_sleep", style="primary"),
        InlineKeyboardButton("📢 اعلام آپدیت", callback_data="update_announce", style="primary")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="menu_pishva", style="danger")],
    ])

# ─── داشبورد ──────────────────────────────────────────────────
def kb_dashboard_pishva():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 به‌روزرسانی", callback_data="dashboard_pishva", style="primary"),
        InlineKeyboardButton("🔙 بازگشت", callback_data="back_main", style="danger")],
    ])

def kb_dashboard_admin():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 به‌روزرسانی", callback_data="dashboard_admin", style="primary"),
        InlineKeyboardButton("🔙 بازگشت", callback_data="back_main", style="danger")],
    ])

# ─── Auto Backup ──────────────────────────────────────────────
def kb_auto_backup_settings(enabled, interval, fmt, period):
    e_icon = "✅" if enabled == "1" else "❌"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🔄 بکاپ خودکار {e_icon}", callback_data="abk_toggle", style="primary")],
        [InlineKeyboardButton(f"⏰ هر {interval} ساعت", callback_data="abk_interval", style="primary"),
        InlineKeyboardButton(f"📁 {fmt}", callback_data="abk_fmt", style="primary")],
        [InlineKeyboardButton(f"📊 بازه: {period}", callback_data="abk_period", style="primary")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="pishva_backup", style="danger")],
    ])

def kb_auto_backup_interval():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⏰ هر ۶ ساعت", callback_data="abk_set_interval_6", style="primary"),
        InlineKeyboardButton("⏰ هر ۱۲ ساعت", callback_data="abk_set_interval_12", style="primary")],
        [InlineKeyboardButton("⏰ هر ۲۴ ساعت", callback_data="abk_set_interval_24", style="primary"),
        InlineKeyboardButton("⏰ هر ۴۸ ساعت", callback_data="abk_set_interval_48", style="primary")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="pishva_auto_backup", style="danger")],
    ])

def kb_dbstatus_menu(current):
    label = "⚠️ تغییر به غیرفعال" if current == "1" else "🔗 فعال"
    action = "dbstatus_off" if current == "1" else "dbstatus_on"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(label, callback_data=action, style="primary")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="menu_pishva", style="danger")],
    ])

# ─── ثبت‌نام گروهی ────────────────────────────────────────────
def kb_bulk_preview():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ ثبت و تایید", callback_data="bulk_confirm", style="success")],
        [InlineKeyboardButton("✏️ ویرایش", callback_data="bulk_edit", style="primary"),
        InlineKeyboardButton("❌ لغو", callback_data="bulk_cancel", style="danger")],
    ])

# ─── یادآورها ─────────────────────────────────────────────────
def kb_reminders_menu(master_on, items):
    rows = [[InlineKeyboardButton(
        f"{'✅' if master_on else '❌'} فعال‌سازی کلی یادآورها",
        callback_data="reminder_toggle_master", style="success")]]
    for rtype, label, enabled, interval in items:
        icon = "✅" if enabled else "❌"
        rows.append([
            InlineKeyboardButton(f"{icon} {label}", callback_data=f"reminder_toggle_{rtype}", style="primary"),
            InlineKeyboardButton(f"⏰ هر {interval} ساعت", callback_data=f"reminder_interval_{rtype}", style="primary"),
        ])
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="menu_pishva", style="danger")])
    return InlineKeyboardMarkup(rows)


def kb_reminder_interval_options(rtype):
    hours_options = [1, 3, 6, 12, 24, 48]
    rows = []
    row = []
    for h in hours_options:
        row.append(InlineKeyboardButton(f"⏰ هر {h} ساعت", callback_data=f"reminder_set_{rtype}_{h}", style="primary"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="pishva_reminders", style="danger")])
    return InlineKeyboardMarkup(rows)


# ─── پخش خودکار به گروه/کانال ─────────────────────────────────
def kb_broadcast_menu(items):
    rows = []
    for key, label, group_key, g_on, channel_key, c_on in items:
        rows.append([InlineKeyboardButton(f"— {label} —", callback_data="noop_label", style="primary")])
        g_icon = "✅" if g_on else "❌"
        c_icon = "✅" if c_on else "❌"
        rows.append([
            InlineKeyboardButton(f"{g_icon} گروه", callback_data=f"broadcast_toggle_{group_key}", style="primary"),
            InlineKeyboardButton(f"{c_icon} کانال", callback_data=f"broadcast_toggle_{channel_key}", style="primary"),
        ])
        if key == "chess_ai_defeat":
            rows.append([InlineKeyboardButton("✏️ ویرایش متنِ اعلان", callback_data="pishva_chess_ai_broadcast_text", style="primary")])
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="menu_pishva", style="danger")])
    return InlineKeyboardMarkup(rows)


# ─── قرعه‌کشی پیشرفته ─────────────────────────────────────────
# ─── امنیت APS (صف انتظار و بلاک) ──────────────────────────────
def kb_security_panel():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⏳ صف انتظار", callback_data="security_queue", style="primary"),
        InlineKeyboardButton("🚫 بلاک‌شده‌ها", callback_data="security_blocked", style="danger")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="menu_pishva", style="danger")],
    ])

def kb_queue_list(queued):
    rows = []
    for i in range(0, len(queued), 2):
        row = [InlineKeyboardButton(
            f"⏳ {r['full_name'] or r['telegram_id']}",
            callback_data=f"queueview_{r['id']}"
        , style="primary") for r in queued[i:i+2]]
        rows.append(row)
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="security_panel", style="danger")])
    return InlineKeyboardMarkup(rows)

def kb_queue_item_actions(req_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ تأیید و عضویت", callback_data=f"queueapprove_{req_id}", style="success")],
        [InlineKeyboardButton("🔓 خروج از صف بدون تأیید", callback_data=f"queuerelease_{req_id}", style="danger")],
        [InlineKeyboardButton("🚫 بلاک دائم", callback_data=f"queueblockask_{req_id}", style="danger")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="security_queue", style="danger")],
    ])

def kb_block_confirm(token, back_cb="security_panel"):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚫 بله، بلاک کن", callback_data=f"blockconfirm_{token}", style="danger"),
        InlineKeyboardButton("❌ انصراف", callback_data=back_cb, style="danger")],
    ])

def kb_blocked_list(blocked):
    rows = []
    for i in range(0, len(blocked), 2):
        row = [InlineKeyboardButton(
            f"🚫 {b['full_name'] or b['telegram_id']}",
            callback_data=f"blockedview_{b['telegram_id']}"
        , style="primary") for b in blocked[i:i+2]]
        rows.append(row)
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="security_panel", style="danger")])
    return InlineKeyboardMarkup(rows)

def kb_blocked_item_actions(tid):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔓 آنبلاک", callback_data=f"unblock_{tid}", style="success")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="security_blocked", style="danger")],
    ])

def kb_adv_lottery_scope():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎯 هر دو طرف از یک کلاس", callback_data="adv_scope_same", style="primary")],
        [InlineKeyboardButton("🔀 هرکدام از یک کلاس متفاوت", callback_data="adv_scope_diff", style="primary")],
        [InlineKeyboardButton("🌐 از همه کلاس‌ها (آزاد)", callback_data="adv_scope_open", style="primary")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="back_matches", style="danger")],
    ])
