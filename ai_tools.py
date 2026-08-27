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

    # ── امنیت — پیشوا و مدیر امنیتی ──
    "block_user":         [ROLE_PISHVA, ROLE_SECURITY_MANAGER],
    "unblock_user":       [ROLE_PISHVA, ROLE_SECURITY_MANAGER],
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

        elif name == "recent_matches":
            limit = int(args.get("limit") or 5)
            rows = await db.get_matches_by_filter("all")
            rows = rows[:limit]
            if not rows:
                return "مسابقه‌ای ثبت نشده."
            lines = []
            for r in rows:
                res = r["result"] or "در انتظار"
                lines.append(f"- {r.get('white_name','?')} vs {r.get('black_name','?')} → {res}")
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

        return f"❌ تابع «{name}» تعریف نشده."

    except Exception as e:
        logger.exception(f"AI tool '{name}' failed")
        return f"⚠️ در اجرای این عملیات خطایی رخ داد: {e}"
