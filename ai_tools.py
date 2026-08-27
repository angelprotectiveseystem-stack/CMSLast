"""
ai_tools.py — تعریف «ابزارهای» دستیار هوشمند + ماتریس دسترسی نقش‌ها

این فایل دو کار می‌کنه:
۱) TOOL_DECLARATIONS: لیست تابع‌هایی که به Gemini معرفی می‌شن (اسم،
   توضیح فارسی، پارامترهای لازم) تا مدل بفهمه چه امکاناتی داره.
۲) TOOL_PERMISSIONS: این‌که هر نقش (پیشوا / مدیر مسابقات / مدیر امنیتی)
   اجازه‌ی اجرای کدوم تابع‌ها رو داره.

نکته‌ی امنیتی مهم: حتی اگه یه کاربر با ترفند مدل رو گول بزنه که یه
تابع غیرمجاز صدا بزنه، تابع dispatch() پایین دوباره از نو چک می‌کنه
که نقش کاربر واقعاً اجازه داره یا نه. یعنی هوش مصنوعی هیچ‌وقت خودش
تنها مرجع تصمیم امنیتی نیست.

برای اضافه‌کردن یه ابزار جدید در آینده:
  ۱) یه تعریف تابع به TOOL_DECLARATIONS اضافه کن
  ۲) نقش‌های مجازش رو به TOOL_PERMISSIONS اضافه کن
  ۳) یه شاخه‌ی elif به دیسپچر dispatch() اضافه کن
"""
import logging

import database as db
import workhours
import comms
from helpers import broadcast_to_admins, now_shamsi
from config import ROLE_PISHVA, ROLE_TOURNAMENT_MANAGER, ROLE_SECURITY_MANAGER

logger = logging.getLogger(__name__)

ALL_ROLES = [ROLE_PISHVA, ROLE_TOURNAMENT_MANAGER, ROLE_SECURITY_MANAGER]

# ────────────────────────────────────────────────────────────────
# ماتریس دسترسی — کلید = اسم تابع، مقدار = لیست نقش‌های مجاز
# ────────────────────────────────────────────────────────────────
TOOL_PERMISSIONS = {
    # ── ساعت کاری — فقط پیشوا ──
    "start_workhours":   [ROLE_PISHVA],
    "end_workhours":     [ROLE_PISHVA],

    # ── بازیکن‌ها — پیشوا و مدیر مسابقات ──
    "register_player":   [ROLE_PISHVA, ROLE_TOURNAMENT_MANAGER],
    "search_player":      ALL_ROLES,
    "warn_player":        [ROLE_PISHVA, ROLE_TOURNAMENT_MANAGER],
    "kick_player":        [ROLE_PISHVA, ROLE_TOURNAMENT_MANAGER],
    "revive_player":      [ROLE_PISHVA, ROLE_TOURNAMENT_MANAGER],

    # ── مسابقات و نتایج ──
    "create_tournament":  [ROLE_PISHVA, ROLE_TOURNAMENT_MANAGER],
    "list_tournaments":   ALL_ROLES,
    "record_match":       [ROLE_PISHVA, ROLE_TOURNAMENT_MANAGER],
    "recent_matches":     ALL_ROLES,

    # ── گزارش‌گیری — همه نقش‌ها ──
    "quick_stats":        ALL_ROLES,
    "system_status":      ALL_ROLES,

    # ── ارتباطات — فقط پیشوا ──
    "send_announcement":  [ROLE_PISHVA],
    "send_news":          [ROLE_PISHVA],

    # ── مدیریت ادمین‌ها — فقط پیشوا ──
    "list_admins":        [ROLE_PISHVA, ROLE_SECURITY_MANAGER],
    "warn_admin":         [ROLE_PISHVA],
    "clear_admin_warnings": [ROLE_PISHVA],
    "set_admin_role":     [ROLE_PISHVA],

    # ── امنیت — پیشوا و مدیر امنیتی ──
    "block_user":         [ROLE_PISHVA, ROLE_SECURITY_MANAGER],
    "unblock_user":       [ROLE_PISHVA, ROLE_SECURITY_MANAGER],

    # ── باز کردن پنل‌ها (دکمه‌ی شیشه‌ای زیر پیام) — دسترسی داخل خود دیسپچر هم چک می‌شود ──
    "open_panel":          ALL_ROLES,

    # ── اصلاح مسابقات ثبت‌شده — فقط پیشوا ──
    "edit_match_result":   [ROLE_PISHVA],
    "delete_match":        [ROLE_PISHVA],

    # ── ابزارهای سطح‌بالای مدیریتی — فقط پیشوا ──
    "get_admin_profile":   [ROLE_PISHVA],
    "set_system_status":   [ROLE_PISHVA],
    "toggle_ai_online":    [ROLE_PISHVA],
    "toggle_admin_ai_access": [ROLE_PISHVA],
    "toggle_bot_setting":  [ROLE_PISHVA],
}

# ────────────────────────────────────────────────────────────────
# پنل‌هایی که دستیار می‌تونه با دکمه‌ی شیشه‌ای بازشون کنه.
# کلید = چیزی که مدل به‌عنوان panel می‌فرسته؛ مقدار = (برچسب دکمه، callback_data، نقش‌های مجاز)
# نکته: خود دکمه هم وقتی لمس بشه از نو توسط هندلر اصلی‌اش چک دسترسی می‌شه (خط دفاعی دوم).
# ────────────────────────────────────────────────────────────────
PANEL_MAP = {
    "own_main":       ("🏠 پنل شخصی من", "back_main", ALL_ROLES),
    "pishva_main":    ("👑 پنل پیشوا", "menu_pishva", [ROLE_PISHVA]),
    "settings":       ("⚙️ تنظیمات ربات", "pishva_settings", [ROLE_PISHVA]),
    "logs":           ("🔍 پیگیری اقدامات", "pishva_logs", [ROLE_PISHVA]),
    "requests":       ("📥 درخواست‌های دسترسی", "pishva_requests", [ROLE_PISHVA]),
    "backup":         ("💾 بکاپ", "pishva_backup", [ROLE_PISHVA]),
    "workhours":      ("🕐 ساعت کاری", "pishva_workhours", [ROLE_PISHVA]),
    "security_panel": ("🛡️ پنل امنیتی APS", "security_panel", [ROLE_PISHVA]),
    "admins_list":    ("👥 مدیریت مدیران", "menu_admins", [ROLE_PISHVA]),
    "ai_admin_logs":  ("🗂️ سوابق AI ادمین‌ها", "ai_admlog_menu", [ROLE_PISHVA]),
    "matches":        ("♟️ مدیریت مسابقات", "menu_matches", ALL_ROLES),
    "players":        ("👤 مدیریت بازیکنان", "menu_players", ALL_ROLES),
    "dashboard":      ("📊 داشبورد", "dashboard_pishva", [ROLE_PISHVA]),
    "admin_profile":  (None, "admin_view_{tid}", [ROLE_PISHVA]),  # نیاز به identifier داره
}

# ────────────────────────────────────────────────────────────────
# تعریف تابع‌ها برای Gemini (فرمت OpenAPI-schema که Gemini می‌خواد)
# ────────────────────────────────────────────────────────────────
TOOL_DECLARATIONS = [
    {
        "name": "start_workhours",
        "description": "شروع ساعت کاری ربات برای همه‌ی مدیران. اختیاری: بعد از چند دقیقه خودکار بسته بشه.",
        "parameters": {
            "type": "object",
            "properties": {
                "autoend_minutes": {"type": "integer", "description": "چند دقیقه دیگه خودکار پایان یابد (اختیاری، اگر نگفت خالی بذار)"},
            },
        },
    },
    {
        "name": "end_workhours",
        "description": "پایان‌دادن دستی به ساعت کاری ربات.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "register_player",
        "description": "ثبت یک بازیکن جدید با نام کامل و نام کلاس.",
        "parameters": {
            "type": "object",
            "properties": {
                "full_name": {"type": "string", "description": "نام و نام‌خانوادگی بازیکن"},
                "class_name": {"type": "string", "description": "نام کلاس بازیکن"},
            },
            "required": ["full_name", "class_name"],
        },
    },
    {
        "name": "search_player",
        "description": "جست‌وجوی بازیکن بر اساس نام یا بخشی از نام، برای دیدن اطلاعات و آمارش.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "نام یا بخشی از نام بازیکن"}},
            "required": ["query"],
        },
    },
    {
        "name": "warn_player",
        "description": "دادن اخطار به یک بازیکن با ذکر دلیل.",
        "parameters": {
            "type": "object",
            "properties": {
                "full_name": {"type": "string"},
                "reason": {"type": "string", "description": "دلیل اخطار"},
            },
            "required": ["full_name", "reason"],
        },
    },
    {
        "name": "kick_player",
        "description": "حذف/اخراج یک بازیکن از سیستم.",
        "parameters": {
            "type": "object",
            "properties": {"full_name": {"type": "string"}},
            "required": ["full_name"],
        },
    },
    {
        "name": "revive_player",
        "description": "بازگردانی یک بازیکن اخراج/معلق‌شده به حالت فعال.",
        "parameters": {
            "type": "object",
            "properties": {"full_name": {"type": "string"}},
            "required": ["full_name"],
        },
    },
    {
        "name": "create_tournament",
        "description": "ساخت یک مسابقه/تورنومنت جدید، با امکان تعیین آن به‌عنوان پیش‌فرض.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "نام تورنومنت"},
                "set_default": {"type": "boolean", "description": "آیا این تورنومنت پیش‌فرض بشه"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "list_tournaments",
        "description": "نمایش لیست همه‌ی تورنومنت‌ها و وضعیتشان.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "record_match",
        "description": "ثبت یک مسابقه‌ی جدید همراه با نتیجه‌اش بین دو بازیکن.",
        "parameters": {
            "type": "object",
            "properties": {
                "white_name": {"type": "string", "description": "نام بازیکن اول (سفید)"},
                "black_name": {"type": "string", "description": "نام بازیکن دوم (سیاه)"},
                "winner": {
                    "type": "string",
                    "description": "برنده: دقیقاً نام یکی از دو بازیکن، یا کلمه‌ی 'مساوی' اگر تساوی بود",
                },
                "reason": {"type": "string", "description": "دلیل تساوی/نتیجه (اختیاری)"},
            },
            "required": ["white_name", "black_name", "winner"],
        },
    },
    {
        "name": "edit_match_result",
        "description": "اصلاح نتیجه‌ی یک مسابقه‌ی از قبل ثبت‌شده (با شناسه‌ی مسابقه که از recent_matches می‌گیری). آمار برد/باخت/مساوی بازیکن‌ها خودکار درست می‌شود.",
        "parameters": {
            "type": "object",
            "properties": {
                "match_id": {"type": "integer", "description": "شناسه‌ی مسابقه (عدد # جلوی هر ردیف در recent_matches)"},
                "winner": {"type": "string", "description": "برنده‌ی صحیح: 'white'، 'black' یا 'draw'"},
                "reason": {"type": "string", "description": "دلیل اصلاح (اختیاری)"},
            },
            "required": ["match_id", "winner"],
        },
    },
    {
        "name": "delete_match",
        "description": "حذف کامل یک مسابقه‌ی ثبت‌شده (مثلاً اگر اشتباهی ثبت شده). اگر نتیجه داشته، آمار بازیکن‌ها خودکار اصلاح می‌شود.",
        "parameters": {
            "type": "object",
            "properties": {
                "match_id": {"type": "integer", "description": "شناسه‌ی مسابقه (عدد # جلوی هر ردیف در recent_matches)"},
            },
            "required": ["match_id"],
        },
    },
    {
        "name": "recent_matches",
        "description": "نمایش آخرین نتایج مسابقات ثبت‌شده.",
        "parameters": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "description": "چند مسابقه‌ی اخیر (پیش‌فرض ۵)"}},
        },
    },
    {
        "name": "quick_stats",
        "description": "آمار کلی: تعداد بازیکنان فعال، تعداد مسابقات، تعداد کلاس‌ها و مانند آن.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "system_status",
        "description": "وضعیت فعلی سیستم: ساعت کاری باز است یا نه، تعداد درخواست‌های در انتظار و غیره.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "send_announcement",
        "description": "ارسال یک بیانیه‌ی رسمی برای همه‌ی مدیران.",
        "parameters": {
            "type": "object",
            "properties": {"text": {"type": "string", "description": "متن بیانیه"}},
            "required": ["text"],
        },
    },
    {
        "name": "send_news",
        "description": "ارسال یک خبر برای همه‌ی مدیران.",
        "parameters": {
            "type": "object",
            "properties": {"text": {"type": "string", "description": "متن خبر"}},
            "required": ["text"],
        },
    },
    {
        "name": "list_admins",
        "description": "نمایش لیست همه‌ی مدیران و نقششان.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "warn_admin",
        "description": "دادن اخطار به یک مدیر (با یوزرنیم یا نام) با ذکر دلیل.",
        "parameters": {
            "type": "object",
            "properties": {
                "identifier": {"type": "string", "description": "یوزرنیم (با یا بدون @) یا نام کامل مدیر"},
                "reason": {"type": "string"},
            },
            "required": ["identifier", "reason"],
        },
    },
    {
        "name": "clear_admin_warnings",
        "description": "پاک‌کردن اخطارهای یک مدیر (صفر کردن شمارنده‌ی اخطار). برای اصلاح یا بخشیدن اخطارهای قبلی.",
        "parameters": {
            "type": "object",
            "properties": {
                "identifier": {"type": "string", "description": "آیدی عددی، یوزرنیم یا نام کامل مدیر"},
            },
            "required": ["identifier"],
        },
    },
    {
        "name": "set_admin_role",
        "description": "تغییر نقش یک مدیر بین «مدیر مسابقات» و «مدیر امنیتی».",
        "parameters": {
            "type": "object",
            "properties": {
                "identifier": {"type": "string", "description": "آیدی عددی، یوزرنیم یا نام کامل مدیر"},
                "new_role": {"type": "string", "enum": ["tournament_manager", "security_manager"],
                             "description": "نقش جدید"},
            },
            "required": ["identifier", "new_role"],
        },
    },
    {
        "name": "block_user",
        "description": "مسدودکردن یک کاربر تلگرام از دسترسی به ربات، با ذکر آیدی عددی یا یوزرنیم و دلیل.",
        "parameters": {
            "type": "object",
            "properties": {
                "identifier": {"type": "string", "description": "آیدی عددی تلگرام یا یوزرنیم"},
                "reason": {"type": "string"},
            },
            "required": ["identifier", "reason"],
        },
    },
    {
        "name": "unblock_user",
        "description": "رفع مسدودیت یک کاربر تلگرام.",
        "parameters": {
            "type": "object",
            "properties": {"identifier": {"type": "string", "description": "آیدی عددی تلگرام یا یوزرنیم"}},
            "required": ["identifier"],
        },
    },
    {
        "name": "open_panel",
        "description": (
            "باز کردن یک پنل/بخش از ربات با یک دکمه‌ی شیشه‌ای زیر پیام، دقیقاً همون چیزی که از منو باز می‌شه. "
            "برای درخواست‌هایی مثل «پنل پیشوا رو باز کن»، «برو پنل تنظیمات»، «پنل فلان ادمین رو نشون بده» از این استفاده کن. "
            "برای «admin_profile» حتماً identifier (یوزرنیم یا نام ادمین) رو هم بده."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "panel": {
                    "type": "string",
                    "description": (
                        "یکی از: own_main, pishva_main, settings, logs, requests, backup, workhours, "
                        "security_panel, admins_list, ai_admin_logs, matches, players, dashboard, admin_profile"
                    ),
                },
                "identifier": {"type": "string", "description": "فقط برای admin_profile: یوزرنیم یا نام مدیر"},
            },
            "required": ["panel"],
        },
    },
    {
        "name": "get_admin_profile",
        "description": "گزارش متنی کامل از یک مدیر: اخطارها، وضعیت، آخرین فعالیت، تعداد اقدامات ثبت‌شده.",
        "parameters": {
            "type": "object",
            "properties": {"identifier": {"type": "string", "description": "یوزرنیم یا نام مدیر"}},
            "required": ["identifier"],
        },
    },
    {
        "name": "set_system_status",
        "description": "تغییر وضعیت امنیتی کل سیستم (normal=نرمال, bad=بد, danger=خطرناک, aps=APS). در حالت danger/aps ربات برای همه‌ی مدیران (به‌جز پیشوا) قفل می‌شود.",
        "parameters": {
            "type": "object",
            "properties": {"status": {"type": "string", "description": "normal | bad | danger | aps"}},
            "required": ["status"],
        },
    },
    {
        "name": "toggle_ai_online",
        "description": "روشن/خاموش‌کردن کلی دستیار هوشمند برای همه (وقتی خاموشه، پیام «هوش مصنوعی فعلا در دسترس نیست» دیده می‌شه).",
        "parameters": {
            "type": "object",
            "properties": {"online": {"type": "boolean", "description": "true=روشن, false=خاموش"}},
            "required": ["online"],
        },
    },
    {
        "name": "toggle_admin_ai_access",
        "description": "اجازه یا عدم اجازه‌ی استفاده از دستیار هوشمند برای یک مدیر خاص.",
        "parameters": {
            "type": "object",
            "properties": {
                "identifier": {"type": "string", "description": "یوزرنیم یا نام مدیر"},
                "allow": {"type": "boolean"},
            },
            "required": ["identifier", "allow"],
        },
    },
    {
        "name": "toggle_bot_setting",
        "description": (
            "روشن/خاموش‌کردن یکی از سوییچ‌های عمومی ربات. کلیدهای معتبر: notifications_enabled, "
            "communications_enabled, help_enabled, match_registration_enabled, admin_login_enabled, "
            "bot_active_for_admins, team_mode_enabled, team_registration_enabled, managers_can_create_teams, "
            "admin_dashboard_enabled, ai_online"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "key": {"type": "string"},
                "value": {"type": "boolean"},
            },
            "required": ["key", "value"],
        },
    },
]


# ────────────────────────────────────────────────────────────────
# توابع کمکی داخلی
# ────────────────────────────────────────────────────────────────
async def _find_admin_by_identifier(identifier: str):
    identifier = (identifier or "").strip().lstrip("@")
    admins = await db.get_all_admins()
    for a in admins:
        uname = (a["username"] or "").lstrip("@")
        if uname.lower() == identifier.lower():
            return a
        if a["full_name"] and identifier.lower() in a["full_name"].lower():
            return a
        if identifier.isdigit() and a["telegram_id"] == int(identifier):
            return a
    return None


# ────────────────────────────────────────────────────────────────
# دیسپچر اصلی — این تابع صداش می‌شه، هم چک دسترسی می‌کنه هم اجرا
# ────────────────────────────────────────────────────────────────
async def dispatch(name: str, args: dict, caller_id: int, caller_role: str, ctx) -> str:
    """
    اجرای واقعی یک ابزار. خروجی: پیام متنی فارسی (نتیجه‌ی عملیات یا خطا)
    که هم به مدل برگردونده می‌شه، هم خلاصه‌ش به کاربر گفته می‌شه.
    """
    allowed_roles = TOOL_PERMISSIONS.get(name)
    if allowed_roles is None:
        return f"❌ تابع ناشناخته: {name}"
    if caller_role not in allowed_roles:
        return "⛔ شما اجازه‌ی اجرای این عملیات را ندارید (خارج از محدوده‌ی نقش شما)."

    args = args or {}

    try:
        # ── ساعت کاری ──
        if name == "start_workhours":
            minutes = args.get("autoend_minutes")
            minutes = int(minutes) if minutes else None
            ts, extra = await workhours._do_start(ctx.bot, ctx.job_queue, minutes)
            return f"✅ ساعت کاری از {ts} آغاز شد.{extra}"

        elif name == "end_workhours":
            await workhours._do_end(ctx.bot, ctx.job_queue, reason="ai_assistant")
            return "✅ ساعت کاری پایان یافت."

        # ── بازیکن‌ها ──
        elif name == "register_player":
            class_id = await db.get_or_create_class(args["class_name"])
            pid = await db.create_player(args["full_name"], class_id)
            return f"✅ بازیکن «{args['full_name']}» در کلاس «{args['class_name']}» ثبت شد (شناسه {pid})."

        elif name == "search_player":
            rows = await db.search_players(args["query"])
            if not rows:
                return f"چیزی با «{args['query']}» پیدا نشد."
            lines = [f"- {r['full_name']} | کلاس: {r.get('class_name') or '—'} | برد {r['wins']} باخت {r['losses']} مساوی {r['draws']} | وضعیت: {r['status']} | اخطار: {r['warnings']}" for r in rows[:10]]
            return "نتایج جست‌وجو:\n" + "\n".join(lines)

        elif name == "warn_player":
            p = await db.get_player_by_name(args["full_name"])
            if not p:
                return f"بازیکنی به نام «{args['full_name']}» پیدا نشد."
            await db.add_player_warning(p["id"], args["reason"], caller_id)
            return f"⚠️ به {p['full_name']} اخطار ثبت شد. دلیل: {args['reason']}"

        elif name == "kick_player":
            p = await db.get_player_by_name(args["full_name"])
            if not p:
                return f"بازیکنی به نام «{args['full_name']}» پیدا نشد."
            await db.update_player(p["id"], status="kicked")
            return f"🚫 {p['full_name']} از سیستم اخراج شد."

        elif name == "revive_player":
            p = await db.get_player_by_name(args["full_name"])
            if not p:
                return f"بازیکنی به نام «{args['full_name']}» پیدا نشد."
            await db.update_player(p["id"], status="active", warnings=0)
            return f"✅ {p['full_name']} به حالت فعال بازگشت."

        # ── تورنومنت ──
        elif name == "create_tournament":
            tid, created = await db.get_or_create_tournament(args["name"], is_default=bool(args.get("set_default")))
            verb = "ساخته شد" if created else "از قبل وجود داشت"
            return f"🏆 تورنومنت «{args['name']}» {verb}" + (" و پیش‌فرض شد." if args.get("set_default") else ".")

        elif name == "list_tournaments":
            rows = await db.get_all_tournaments()
            if not rows:
                return "هیچ تورنومنتی ثبت نشده."
            lines = [f"- {r['name']} ({r['status']})" for r in rows]
            return "لیست تورنومنت‌ها:\n" + "\n".join(lines)

        # ── مسابقه/نتیجه ──
        elif name == "record_match":
            wp = await db.get_player_by_name(args["white_name"])
            bp = await db.get_player_by_name(args["black_name"])
            if not wp or not bp:
                missing = args["white_name"] if not wp else args["black_name"]
                return f"بازیکن «{missing}» پیدا نشد."
            tourn = await db.get_default_tournament()
            tid = tourn["id"] if tourn else None
            mid = await db.create_match(wp["id"], bp["id"], now_shamsi(), tid, caller_id)
            winner = args["winner"].strip()
            if winner in ("مساوی", "تساوی", "draw"):
                result = "draw"
            elif winner.lower() == args["white_name"].strip().lower() or winner == wp["full_name"]:
                result = "white"
            elif winner.lower() == args["black_name"].strip().lower() or winner == bp["full_name"]:
                result = "black"
            else:
                return f"مشخص نیست «{winner}» برنده‌ی کدام طرفه؛ لطفاً دقیقاً نام یکی از دو بازیکن یا «مساوی» را بگو."
            ok = await db.record_match_result(mid, result, args.get("reason", ""), caller_id)
            if not ok:
                return "این مسابقه قبلاً نتیجه داشته، دوباره ثبت نشد."
            return f"✅ نتیجه ثبت شد: {wp['full_name']} ⚔️ {bp['full_name']} → {'مساوی' if result=='draw' else (wp['full_name'] if result=='white' else bp['full_name']) + ' برد'}"

        elif name == "edit_match_result":
            mid = int(args["match_id"])
            winner_raw = str(args["winner"]).strip().lower()
            if winner_raw in ("white", "سفید"):
                new_result = "white"
            elif winner_raw in ("black", "سیاه"):
                new_result = "black"
            elif winner_raw in ("draw", "مساوی", "تساوی"):
                new_result = "draw"
            else:
                return "برنده باید 'white'، 'black' یا 'draw' باشد."
            try:
                m = await db.correct_match_result(mid, new_result, args.get("reason", ""), caller_id)
            except ValueError as e:
                return str(e)
            if m is None:
                return f"مسابقه‌ای با شناسه‌ی #{mid} پیدا نشد."
            return f"✅ نتیجه‌ی مسابقه‌ی #{mid} اصلاح شد و آمار بازیکن‌ها به‌روزرسانی شد."

        elif name == "delete_match":
            mid = int(args["match_id"])
            m = await db.delete_match_safely(mid)
            if m is None:
                return f"مسابقه‌ای با شناسه‌ی #{mid} پیدا نشد."
            return f"🗑️ مسابقه‌ی #{mid} حذف شد و آمار بازیکن‌ها (در صورت داشتن نتیجه) اصلاح شد."

        elif name == "recent_matches":
            limit = int(args.get("limit") or 5)
            rows = await db.get_matches_by_filter("all")
            rows = rows[:limit]
            if not rows:
                return "مسابقه‌ای ثبت نشده."
            lines = []
            for r in rows:
                res = r["result"] or "در انتظار"
                lines.append(f"- #{r['id']} | {r.get('white_name','?')} vs {r.get('black_name','?')} → {res}")
            return "آخرین مسابقات:\n" + "\n".join(lines)

        # ── گزارش‌گیری ──
        elif name == "quick_stats":
            players = await db.get_all_players()
            active = [p for p in players if p["status"] == "active"]
            matches = await db.get_matches_by_filter("all")
            classes = await db.get_all_classes()
            return (f"📊 آمار کلی:\n- بازیکنان فعال: {len(active)} از {len(players)}\n"
                    f"- تعداد کلاس‌ها: {len(classes)}\n- تعداد مسابقات ثبت‌شده: {len(matches)}")

        elif name == "system_status":
            active = (await db.get_setting("working_hours_active", "0")) == "1"
            pending = await db.get_pending_requests()
            return (f"🖥️ وضعیت سیستم:\n- ساعت کاری: {'باز' if active else 'بسته'}\n"
                    f"- درخواست‌های در انتظار: {len(pending)}")

        # ── ارتباطات ──
        elif name == "send_announcement":
            await comms._send_announcement(ctx.bot, args["text"], "", "")
            await db.create_announcement(args["text"], "", "")
            return "📢 بیانیه برای همه‌ی مدیران ارسال شد."

        elif name == "send_news":
            await broadcast_to_admins(ctx.bot, f"📰 خبر:\n\n{args['text']}")
            await db.create_news(args["text"])
            return "📰 خبر برای همه‌ی مدیران ارسال شد."

        # ── مدیریت ادمین‌ها ──
        elif name == "list_admins":
            admins = await db.get_all_admins()
            if not admins:
                return "هیچ مدیری ثبت نشده."
            lines = [f"- {a['full_name']} ({a['role']}) {'فعال' if a['is_active'] else 'غیرفعال'}" for a in admins]
            return "لیست مدیران:\n" + "\n".join(lines)

        elif name == "warn_admin":
            a = await _find_admin_by_identifier(args["identifier"])
            if not a:
                return f"مدیری با مشخصات «{args['identifier']}» پیدا نشد."
            await db.add_admin_warning(a["telegram_id"], args["reason"], caller_id)
            return f"⚠️ به {a['full_name']} اخطار داده شد. دلیل: {args['reason']}"

        elif name == "clear_admin_warnings":
            a = await _find_admin_by_identifier(args["identifier"])
            if not a:
                return f"مدیری با مشخصات «{args['identifier']}» پیدا نشد."
            await db.set_admin_warnings(a["telegram_id"], 0)
            return f"✅ اخطارهای {a['full_name']} پاک شد."

        elif name == "set_admin_role":
            a = await _find_admin_by_identifier(args["identifier"])
            if not a:
                return f"مدیری با مشخصات «{args['identifier']}» پیدا نشد."
            new_role = args["new_role"]
            if new_role not in (ROLE_TOURNAMENT_MANAGER, ROLE_SECURITY_MANAGER):
                return "نقش نامعتبر است."
            await db.set_admin_role(a["telegram_id"], new_role)
            label = "مدیر مسابقات" if new_role == ROLE_TOURNAMENT_MANAGER else "مدیر امنیتی"
            return f"✅ نقش {a['full_name']} به «{label}» تغییر کرد."

        # ── امنیت ──
        elif name == "block_user":
            ident = args["identifier"].strip().lstrip("@")
            tid = int(ident) if ident.isdigit() else None
            if tid is None:
                a = await _find_admin_by_identifier(ident)
                tid = a["telegram_id"] if a else None
            if tid is None:
                return f"کاربری با «{args['identifier']}» پیدا نشد."
            await db.block_user(tid, ident, ident, args["reason"], caller_id)
            return f"🚫 کاربر {ident} مسدود شد. دلیل: {args['reason']}"

        elif name == "unblock_user":
            ident = args["identifier"].strip().lstrip("@")
            tid = int(ident) if ident.isdigit() else None
            if tid is None:
                return "برای رفع مسدودیت، آیدی عددی تلگرام لازم است."
            await db.unblock_user(tid)
            return f"✅ کاربر {tid} از حالت مسدود خارج شد."

        # ── باز کردن پنل (دکمه‌ی شیشه‌ای) ──
        elif name == "open_panel":
            panel = (args.get("panel") or "").strip()
            info = PANEL_MAP.get(panel)
            if not info:
                return f"❌ پنل «{panel}» شناخته‌شده نیست."
            label, cb_template, allowed = info
            if caller_role not in allowed:
                return f"⛔ پنل «{panel}» خارج از دسترسی نقش شماست."
            if panel == "admin_profile":
                ident = args.get("identifier")
                if not ident:
                    return "برای باز کردن پروفایل یک مدیر، نام یا یوزرنیمش رو بگو."
                a = await _find_admin_by_identifier(ident)
                if not a:
                    return f"مدیری با مشخصات «{ident}» پیدا نشد."
                label = f"👤 پروفایل {a['full_name']}"
                cb = cb_template.format(tid=a["telegram_id"])
            else:
                cb = cb_template
            pending = ctx.user_data.setdefault("_ai_pending_buttons", [])
            pending.append((label, cb))
            return f"✅ دکمه‌ی «{label}» رو براتون آماده کردم، پایین پیام بزنید روش."

        # ── پروفایل کامل یک ادمین (متنی) ──
        elif name == "get_admin_profile":
            a = await _find_admin_by_identifier(args["identifier"])
            if not a:
                return f"مدیری با مشخصات «{args['identifier']}» پیدا نشد."
            logs = await db.get_action_logs("all", a["telegram_id"])
            role_map = {ROLE_TOURNAMENT_MANAGER: "🏆 مدیر مسابقات", ROLE_SECURITY_MANAGER: "🛡️ مدیر امنیتی"}
            try:
                import json as _json
                perms = _json.loads(a["permissions"])
                ai_ok = "✅" if perms.get("ai_access", True) else "⛔"
            except Exception:
                ai_ok = "؟"
            return (
                f"👤 {a['full_name']} ({role_map.get(a['role'], a['role'])})\n"
                f"🪪 یوزرنیم: {('@' + a['username']) if a['username'] else '—'}\n"
                f"🆔 آیدی: {a['telegram_id']}\n"
                f"وضعیت: {'✅ فعال' if a['is_active'] else '🔴 غیرفعال'} | اخطار: {a['warnings']}\n"
                f"دسترسی به هوش مصنوعی: {ai_ok}\n"
                f"تعداد اقدامات ثبت‌شده: {len(logs)}\n"
                f"آخرین فعالیت: {str(a['last_active'] or '')[:16]}"
            )

        # ── تغییر وضعیت امنیتی سیستم ──
        elif name == "set_system_status":
            status = (args.get("status") or "").strip().lower()
            if status not in ("normal", "bad", "danger", "aps"):
                return "وضعیت باید یکی از این‌ها باشد: normal، bad، danger، aps"
            await db.set_setting("system_status", status)
            await db.log_action(caller_id, "set_status", f"تغییر وضعیت به: {status} (توسط دستیار هوشمند)")
            if status in ("danger", "aps"):
                await broadcast_to_admins(
                    ctx.bot,
                    f"🔴 وضعیت سیستم به «{status}» تغییر کرد. دسترسی شما موقتاً محدود شده؛ منتظر دستور پیشوا باشید."
                )
            return f"✅ وضعیت سیستم به «{status}» تغییر کرد."

        # ── روشن/خاموش‌کردن کلی هوش مصنوعی ──
        elif name == "toggle_ai_online":
            online = bool(args.get("online", True))
            await db.set_setting("ai_online", "1" if online else "0")
            await db.log_action(caller_id, "toggle_ai_online", str(online))
            return f"✅ دستیار هوشمند {'روشن' if online else 'خاموش'} شد."

        # ── اجازه‌ی هوش مصنوعی به یک مدیر خاص ──
        elif name == "toggle_admin_ai_access":
            a = await _find_admin_by_identifier(args["identifier"])
            if not a:
                return f"مدیری با مشخصات «{args['identifier']}» پیدا نشد."
            allow = bool(args.get("allow", True))
            await db.set_admin_permission(a["telegram_id"], "ai_access", allow)
            await db.log_action(caller_id, "toggle_perm", f"ai_access: {allow}", a["telegram_id"])
            return f"✅ دسترسی هوش مصنوعی برای {a['full_name']} {'فعال' if allow else 'غیرفعال'} شد."

        # ── سوییچ‌های عمومی ربات ──
        elif name == "toggle_bot_setting":
            valid_keys = {
                "notifications_enabled", "communications_enabled", "help_enabled",
                "match_registration_enabled", "admin_login_enabled", "bot_active_for_admins",
                "team_mode_enabled", "team_registration_enabled", "managers_can_create_teams",
                "admin_dashboard_enabled", "ai_online",
            }
            key = args.get("key")
            if key not in valid_keys:
                return f"❌ کلید «{key}» معتبر نیست."
            value = bool(args.get("value", True))
            await db.set_setting(key, "1" if value else "0")
            await db.log_action(caller_id, "toggle_setting", f"{key} -> {value} (دستیار هوشمند)")
            return f"✅ «{key}» {'فعال' if value else 'غیرفعال'} شد."

        return f"❌ تابع «{name}» تعریف نشده."

    except Exception as e:
        logger.exception(f"AI tool '{name}' failed")
        return f"⚠️ در اجرای این عملیات خطایی رخ داد: {e}"
