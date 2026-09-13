import turso_db as aiosqlite
import asyncio
import json
import logging
from datetime import datetime, timedelta
from config import DB_PATH, STATUS_NORMAL, ROLE_PISHVA, PISHVA_ID

# درخواست‌های بازی شطرنجی که طرف مقابل بعد از این مدت به آن‌ها پاسخ نداده باشد،
# دیگر «در انتظار پاسخ» حساب نمی‌شوند و مانع ارسال درخواست جدید نمی‌شوند.
CHESS_REQUEST_EXPIRY_MINUTES = 30

logger = logging.getLogger(__name__)

# ─── کش کوتاه‌مدت برای get_setting/get_admin ───────────────────────────
# ریشه‌ی اصلیِ لگِ حسِ‌شده در شطرنج زنده: هر دیتابیس (اعم از get_setting یا
# get_admin) الان یک درخواستِ شبکه‌ایِ جداگانه به Turso (دیتابیسِ ابری) است،
# نه یک فایلِ محلی. هر تک حرکتِ شطرنج، قبل از اینکه اصلاً روی صفحه ثبت شود،
# از مسیرِ can_use_live_chess() سه بار پشتِ‌سرِهم (نه موازی) از این دو تابع
# استفاده می‌کند؛ یعنی هر حرکت = حداقل ۳ رفت‌وبرگشتِ شبکه‌ایِ اضافه، فقط برای
# چک‌کردنِ چیزی که تقریباً هیچ‌وقت (بینِ دو حرکتِ متوالی) عوض نمی‌شود: وضعیتِ
# قفلِ کلیِ شطرنج زنده و پرمیشن‌های ادمین. همین تاخیرِ شبکه‌ایِ تکرارشونده،
# روی هر حرکت، دقیقاً همان «سکته»ای است که حس می‌شود — نه خودِ کدِ انیمیشن.
# راه‌حل: نتیجه‌ی این دو تابع را برای چند ثانیه در حافظه نگه می‌داریم (TTL
# کوتاه، نه کش دائمی) تا حرکات پشتِ‌سرِهم مجبور به رفت‌وبرگشتِ شبکه‌ی تکراری
# نباشند، ولی تغییراتِ واقعی (روشن/خاموش‌کردنِ شطرنج، تغییرِ دسترسیِ ادمین)
# هم حداکثر با چند ثانیه تاخیر خودشان را نشان بدهند.
_SETTING_CACHE_TTL = 45  # ثانیه
# قبلاً ۴ ثانیه بود — این مقدار برای حرکاتِ پشتِ‌سرِهمِ شطرنج زنده (که واقعاً
# چند تا حرکت توی چند ثانیه اتفاق می‌افته) کافی بود، ولی برای ناوبریِ عادیِ
# آدمیزاد بین منوها (که بین هر کلیک چند ثانیه طول می‌کشه چون کاربر داره
# صفحه رو می‌خونه) عملاً کش همیشه سرد بود — یعنی هر کلیک، دوباره یک
# رفت‌وبرگشتِ کاملِ شبکه‌ای به Turso، دقیقاً همون کندیِ حس‌شده روی منوهایی
# مثل «مدیریت بازیکنان»/«مدیریت مسابقات» که چند تا تنظیمِ جداگانه رو چک
# می‌کنن. چون هر نوشتنِ واقعی (set_setting/تغییرات ادمین/بلاک-آنبلاک) همین
# الان کشِ مربوطه رو فوری invalidate می‌کنه، طولانی‌تر کردنِ TTL امنه: تغییرِ
# واقعی همون لحظه دیده می‌شه، فقط چیزی که تغییر نکرده مجبور نیست هر ۴ ثانیه
# یک‌بار دوباره از شبکه خونده بشه.
_setting_cache = {}   # key -> (value, expires_at_monotonic)
_admin_cache = {}     # telegram_id -> (row, expires_at_monotonic)

# ─── کش لیستِ ادمین‌ها + بازیکنانِ ادامه‌دهنده ──────────────────────
# FIX (کندیِ منوی شطرنج / ثبت مسابقه / پنل مدیر ارشد): get_all_admins و
# get_active_admins هیچ‌وقت کش نمی‌شدن — با اینکه get_admin (تکی) از قبل
# کش داشت. اما این دو تابع دقیقاً همون چیزی هستن که منوی شطرنج زنده (برای
# لیستِ حریف‌ها) و اکثرِ دکمه‌های پنلِ مدیر ارشد (لیستِ ادمین‌ها) روی هر
# کلیک صداشون می‌زنن؛ یعنی هر کلیک = یک اسکنِ کاملِ جدولِ admins روی شبکه
# به Turso، دقیقاً همون معادله‌ای که برای get_setting/get_admin حل شده بود
# ولی اینجا حل نشده بود. get_continuing_players (لیستِ بازیکنانِ مجاز برای
# ثبتِ مسابقه‌ی جدید) هم همین مشکل رو داشت. راه‌حل: همون الگوی TTL کوتاه،
# invalidate‌شونده روی هر نوشتنِ واقعی.
_admin_list_cache = {}       # "all" | "active" -> (rows, expires_at_monotonic)
_continuing_players_cache = {}  # "list" -> (rows, expires_at_monotonic)

# ─── کش لیست‌های بازیکنان/کلاس‌ها/تورنومنت‌ها/مسابقات ────────────────
# FIX (کندیِ منوی بازیکن‌ها / منوی شطرنج / پنل پیشوا): همون مشکلِ بالا،
# اینجا هم بود. get_all_players/get_all_classes/get_all_tournaments/
# get_matches_by_filter هیچ‌کدوم کش نمی‌شدن، و دقیقاً همین‌ها هستن که
# منوهای «بازیکن‌ها»، «شطرنج»، و خلاصه‌ی پنل پیشوا صداشون می‌زنن — در
# موردِ پنل پیشوا حتی ۵ تا از این‌ها پشتِ‌سرِهم (نه موازی) توی یک صفحه.
# همون الگوی TTL کوتاه + invalidate روی نوشتنِ واقعی.
_LIST_CACHE_TTL = 15  # ثانیه — کوتاه‌تر از کشِ تنظیمات چون این جدول‌ها بیشتر عوض می‌شن
_players_cache = {}      # "all" | "active" -> (rows, expires_at_monotonic)
_classes_cache = {}      # "all" -> (rows, expires_at_monotonic)
_tournaments_cache = {}  # "all" -> (rows, expires_at_monotonic)
_matches_cache = {}      # period -> (rows, expires_at_monotonic)

# ─── کش «بلاک بودن کاربر» ───────────────────────────────────────────
# block_gate روی *هر تک آپدیت* (هر پیام، هر دکمه، از هر نفر) قبل از هر
# چیز دیگه‌ای اجرا می‌شه و get_blocked_user رو صدا می‌زنه. یعنی این یکی
# حتی از get_admin/get_setting هم داغ‌تره — پرتکرارترین کوئری کل رباته
# و تا امروز اصلاً کش نمی‌شد. چند ثانیه تاخیر توی دیدنِ یک بلاکِ تازه
# (که خودِ ادمین همون لحظه انجامش داده و نتیجه رو می‌بینه) قابل‌قبوله.
_blocked_cache = {}   # telegram_id -> (row_or_None, expires_at_monotonic)

# مجموعه‌ای برای نگه‌داشتنِ رفرنسِ تسک‌های پس‌زمینه (fire-and-forget)
# تا گاربیج‌کالکتور وسط کار نابودشون نکنه («Task was destroyed but it
# is pending»)؛ با پایان هر تسک خودش از این ست حذف می‌شه.
_bg_tasks = set()


def _fire_and_forget(coro):
    """یک کوروتین رو در پس‌زمینه اجرا می‌کنه بدون این‌که صدازننده منتظرش
    بمونه. برای نوشتن‌هایی که نتیجه‌شون برای ادامه‌ی کار لازم نیست
    (لاگ کردن، به‌روزرسانیِ last_active و مشابه) — این‌جور نوشتن‌ها
    نباید کاربر رو معطلِ یک رفت‌وبرگشتِ شبکه‌ای به Turso نگه دارن."""
    task = asyncio.create_task(coro)
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)
    return task


_CACHE_MISS = object()  # سنتینل، چون خودِ مقدارِ کش‌شده می‌تونه None باشه
# (مثلاً «بلاک نیست») و نباید با «توی کش نیست/منقضی شده» قاطی بشه.


def _cache_get(store, key):
    import time
    hit = store.get(key)
    if hit and hit[1] > time.monotonic():
        return hit[0]
    return _CACHE_MISS


def _cache_set(store, key, value, ttl=None):
    import time
    store[key] = (value, time.monotonic() + (ttl if ttl is not None else _SETTING_CACHE_TTL))


def _invalidate_setting_cache(key=None):
    """بعد از هر تغییرِ واقعیِ یک تنظیم، بلافاصله کش را پاک کن تا کاربر
    مجبور نباشد چند ثانیه صبر کند تا اثرِ تغییرش را ببیند."""
    if key is None:
        _setting_cache.clear()
    else:
        _setting_cache.pop(key, None)


def _invalidate_admin_cache(telegram_id=None):
    if telegram_id is None:
        _admin_cache.clear()
    else:
        _admin_cache.pop(telegram_id, None)
    # هر تغییرِ ادمینی (عضو جدید/اخراج/برگشت/پرمیشن/نقش/اخطار) روی محتوای
    # لیست‌ها هم اثر می‌ذاره، پس هر دو لیست هم همین‌جا پاک می‌شن.
    _admin_list_cache.clear()


def _invalidate_blocked_cache(telegram_id=None):
    if telegram_id is None:
        _blocked_cache.clear()
    else:
        _blocked_cache.pop(telegram_id, None)


def _invalidate_continuing_players_cache():
    _continuing_players_cache.clear()


def _invalidate_players_cache():
    _players_cache.clear()
    _continuing_players_cache.clear()


def _invalidate_classes_cache():
    _classes_cache.clear()


def _invalidate_tournaments_cache():
    _tournaments_cache.clear()


def _invalidate_matches_cache():
    _matches_cache.clear()


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
        CREATE TABLE IF NOT EXISTS system_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY,
            telegram_id INTEGER UNIQUE,
            username TEXT,
            full_name TEXT,
            display_name TEXT,
            role TEXT,
            is_active INTEGER DEFAULT 1,
            warnings INTEGER DEFAULT 0,
            joined_at TEXT,
            last_active TEXT,
            permissions TEXT DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS classes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT,
            class_id INTEGER,
            status TEXT DEFAULT 'active',
            warnings INTEGER DEFAULT 0,
            notes TEXT DEFAULT '',
            is_elite INTEGER DEFAULT 0,
            is_special INTEGER DEFAULT 0,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            draws INTEGER DEFAULT 0,
            suspension_reason TEXT DEFAULT '',
            created_at TEXT,
            FOREIGN KEY(class_id) REFERENCES classes(id)
        );
        CREATE TABLE IF NOT EXISTS tournaments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            status TEXT DEFAULT 'active',
            is_default INTEGER DEFAULT 0,
            created_at TEXT,
            ended_at TEXT
        );
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            white_player_id INTEGER,
            black_player_id INTEGER,
            result TEXT DEFAULT NULL,
            draw_reason TEXT DEFAULT NULL,
            match_date TEXT,
            tournament_id INTEGER,
            created_by INTEGER,
            created_at TEXT,
            updated_by INTEGER,
            updated_at TEXT,
            is_pinned INTEGER DEFAULT 0,
            FOREIGN KEY(white_player_id) REFERENCES players(id),
            FOREIGN KEY(black_player_id) REFERENCES players(id),
            FOREIGN KEY(tournament_id) REFERENCES tournaments(id)
        );
        CREATE TABLE IF NOT EXISTS warnings_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_type TEXT,
            target_id INTEGER,
            reason TEXT,
            issued_by INTEGER,
            issued_at TEXT
        );
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER,
            receiver_id INTEGER,
            text TEXT,
            sent_at TEXT,
            is_read INTEGER DEFAULT 0,
            msg_type TEXT DEFAULT 'direct'
        );
        CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT,
            file_id TEXT,
            file_type TEXT,
            sent_at TEXT,
            is_pinned INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT,
            sent_at TEXT
        );
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assigned_to INTEGER,
            assigned_by INTEGER,
            title TEXT,
            description TEXT,
            status TEXT DEFAULT 'pending',
            fail_reason TEXT DEFAULT '',
            assigned_at TEXT,
            completed_at TEXT
        );
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER,
            fb_type TEXT,
            title TEXT,
            content TEXT,
            sent_at TEXT,
            reply TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS action_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER,
            action_type TEXT,
            description TEXT,
            target_id INTEGER,
            logged_at TEXT
        );
        CREATE TABLE IF NOT EXISTS access_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            username TEXT,
            full_name TEXT,
            role TEXT,
            message TEXT,
            status TEXT DEFAULT 'pending',
            requested_at TEXT
        );
        CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            slogan TEXT,
            team_code TEXT UNIQUE,
            requester_name TEXT,
            captain_id INTEGER,
            created_by INTEGER,
            created_at TEXT,
            status TEXT DEFAULT 'active',
            warnings INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS team_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER,
            player_id INTEGER,
            level TEXT DEFAULT '',
            is_reserve INTEGER DEFAULT 0,
            joined_at TEXT,
            FOREIGN KEY(team_id) REFERENCES teams(id),
            FOREIGN KEY(player_id) REFERENCES players(id)
        );
        CREATE TABLE IF NOT EXISTS team_matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team1_id INTEGER,
            team2_id INTEGER,
            match_type TEXT,
            scoring_method TEXT,
            round_num INTEGER,
            created_by INTEGER,
            created_at TEXT,
            status TEXT DEFAULT 'pending'
        );
        CREATE TABLE IF NOT EXISTS team_match_boards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_match_id INTEGER,
            board_num INTEGER,
            player1_id INTEGER,
            player2_id INTEGER,
            result TEXT,
            FOREIGN KEY(team_match_id) REFERENCES team_matches(id)
        );
        CREATE TABLE IF NOT EXISTS backups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            label TEXT,
            period TEXT,
            format TEXT,
            file_data TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS blocked_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE,
            username TEXT,
            full_name TEXT,
            reason TEXT,
            blocked_by INTEGER,
            blocked_at TEXT
        );
        CREATE TABLE IF NOT EXISTS ai_chat_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            role TEXT,
            title TEXT DEFAULT '',
            started_at TEXT,
            last_message_at TEXT
        );
        CREATE TABLE IF NOT EXISTS ai_chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            sender TEXT,
            text TEXT,
            sent_at TEXT,
            FOREIGN KEY(session_id) REFERENCES ai_chat_sessions(id)
        );
        CREATE TABLE IF NOT EXISTS chess_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            requester_id INTEGER,
            target_id INTEGER,
            status TEXT DEFAULT 'pending',
            time_control INTEGER DEFAULT 300,
            requester_color TEXT DEFAULT 'random',
            created_at TEXT,
            responded_at TEXT
        );
        CREATE TABLE IF NOT EXISTS chess_games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT UNIQUE,
            white_id INTEGER,
            black_id INTEGER,
            white_name TEXT,
            black_name TEXT,
            fen TEXT,
            pgn TEXT DEFAULT '',
            status TEXT DEFAULT 'active',
            winner_id INTEGER,
            last_move_from TEXT,
            last_move_to TEXT,
            white_time INTEGER DEFAULT 300,
            black_time INTEGER DEFAULT 300,
            last_move_at TEXT,
            draw_offer_by INTEGER,
            created_at TEXT,
            finished_at TEXT
        );
        CREATE TABLE IF NOT EXISTS chess_chat (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT,
            sender_id INTEGER,
            sender_name TEXT,
            text TEXT,
            sent_at TEXT
        );
        CREATE TABLE IF NOT EXISTS stranger_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            username TEXT,
            full_name TEXT,
            action TEXT,
            ts TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_stranger_log_tid_ts ON stranger_log(telegram_id, ts);
        CREATE TABLE IF NOT EXISTS ai_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT,
            content TEXT,
            visibility TEXT DEFAULT 'pishva',
            created_by INTEGER,
            created_at TEXT
        );
        """)

        # ─── Lightweight migrations (add columns if missing) ──────────
        # از ALTER TABLE استفاده می‌کنیم چون ستون‌های جدید بعد از اولین
        # اجرای init_db اضافه شدن. اگه ستون از قبل باشه، خطا رو نادیده می‌گیریم.
        for stmt in (
            "ALTER TABLE matches ADD COLUMN claimed_by INTEGER",
            "ALTER TABLE matches ADD COLUMN claimed_at TEXT",
            "ALTER TABLE chess_requests ADD COLUMN time_control INTEGER DEFAULT 300",
            "ALTER TABLE chess_requests ADD COLUMN requester_color TEXT DEFAULT 'random'",
            "ALTER TABLE chess_games ADD COLUMN white_elo_change INTEGER",
            "ALTER TABLE chess_games ADD COLUMN black_elo_change INTEGER",
            "ALTER TABLE chess_games ADD COLUMN white_msg_id INTEGER",
            "ALTER TABLE chess_games ADD COLUMN black_msg_id INTEGER",
            "ALTER TABLE chess_games ADD COLUMN ai_level TEXT",
            "ALTER TABLE ai_memory ADD COLUMN visibility TEXT DEFAULT 'pishva'",
            # این یکی رو دیر اضافه کردیم: جدول ai_memory قبلاً روی دیتابیس واقعی
            # (Turso) بدون ستون content ساخته شده بود، و چون CREATE TABLE IF NOT
            # EXISTS وقتی جدول از قبل هست هیچ کاری نمی‌کنه، content هیچ‌وقت واقعاً
            # اضافه نمی‌شد — نتیجه‌ش این بود که هر ثبتِ حافظه (remember_note،
            # send_announcement، message_admin و...) با خطای «no column named
            # content» شکست می‌خورد و عملاً کل قابلیت حافظه‌ی بلندمدت کار نمی‌کرد.
            "ALTER TABLE ai_memory ADD COLUMN content TEXT",
            # ─── هشدار حذف مشکوک: اسنپ‌شات (برای بازگردانیِ حذف‌های واقعی مثل
            # حذف مسابقه) و پرچمِ «قبلاً خنثی شده» (تا دکمه‌ی خنثی‌سازی روی
            # یک اقدام دوبار اجرا نشه) ───
            "ALTER TABLE action_logs ADD COLUMN snapshot TEXT",
            "ALTER TABLE action_logs ADD COLUMN undone INTEGER DEFAULT 0",
        ):
            try:
                await db.execute(stmt)
            except Exception:
                pass  # ستون قبلاً وجود داره

        # Default settings
        defaults = {
            "system_status": STATUS_NORMAL,
            "notifications_enabled": "1",
            "communications_enabled": "1",
            "help_enabled": "1",
            "match_registration_enabled": "1",
            "admin_login_enabled": "1",
            "bot_active_for_admins": "1",
            "working_hours_active": "0",
            "workhours_autoend_enabled": "0",
            "workhours_reminder_enabled": "0",
            "workhours_reminder_minutes": "60",
            "repair_mode": "0",
            "repair_reason": "",
            "default_tournament_id": "",
            "pishva_display_name": "مدیر ارشد",
            "team_mode_enabled": "0",
            "team_registration_enabled": "1",
            "managers_can_create_teams": "0",
            "announcement_group_id": "",
            "bot_update_mode": "0",
            "ai_online": "1",
            "live_chess_enabled": "1",
            # ─── هشدار حذف مشکوک (پنل تنظیمات مدیر ارشد) ───
            "suspicious_alert_enabled": "1",
            "suspicious_deletion_threshold": "5",
            "suspicious_deletion_window_minutes": "10",
            # ─── روشن/خاموشِ جداگانه‌ی دو پنل وب (لینک‌دار) ───
            "principal_panel_enabled": "1",
            "admin_webpanel_enabled": "1",
        }
        for k, v in defaults.items():
            await db.execute(
                "INSERT OR IGNORE INTO system_settings(key, value) VALUES (?, ?)",
                (k, v)
            )
        await db.commit()
    logger.info("Database initialized.")


# ─── Settings ────────────────────────────────────────────────
async def get_setting(key: str, default="") -> str:
    cached = _cache_get(_setting_cache, key)
    if cached is not _CACHE_MISS:
        return cached
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM system_settings WHERE key=?", (key,)) as cur:
            row = await cur.fetchone()
            value = row[0] if row else default
            _cache_set(_setting_cache, key, value)
            return value


async def get_settings_bulk(keys, default="1") -> dict:
    """مثلِ get_setting ولی برای چند کلید با هم. FIX (کندیِ پنلِ تنظیمات):
    قبلاً هرکدوم از این کلیدها با asyncio.gather «هم‌زمان» صدا زده می‌شدن، ولی
    چون Turso دور و کندِ‌رفت‌وبرگشته، هم‌زمانیِ سطحِ پایتون به معنیِ یک
    رفت‌وبرگشتِ شبکه‌ی واحد نبود — چند موجِ رفت‌وبرگشتِ جدا پشتِ‌سرِهم پیش
    می‌اومد. این تابع فقط کلیدهایی که در کش نیستن رو با یک کوئریِ
    IN(...) (یک رفت‌وبرگشتِ شبکه‌ی واحد، نه یکی به‌ازای هر کلید) می‌گیره."""
    result = {}
    missing = []
    for k in keys:
        cached = _cache_get(_setting_cache, k)
        if cached is not _CACHE_MISS:
            result[k] = cached
        else:
            missing.append(k)
    if missing:
        placeholders = ",".join("?" for _ in missing)
        async with aiosqlite.connect(DB_PATH) as conn:
            async with conn.execute(
                f"SELECT key, value FROM system_settings WHERE key IN ({placeholders})",
                missing,
            ) as cur:
                rows = await cur.fetchall()
        found = {row["key"]: row["value"] for row in rows}
        for k in missing:
            value = found.get(k, default)
            _cache_set(_setting_cache, k, value)
            result[k] = value
    return result


async def set_setting(key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO system_settings(key, value) VALUES (?, ?)",
            (key, value)
        )
        await db.commit()
    _invalidate_setting_cache(key)


# ─── Admins ───────────────────────────────────────────────────
async def get_admin(telegram_id: int):
    cached = _cache_get(_admin_cache, telegram_id)
    if cached is not _CACHE_MISS:
        return cached
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM admins WHERE telegram_id=?", (telegram_id,)) as cur:
            row = await cur.fetchone()
            _cache_set(_admin_cache, telegram_id, row)
            return row


async def get_all_admins():
    cached = _cache_get(_admin_list_cache, "all")
    if cached is not _CACHE_MISS:
        return cached
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM admins ORDER BY joined_at DESC") as cur:
            rows = await cur.fetchall()
            _cache_set(_admin_list_cache, "all", rows)
            return rows


async def get_active_admins():
    cached = _cache_get(_admin_list_cache, "active")
    if cached is not _CACHE_MISS:
        return cached
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM admins WHERE is_active=1") as cur:
            rows = await cur.fetchall()
            _cache_set(_admin_list_cache, "active", rows)
            return rows


async def create_admin(telegram_id, username, full_name, role):
    now = datetime.now().isoformat()
    default_perms = json.dumps({
        "notifications": True, "news": True, "match_management": True,
        "view_players": True, "issue_warning": True, "request_ban": True,
        "direct_ban": False, "assign_task": False, "report": True,
        "bot_active": True, "settings_access": False, "senior_admin": False,
        "edit_delete_match": True, "communications": True, "ai_access": True,
        "chess_access": True,
    })
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO admins(telegram_id,username,full_name,display_name,role,joined_at,last_active,permissions) VALUES (?,?,?,?,?,?,?,?)",
            (telegram_id, username, full_name, full_name, role, now, now, default_perms)
        )
        await db.commit()
    _invalidate_admin_cache(telegram_id)


async def update_admin_activity(telegram_id):
    """این تابع روی *هر* پیام/دکمه‌ای که یک ادمین می‌زنه صدا زده می‌شه —
    یعنی پرتکرارترین نوشتنِ کل ربات. قبلاً دو مشکل داشت: (۱) صدازننده
    منتظرِ یک رفت‌وبرگشتِ کاملِ شبکه‌ای به Turso می‌موند قبل از این‌که
    اصلاً به منطقِ دکمه برسه، (۲) بلافاصله بعدش کشِ ادمین رو پاک می‌کرد،
    یعنی همون کشی که قرار بود چک‌های بعدیِ همون کلیک رو رایگان کنه، خودش
    باعث می‌شد چک بعدی دوباره یک رفت‌وبرگشتِ تازه بخواد. جمعِ این دو تا
    روی هر تک کلیک، دقیقاً همون کندیِ حس‌شده بود.
    راه‌حل: نوشتن در پس‌زمینه (بدون await کردنِ نتیجه)، و به‌جای پاک کردنِ
    کش، فقط فیلدِ last_active توی نسخه‌ی کش‌شده اصلاح می‌شه — چون این فیلد
    فقط برای نمایشِ «آنلاین/الان» استفاده می‌شه، نه برای تصمیمِ دسترسی."""
    now = datetime.now().isoformat()

    async def _write():
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE admins SET last_active=? WHERE telegram_id=?", (now, telegram_id))
            await db.commit()

    _fire_and_forget(_write())

    cached = _admin_cache.get(telegram_id)
    if cached is not None:
        row, expires_at = cached
        try:
            row["last_active"] = now
        except Exception:
            pass
        _admin_cache[telegram_id] = (row, expires_at)


# ─── ردیابیِ فعالیتِ کاربرهای «غریبه» (نه مدیر ارشد، نه ادمینِ ثبت‌شده) ──
# هر پیام یا دکمه‌ای که این‌جور کاربرها بزنن، این‌جا لاگ می‌شه؛ هم برای این‌که
# توی لیست «آنلاین/الان» دیده بشن، هم برای این‌که با زدن دکمه‌ی جزییات دقیقاً
# معلوم بشه کی هستن و چیکار کردن.
async def record_stranger_activity(telegram_id: int, username: str, full_name: str, action: str):
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO stranger_log(telegram_id, username, full_name, action, ts) VALUES (?,?,?,?,?)",
            (telegram_id, username or "", full_name or "", action or "", now)
        )
        await db.commit()


async def get_recent_strangers(minutes: int = 60, limit: int = 20):
    """لیست غریبه‌های اخیراً فعال (آخرین فعالیتشون در N دقیقه‌ی گذشته)، جدیدترین اول.
    برای هر کدوم آخرین username/full_name شناخته‌شده و تعداد کل اقدامات ثبت‌شده رو هم برمی‌گردونه."""
    threshold = (datetime.now() - timedelta(minutes=minutes)).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT telegram_id,
                   (SELECT username FROM stranger_log s2 WHERE s2.telegram_id = s1.telegram_id ORDER BY s2.id DESC LIMIT 1) AS username,
                   (SELECT full_name FROM stranger_log s2 WHERE s2.telegram_id = s1.telegram_id ORDER BY s2.id DESC LIMIT 1) AS full_name,
                   MAX(ts) AS last_active,
                   COUNT(*) AS action_count
            FROM stranger_log s1
            WHERE ts >= ?
            GROUP BY telegram_id
            ORDER BY last_active DESC
            LIMIT ?
            """,
            (threshold, limit)
        ) as cur:
            return await cur.fetchall()


async def get_stranger_log(telegram_id: int, limit: int = 15):
    """ریزِ اقدامات یک غریبه‌ی خاص، جدیدترین اول — برای دکمه‌ی «جزییات»."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM stranger_log WHERE telegram_id=? ORDER BY id DESC LIMIT ?",
            (telegram_id, limit)
        ) as cur:
            return await cur.fetchall()


async def get_stranger_summary(telegram_id: int):
    """اولین و آخرین فعالیت + تعداد کل اقدامات یک غریبه (مستقل از بازه‌ی زمانی)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT
                (SELECT username FROM stranger_log WHERE telegram_id=? ORDER BY id DESC LIMIT 1) AS username,
                (SELECT full_name FROM stranger_log WHERE telegram_id=? ORDER BY id DESC LIMIT 1) AS full_name,
                MIN(ts) AS first_seen,
                MAX(ts) AS last_active,
                COUNT(*) AS action_count
            FROM stranger_log WHERE telegram_id=?
            """,
            (telegram_id, telegram_id, telegram_id)
        ) as cur:
            return await cur.fetchone()


# ─── حافظه‌ی بلندمدتِ دستیار هوشمند ────────────────────────────
# مستقل از تاریخچه‌ی هر گفتگو (که با هر «چت جدید»/بستن دستیار پاک می‌شه)،
# این‌جا یادداشت‌ها/مسائلی که دستیار درباره‌ی یه مدیر یا موضوع ثبت می‌کنه
# نگه‌داری می‌شه تا توی هر چتِ دیگه‌ای هم (حتی روزها بعد) در دسترسش باشه.
# visibility='all' یعنی محتوایی که همین الان هم برای همه‌ی مدیران عمومی
# بوده (بیانیه/خبر)، پس توی حافظه‌ی هر نقشی نشون داده می‌شه؛ visibility='pishva'
# یعنی یادداشت‌های خصوصی‌تر (پیام به یه مدیر خاص، اخطار، وظیفه) که فقط توی
# چتِ خودِ مدیر ارشد به‌عنوان زمینه برگردونده می‌شه.
async def add_memory_note(subject: str, content: str, visibility: str = "pishva", created_by: int = None):
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO ai_memory(subject, content, visibility, created_by, created_at) VALUES (?,?,?,?,?)",
            ((subject or "عمومی").strip() or "عمومی", (content or "").strip(), visibility, created_by, now)
        )
        await db.commit()


async def get_recent_memory(visibility_levels, limit: int = 8):
    placeholders = ",".join("?" * len(visibility_levels))
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            f"SELECT * FROM ai_memory WHERE visibility IN ({placeholders}) ORDER BY id DESC LIMIT ?",
            (*visibility_levels, limit)
        ) as cur:
            return await cur.fetchall()


async def search_memory(query: str, visibility_levels, limit: int = 10):
    like = f"%{query}%"
    placeholders = ",".join("?" * len(visibility_levels))
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            f"SELECT * FROM ai_memory WHERE (subject LIKE ? OR content LIKE ?) AND visibility IN ({placeholders}) "
            f"ORDER BY id DESC LIMIT ?",
            (like, like, *visibility_levels, limit)
        ) as cur:
            return await cur.fetchall()


async def delete_memory_note(memory_id: int) -> bool:
    """یه یادداشت مشخص رو با شناسه‌ش از حافظه‌ی بلندمدت پاک می‌کنه.
    True برمی‌گردونه اگه واقعاً چیزی حذف شده باشه، False اگه اون id وجود نداشت.
    نکته: کِرسِرِ لایه‌ی Turso (turso_db.py) اصلاً attribute به‌اسم rowcount نداره
    (نه sqlite3 خام است، نه aiosqlite واقعی) — قبلاً اینجا از cur.rowcount
    استفاده می‌شد که همیشه با AttributeError کرش می‌کرد، یعنی forget_note
    عملاً از روز اول کار نمی‌کرد. برای همین اول با یه SELECT وجودِ ردیف رو
    چک می‌کنیم، بعد اگه بود حذفش می‌کنیم."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT id FROM ai_memory WHERE id = ?", (memory_id,)) as cur:
            existing = await cur.fetchone()
        if existing is None:
            return False
        await db.execute("DELETE FROM ai_memory WHERE id = ?", (memory_id,))
        await db.commit()
        return True


async def get_admin_permission(telegram_id: int, perm: str) -> bool:
    admin = await get_admin(telegram_id)
    if not admin:
        return False
    try:
        perms = json.loads(admin["permissions"])
        return perms.get(perm, False)
    except Exception:
        return False


async def set_admin_permission(telegram_id: int, perm: str, value: bool):
    admin = await get_admin(telegram_id)
    if not admin:
        return
    try:
        perms = json.loads(admin["permissions"])
    except Exception:
        perms = {}
    perms[perm] = value
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE admins SET permissions=? WHERE telegram_id=?",
                          (json.dumps(perms), telegram_id))
        await db.commit()
    _invalidate_admin_cache(telegram_id)


# ─── شطرنج زنده — قفل امنیتی و سوییچ دستی ──────────────────────
async def is_chess_locked_by_status() -> bool:
    """در وضعیت خطرناک یا APS، شطرنج زنده برای همه — حتی مدیر ارشد — کاملاً
    قفل می‌شود و تا برگشتن وضعیت به «بد» یا «نرمال» دوباره فعال نمی‌شود."""
    status = await get_setting("system_status", STATUS_NORMAL)
    return status in ("danger", "aps")


async def is_chess_admin_switch_off() -> bool:
    """سوییچ دستیِ مدیر ارشد از پنل تنظیمات (روشن/خاموش شطرنج زنده)؛
    فقط روی مدیران عادی اثر دارد، نه خود مدیر ارشد."""
    return (await get_setting("live_chess_enabled", "1")) != "1"


async def can_use_live_chess(telegram_id: int) -> bool:
    """قفل نهایی و ترکیبی شطرنج زنده برای یک کاربر مشخص:
    ۱) وضعیت خطرناک/APS → برای همه (حتی مدیر ارشد) قفل.
    ۲) سوییچ دستی مدیر ارشد → فقط مدیران عادی را قفل می‌کند.
    ۳) دسترسی اختصاصی هر مدیر (chess_access) در پرمیشن‌های شخصی‌اش."""
    if await is_chess_locked_by_status():
        return False
    if telegram_id == PISHVA_ID:
        return True
    if await is_chess_admin_switch_off():
        return False
    admin = await get_admin(telegram_id)
    if not admin:
        return False
    try:
        perms = json.loads(admin["permissions"])
    except Exception:
        perms = {}
    return perms.get("chess_access", True)


async def update_admin_display_name(telegram_id: int, name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE admins SET display_name=? WHERE telegram_id=?", (name, telegram_id))
        await db.commit()
    _invalidate_admin_cache(telegram_id)


async def add_admin_warning(telegram_id: int, reason: str, issued_by: int):
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.batch():
            await db.execute("UPDATE admins SET warnings=warnings+1 WHERE telegram_id=?", (telegram_id,))
            await db.execute(
                "INSERT INTO warnings_log(target_type,target_id,reason,issued_by,issued_at) VALUES (?,?,?,?,?)",
                ("admin", telegram_id, reason, issued_by, now)
            )
        await db.commit()
    _invalidate_admin_cache(telegram_id)


async def kick_admin(telegram_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE admins SET is_active=0 WHERE telegram_id=?", (telegram_id,))
        await db.commit()
    _invalidate_admin_cache(telegram_id)


async def revive_admin(telegram_id: int):
    """برگردوندنِ مدیری که اخراج شده (is_active=0 -> 1) — پیش از این هیچ
    راهی برای برگردوندنِ یک مدیرِ اخراج‌شده وجود نداشت."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE admins SET is_active=1 WHERE telegram_id=?", (telegram_id,))
        await db.commit()
    _invalidate_admin_cache(telegram_id)


async def set_admin_warnings(telegram_id: int, count: int):
    """تنظیم دقیق تعداد اخطارهای یک ادمین (برای پاک‌کردن، count=0 بفرست)."""
    count = max(0, int(count))
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE admins SET warnings=? WHERE telegram_id=?", (count, telegram_id))
        await db.commit()
    _invalidate_admin_cache(telegram_id)


async def set_admin_role(telegram_id: int, new_role: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE admins SET role=? WHERE telegram_id=?", (new_role, telegram_id))
        await db.commit()
    _invalidate_admin_cache(telegram_id)


async def update_admin_role_active(telegram_id: int, new_role: str):
    """تغییر نقش یک ادمین که از قبل توی دیتابیس هست، همراه با فعال‌کردن دوباره‌ش
    (is_active=1) — برای وقتی که کاربر با کلیدواژه‌ی «تنظیم مدیر» روی یه نفر که
    قبلاً وجود داشته (حتی اگه اخراج/غیرفعال بوده) نقش جدید می‌ذاره."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE admins SET role=?, is_active=1 WHERE telegram_id=?",
            (new_role, telegram_id)
        )
        await db.commit()
    _invalidate_admin_cache(telegram_id)


# ─── Classes ─────────────────────────────────────────────────
async def get_all_classes():
    cached = _cache_get(_classes_cache, "all")
    if cached is not _CACHE_MISS:
        return cached
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM classes ORDER BY name") as cur:
            rows = await cur.fetchall()
            _cache_set(_classes_cache, "all", rows, ttl=_LIST_CACHE_TTL)
            return rows


async def get_class(class_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM classes WHERE id=?", (class_id,)) as cur:
            return await cur.fetchone()


async def create_class(name: str):
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO classes(name,created_at) VALUES (?,?)", (name, now))
        await db.commit()
    _invalidate_classes_cache()


async def rename_class(class_id: int, new_name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE classes SET name=? WHERE id=?", (new_name, class_id))
        await db.commit()
    _invalidate_classes_cache()


async def get_class_player_count(class_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) AS c FROM players WHERE class_id=?", (class_id,)
        ) as cur:
            row = await cur.fetchone()
            return row["c"] if row else 0


async def delete_class(class_id: int) -> bool:
    """کلاس رو فقط وقتی حذف می‌کنه که دیگه هیچ بازیکنی بهش وصل نباشه —
    تا هیچ بازیکنی با یک class_id یتیم/نامعتبر توی دیتابیس نمونه.
    خروجی: True اگه واقعاً حذف شد، False اگه به‌خاطر وجود بازیکن رد شد."""
    count = await get_class_player_count(class_id)
    if count > 0:
        return False
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM classes WHERE id=?", (class_id,))
        await db.commit()
    _invalidate_classes_cache()
    return True


# ─── Players ─────────────────────────────────────────────────
async def get_all_players():
    cached = _cache_get(_players_cache, "all")
    if cached is not _CACHE_MISS:
        return cached
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT p.*, c.name as class_name FROM players p LEFT JOIN classes c ON p.class_id=c.id ORDER BY p.full_name"
        ) as cur:
            rows = await cur.fetchall()
            _cache_set(_players_cache, "all", rows, ttl=_LIST_CACHE_TTL)
            return rows


async def get_active_players():
    cached = _cache_get(_players_cache, "active")
    if cached is not _CACHE_MISS:
        return cached
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT p.*, c.name as class_name FROM players p LEFT JOIN classes c ON p.class_id=c.id WHERE p.status='active' ORDER BY p.full_name"
        ) as cur:
            rows = await cur.fetchall()
            _cache_set(_players_cache, "active", rows, ttl=_LIST_CACHE_TTL)
            return rows


async def get_player(player_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT p.*, c.name as class_name FROM players p LEFT JOIN classes c ON p.class_id=c.id WHERE p.id=?",
            (player_id,)
        ) as cur:
            return await cur.fetchone()


async def create_player(full_name: str, class_id: int):
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO players(full_name,class_id,created_at) VALUES (?,?,?)",
            (full_name, class_id, now)
        )
        await db.commit()
        _invalidate_players_cache()
        return cur.lastrowid


async def update_player_stats(player_id: int, result: str):
    """result: 'win','loss','draw'"""
    col = {"win": "wins", "loss": "losses", "draw": "draws"}.get(result)
    if col:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(f"UPDATE players SET {col}={col}+1 WHERE id=?", (player_id,))
            await db.commit()
        _invalidate_players_cache()


async def update_player(player_id: int, **kwargs):
    if not kwargs:
        return
    sets = ", ".join(f"{k}=?" for k in kwargs)
    vals = list(kwargs.values()) + [player_id]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE players SET {sets} WHERE id=?", vals)
        await db.commit()
    # class_id/status/warnings از طریق این تابع هم قابل‌تغییرن (مثلاً
    # ویرایش کلاس یا وضعیت بازیکن)، پس لیستِ بازیکنان و «ادامه‌دهنده‌ها» هم پاک بشن.
    _invalidate_players_cache()


async def delete_player_hard(player_id: int):
    """حذف کامل و غیرقابل‌بازگشتِ یک بازیکن — برخلاف اخراج/تعلیق
    (که فقط status رو عوض می‌کنن و بازیکن همچنان توی لیست کامل دیده
    می‌شه)، این تابع رکورد رو کاملاً از جدول players پاک می‌کنه؛ به‌همراه
    هر رکوردِ وابسته‌ای که با FOREIGN KEY به همین بازیکن اشاره داره
    (مسابقات ثبت‌شده، عضویت در تیم، سابقه‌ی اخطارها) تا چیزی یتیم نمونه."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.batch():
            await db.execute(
                "DELETE FROM warnings_log WHERE target_type='player' AND target_id=?", (player_id,))
            await db.execute("DELETE FROM team_members WHERE player_id=?", (player_id,))
            # team_match_boards.player1_id/player2_id هیچ FOREIGN KEY رسمی به
            # players ندارن (توی schema تعریف نشده)، ولی همون بازیکن رو ارجاع
            # می‌دن؛ بدون این دو خط، بعد از حذف بازیکن یک رفرنسِ یتیم توی
            # جدولِ برد-به-برد تیمی می‌موند که موقع نمایش، اسم بازیکنِ حذف‌شده
            # رو نشون نمی‌ده (چون get_player دیگه چیزی پیدا نمی‌کنه).
            await db.execute(
                "DELETE FROM team_match_boards WHERE player1_id=? OR player2_id=?",
                (player_id, player_id)
            )
            await db.execute(
                "DELETE FROM matches WHERE white_player_id=? OR black_player_id=?",
                (player_id, player_id)
            )
            await db.execute("DELETE FROM players WHERE id=?", (player_id,))
        await db.commit()
    _invalidate_players_cache()
    _invalidate_matches_cache()


async def add_player_warning(player_id: int, reason: str, issued_by: int):
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.batch():
            await db.execute("UPDATE players SET warnings=warnings+1 WHERE id=?", (player_id,))
            await db.execute(
                "INSERT INTO warnings_log(target_type,target_id,reason,issued_by,issued_at) VALUES (?,?,?,?,?)",
                ("player", player_id, reason, issued_by, now)
            )
        await db.commit()
    _invalidate_players_cache()


async def get_players_by_class(class_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT p.*, c.name as class_name FROM players p LEFT JOIN classes c ON p.class_id=c.id WHERE p.class_id=?",
            (class_id,)
        ) as cur:
            return await cur.fetchall()


async def search_players(query: str):
    like = f"%{query}%"
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT p.*, c.name as class_name FROM players p LEFT JOIN classes c ON p.class_id=c.id WHERE p.full_name LIKE ? OR c.name LIKE ?",
            (like, like)
        ) as cur:
            return await cur.fetchall()


async def get_continuing_players():
    """Players with active status, no dangerous warnings, not suspended"""
    cached = _cache_get(_continuing_players_cache, "list")
    if cached is not _CACHE_MISS:
        return cached
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT p.*, c.name as class_name FROM players p LEFT JOIN classes c ON p.class_id=c.id WHERE p.status='active' AND p.warnings < 3 ORDER BY p.full_name"
        ) as cur:
            rows = await cur.fetchall()
            _cache_set(_continuing_players_cache, "list", rows)
            return rows


# ─── Tournaments ─────────────────────────────────────────────
async def get_all_tournaments():
    cached = _cache_get(_tournaments_cache, "all")
    if cached is not _CACHE_MISS:
        return cached
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM tournaments ORDER BY created_at DESC") as cur:
            rows = await cur.fetchall()
            _cache_set(_tournaments_cache, "all", rows, ttl=_LIST_CACHE_TTL)
            return rows


async def get_tournament(tid: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM tournaments WHERE id=?", (tid,)) as cur:
            return await cur.fetchone()


async def get_default_tournament():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM tournaments WHERE is_default=1 AND status='active' LIMIT 1") as cur:
            return await cur.fetchone()


async def create_tournament(name: str) -> int:
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO tournaments(name,status,created_at) VALUES (?,?,?)",
            (name, "active", now)
        )
        await db.commit()
        _invalidate_tournaments_cache()
        return cur.lastrowid


async def update_tournament(tid: int, **kwargs):
    if not kwargs:
        return
    sets = ", ".join(f"{k}=?" for k in kwargs)
    vals = list(kwargs.values()) + [tid]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE tournaments SET {sets} WHERE id=?", vals)
        await db.commit()
    _invalidate_tournaments_cache()


async def set_default_tournament(tid: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.batch():
            await db.execute("UPDATE tournaments SET is_default=0")
            await db.execute("UPDATE tournaments SET is_default=1 WHERE id=?", (tid,))
        await db.commit()
    _invalidate_tournaments_cache()


async def get_tournament_stats(tid: int):
    """BUG FIX: قبلاً یک کوئریِ دومِ کاملاً بی‌مصرف اینجا بود — نتیجه‌ش
    (تعداد بازیکنانِ شرکت‌کننده) نه خونده می‌شد نه توی dict خروجی می‌رفت
    (`async with ... as cur2: pass`)؛ یعنی هم یک رفت‌وبرگشتِ اضافه‌ی
    شبکه‌ای به Turso برای هیچ، هم یک آمار که ظاهراً قرار بوده محاسبه بشه
    ولی هیچ‌وقت واقعاً به جایی نمی‌رسید. الان players واقعاً محاسبه و
    برگردونده می‌شه؛ COUNT(DISTINCT x)+COUNT(DISTINCT y) هم اگه یک نفر
    هم سفید هم سیاه بازی کرده باشه (توی مسابقات مختلف) دوبار می‌شمردش،
    برای همین با UNION درست شده."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) as total, SUM(CASE WHEN result IS NOT NULL THEN 1 ELSE 0 END) as done FROM matches WHERE tournament_id=?",
            (tid,)
        ) as cur:
            row = await cur.fetchone()
            total = row[0] or 0
            done = row[1] or 0
        async with db.execute(
            """SELECT COUNT(*) FROM (
                   SELECT white_player_id AS pid FROM matches WHERE tournament_id=?
                   UNION
                   SELECT black_player_id AS pid FROM matches WHERE tournament_id=?
               )""",
            (tid, tid)
        ) as cur2:
            row2 = await cur2.fetchone()
            players = row2[0] or 0
        return {"total": total, "done": done, "players": players}


async def get_tournament_standings(tid: int):
    """جدولِ امتیازاتِ یک تورنومنت رو حساب می‌کنه — برد=۱ امتیاز، مساوی=۰.۵،
    باخت=۰ — و برحسبِ امتیاز (بعد تعدادِ بردها) مرتب می‌کنه. قبلاً همچین
    تحلیلی اصلاً وجود نداشت، فقط لیستِ خامِ مسابقات در دسترس بود."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT m.*, wp.full_name as white_name, bp.full_name as black_name
               FROM matches m
               LEFT JOIN players wp ON m.white_player_id=wp.id
               LEFT JOIN players bp ON m.black_player_id=bp.id
               WHERE m.tournament_id=? ORDER BY m.created_at ASC""",
            (tid,)
        ) as cur:
            rows = await cur.fetchall()

    stats = {}
    total = len(rows)
    done = 0
    for r in rows:
        wname = r["white_name"] or "؟"
        bname = r["black_name"] or "؟"
        for n in (wname, bname):
            stats.setdefault(n, {"played": 0, "win": 0, "draw": 0, "loss": 0, "points": 0.0})
        if r["result"] is None:
            continue
        done += 1
        stats[wname]["played"] += 1
        stats[bname]["played"] += 1
        if r["result"] == "white":
            stats[wname]["win"] += 1
            stats[wname]["points"] += 1
            stats[bname]["loss"] += 1
        elif r["result"] == "black":
            stats[bname]["win"] += 1
            stats[bname]["points"] += 1
            stats[wname]["loss"] += 1
        elif r["result"] == "draw":
            stats[wname]["draw"] += 1
            stats[wname]["points"] += 0.5
            stats[bname]["draw"] += 1
            stats[bname]["points"] += 0.5

    standings = sorted(stats.items(), key=lambda kv: (-kv[1]["points"], -kv[1]["win"]))
    return {"total": total, "done": done, "pending": total - done, "standings": standings}


# ─── Matches ─────────────────────────────────────────────────
async def create_match(white_id, black_id, match_date, tournament_id, created_by) -> int:
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO matches(white_player_id,black_player_id,match_date,tournament_id,created_by,created_at) VALUES (?,?,?,?,?,?)",
            (white_id, black_id, match_date, tournament_id, created_by, now)
        )
        await db.commit()
        _invalidate_matches_cache()
        return cur.lastrowid


async def get_match(mid: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT m.*,
               wp.full_name as white_name, bp.full_name as black_name,
               wc.name as white_class, bc.name as black_class
               FROM matches m
               LEFT JOIN players wp ON m.white_player_id=wp.id
               LEFT JOIN players bp ON m.black_player_id=bp.id
               LEFT JOIN classes wc ON wp.class_id=wc.id
               LEFT JOIN classes bc ON bp.class_id=bc.id
               WHERE m.id=?""",
            (mid,)
        ) as cur:
            return await cur.fetchone()


_PENDING_REQUESTS_SQL = "SELECT * FROM access_requests WHERE status='pending' ORDER BY requested_at DESC"
_PENDING_MATCHES_SQL = """SELECT m.*,
    wp.full_name as white_name, bp.full_name as black_name,
    COALESCE(a.display_name, a.full_name) as claimed_by_name
    FROM matches m
    LEFT JOIN players wp ON m.white_player_id=wp.id
    LEFT JOIN players bp ON m.black_player_id=bp.id
    LEFT JOIN admins a ON m.claimed_by=a.telegram_id
    WHERE m.result IS NULL ORDER BY m.created_at DESC"""
_ALL_TASKS_SQL = "SELECT * FROM tasks ORDER BY assigned_at DESC"
_ACTIVE_ADMINS_SQL = "SELECT * FROM admins WHERE is_active=1"


def _collect_missing_settings(keys_with_defaults: dict):
    """کلیدهایی که هنوز در کش نیستن رو برمی‌گردونه، به‌همراه مقدارهای
    از-قبل-کش‌شده. (کمکی برای بندل‌های زیر — تا هرچی «الان» در کش هست
    اصلاً وارد کوئری نشه.)"""
    cached = {}
    missing = []
    for k in keys_with_defaults:
        v = _cache_get(_setting_cache, k)
        if v is not _CACHE_MISS:
            cached[k] = v
        else:
            missing.append(k)
    return cached, missing


async def get_pishva_panel_bundle():
    """همه‌ی چیزهای لازم برای پنلِ خوش‌آمدگوییِ پیشوا. سه موردِ اول
    (درخواست‌ها/مسابقات/وظایف) همیشه تازه‌ان (عمداً کش نمی‌شن). بقیه
    (نمایش‌نام، وضعیتِ سیستم، ساعتِ کاری، وضعیتِ دیتابیس، AI، لیستِ
    ادمین‌های فعال) اگه در کش باشن از کش میان، وگرنه — نه یکی‌یکی، بلکه
    با همون یک رفت‌وبرگشتِ شبکه‌ی بالا — گرفته و کش می‌شن. نتیجه: حتی درست
    بعدِ منقضی‌شدنِ کش (مثلاً بعد از ۱ دقیقه بی‌کاری)، کلِ پنل با **یک**
    رفت‌وبرگشتِ شبکه (نه ۵-۶ تای جدا) آماده می‌شه."""
    defaults = {
        "pishva_display_name": "مدیر ارشد",
        "system_status": "normal",
        "working_hours_active": "0",
        "db_manual_status": "1",
        "ai_online": "1",
    }
    settings, missing_keys = _collect_missing_settings(defaults)
    need_admins = _cache_get(_admin_list_cache, "active") is _CACHE_MISS

    stmts = [
        (_PENDING_REQUESTS_SQL, []),
        (_PENDING_MATCHES_SQL, []),
        (_ALL_TASKS_SQL, []),
    ]
    if missing_keys:
        placeholders = ",".join("?" for _ in missing_keys)
        stmts.append((f"SELECT key, value FROM system_settings WHERE key IN ({placeholders})", missing_keys))
    if need_admins:
        stmts.append((_ACTIVE_ADMINS_SQL, []))

    cursors = await aiosqlite.execute_pipeline(stmts)
    reqs = await cursors[0].fetchall()
    matches = await cursors[1].fetchall()
    tasks = await cursors[2].fetchall()
    i = 3
    if missing_keys:
        rows = await cursors[i].fetchall()
        i += 1
        found = {row["key"]: row["value"] for row in rows}
        for k in missing_keys:
            value = found.get(k, defaults[k])
            _cache_set(_setting_cache, k, value)
            settings[k] = value
    if need_admins:
        admins = await cursors[i].fetchall()
        _cache_set(_admin_list_cache, "active", admins)
    else:
        admins = _cache_get(_admin_list_cache, "active")

    return {
        "pending_requests": reqs,
        "pending_matches": matches,
        "all_tasks": tasks,
        "admins": admins,
        "pname": settings["pishva_display_name"],
        "status": settings["system_status"],
        "wh": settings["working_hours_active"],
        "db_stat": settings["db_manual_status"],
        "ai_on": settings["ai_online"],
    }


async def get_admin_panel_bundle(admin_id: int):
    """همون ایده‌ی get_pishva_panel_bundle برای پنلِ ادمین: pending_matches +
    tasks_for(admin_id) همیشه تازه‌ان؛ لیستِ بازیکنان و تنظیمات اگه کش
    نباشن با همون یک رفت‌وبرگشت گرفته می‌شن."""
    defaults = {
        "system_status": "normal",
        "working_hours_active": "0",
        "ai_online": "1",
    }
    settings, missing_keys = _collect_missing_settings(defaults)
    need_players = _cache_get(_players_cache, "all") is _CACHE_MISS

    stmts = [
        (_PENDING_MATCHES_SQL, []),
        ("SELECT * FROM tasks WHERE assigned_to=? ORDER BY assigned_at DESC", [admin_id]),
    ]
    if missing_keys:
        placeholders = ",".join("?" for _ in missing_keys)
        stmts.append((f"SELECT key, value FROM system_settings WHERE key IN ({placeholders})", missing_keys))
    if need_players:
        stmts.append((
            "SELECT p.*, c.name as class_name FROM players p LEFT JOIN classes c ON p.class_id=c.id ORDER BY p.full_name",
            [],
        ))

    cursors = await aiosqlite.execute_pipeline(stmts)
    matches = await cursors[0].fetchall()
    tasks = await cursors[1].fetchall()
    i = 2
    if missing_keys:
        rows = await cursors[i].fetchall()
        i += 1
        found = {row["key"]: row["value"] for row in rows}
        for k in missing_keys:
            value = found.get(k, defaults[k])
            _cache_set(_setting_cache, k, value)
            settings[k] = value
    if need_players:
        all_players = await cursors[i].fetchall()
        _cache_set(_players_cache, "all", all_players, ttl=_LIST_CACHE_TTL)
    else:
        all_players = _cache_get(_players_cache, "all")

    return {
        "pending_matches": matches,
        "tasks": tasks,
        "all_players": all_players,
        "status": settings["system_status"],
        "wh": settings["working_hours_active"],
        "ai_on": settings["ai_online"],
    }


async def get_fresh_pishva_panel_data():
    """FIX (کندیِ /start): pending_requests + pending_matches + all_tasks عمداً
    کش نمی‌شن (باید همیشه تازه باشن، وگرنه مثلاً دو ادمین می‌تونن هم‌زمان
    سراغِ یک مسابقه‌ی claim‌شده برن). این تابع هر سه رو با یک درخواستِ
    شبکه‌ی واحد می‌گیره. (نگاه کن: get_pishva_panel_bundle برای نسخه‌ی
    کامل‌تر که تنظیمات/لیستِ‌ادمین‌های کش‌سرد رو هم توی همون یک رفت‌وبرگشت
    می‌گنجونه.)"""
    reqs_cur, matches_cur, tasks_cur = await aiosqlite.execute_pipeline([
        (_PENDING_REQUESTS_SQL, []),
        (_PENDING_MATCHES_SQL, []),
        (_ALL_TASKS_SQL, []),
    ])
    return await reqs_cur.fetchall(), await matches_cur.fetchall(), await tasks_cur.fetchall()


async def get_fresh_admin_panel_data(admin_id: int):
    """همون FIX بالا، برای پنلِ ادمین: pending_matches + tasks_for(admin_id)
    با یک رفت‌وبرگشتِ شبکه‌ی واحد به‌جای دوتای جدا."""
    matches_cur, tasks_cur = await aiosqlite.execute_pipeline([
        (_PENDING_MATCHES_SQL, []),
        ("SELECT * FROM tasks WHERE assigned_to=? ORDER BY assigned_at DESC", [admin_id]),
    ])
    return await matches_cur.fetchall(), await tasks_cur.fetchall()


async def get_pending_matches():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT m.*,
               wp.full_name as white_name, bp.full_name as black_name,
               COALESCE(a.display_name, a.full_name) as claimed_by_name
               FROM matches m
               LEFT JOIN players wp ON m.white_player_id=wp.id
               LEFT JOIN players bp ON m.black_player_id=bp.id
               LEFT JOIN admins a ON m.claimed_by=a.telegram_id
               WHERE m.result IS NULL ORDER BY m.created_at DESC"""
        ) as cur:
            return await cur.fetchall()


async def claim_match(mid: int, admin_id: int):
    """
    فقط برای نمایش — می‌گه کدوم ادمین داره روی این مسابقه کار می‌کنه، تا
    بقیه‌ی ادمین‌ها تو لیست ببینن و همزمان سراغش نرن. جلوی هیچ‌کس رو
    نمی‌گیره (soft marker)، فقط اطلاع‌رسانیه.
    """
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE matches SET claimed_by=?, claimed_at=? WHERE id=?",
            (admin_id, now, mid)
        )
        await db.commit()
    _invalidate_matches_cache()


async def set_match_result(mid: int, result: str, draw_reason: str, updated_by: int):
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE matches SET result=?,draw_reason=?,updated_by=?,updated_at=? WHERE id=?",
            (result, draw_reason, updated_by, now, mid)
        )
        await db.commit()
    _invalidate_matches_cache()


async def record_match_result(mid: int, result: str, reason: str, updated_by: int):
    """
    ثبت نتیجه‌ی مسابقه + آپدیت آمار بازیکن‌ها، با دو تا محافظ:

    1) idempotency guard: اگه مسابقه از قبل نتیجه داشته باشه (مثلاً به‌خاطر
       دوبار تپ کردن ادمین)، هیچ نوشتنی انجام نمی‌ده و False برمی‌گردونه.
    2) اگه وسط کار (بین قدم‌ها) خطا بخوریم، دقیقاً می‌فهمیم کدوم قدم شکست
       خورده (تو لاگ ثبت می‌شه) و exception دوباره raise می‌شه تا لایه‌ی
       بالاتر (matches.py) بتونه به مدیر ارشد هشدار بده که این مسابقه ممکنه
       دیتای ناقص داشته باشه و نیاز به بررسی دستی داره.

    توجه: چون هر دستور به Turso جداگانه commit می‌شه، این یه rollback
    واقعی نیست - فقط جلوی نوشتن دوباره رو می‌گیره و خرابی‌های واقعی رو
    به‌جای سکوت، بلند اعلام می‌کنه.
    """
    m = await get_match(mid)
    if m is None:
        raise ValueError(f"مسابقه {mid} پیدا نشد")
    if m["result"] is not None:
        return False  # قبلاً ثبت شده - از دوبار شمردن جلوگیری می‌کنیم

    stat_map = {
        "white": ("win", "loss"),
        "black": ("loss", "win"),
        "draw": ("draw", "draw"),
    }
    if result not in stat_map:
        raise ValueError(f"نتیجه‌ی نامعتبر: {result}")
    white_stat, black_stat = stat_map[result]

    step = "set_match_result"
    try:
        await set_match_result(mid, result, reason, updated_by)
        step = "update_white_stats"
        await update_player_stats(m["white_player_id"], white_stat)
        step = "update_black_stats"
        await update_player_stats(m["black_player_id"], black_stat)
    except Exception as e:
        logger.error(
            f"⚠️ ثبت نتیجه مسابقه {mid} در مرحله '{step}' شکست خورد: {e} — "
            f"داده ممکنه ناقص مونده باشه، نیاز به بررسی دستیه."
        )
        raise

    return True


async def get_matches_by_filter(period: str = "all"):
    """BUG FIX (امنیت): قبلاً تاریخ مستقیم با f-string توی متنِ SQL جاگذاری
    می‌شد (`WHERE m.match_date='{d}'`) — چون d همیشه از datetime خودِ سرور
    ساخته می‌شه، فعلاً قابل‌سوءاستفاده نبود، ولی سبکش برخلافِ همه‌جای بقیه‌ی
    این فایله (که پارامتری‌ان) و اگه یک روز این تابع پارامتر گرفت، دقیقاً
    همین الگو راهِ SQL injection می‌شه. الان مثل بقیه‌ی توابع، پارامتری شده."""
    cached = _cache_get(_matches_cache, period)
    if cached is not _CACHE_MISS:
        return cached
    from datetime import timedelta
    now = datetime.now()
    where = ""
    params = []
    if period == "today":
        where = "WHERE m.match_date=?"
        params.append(now.strftime("%Y-%m-%d"))
    elif period == "week":
        where = "WHERE m.created_at>=?"
        params.append((now - timedelta(days=7)).isoformat())
    elif period == "month":
        where = "WHERE m.created_at>=?"
        params.append((now - timedelta(days=30)).isoformat())
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            f"""SELECT m.*, wp.full_name as white_name, bp.full_name as black_name
               FROM matches m
               LEFT JOIN players wp ON m.white_player_id=wp.id
               LEFT JOIN players bp ON m.black_player_id=bp.id
               {where} ORDER BY m.created_at DESC LIMIT 50""",
            params
        ) as cur:
            rows = await cur.fetchall()
            _cache_set(_matches_cache, period, rows, ttl=_LIST_CACHE_TTL)
            return rows


async def search_matches(query: str):
    like = f"%{query}%"
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT m.*, wp.full_name as white_name, bp.full_name as black_name
               FROM matches m
               LEFT JOIN players wp ON m.white_player_id=wp.id
               LEFT JOIN players bp ON m.black_player_id=bp.id
               WHERE wp.full_name LIKE ? OR bp.full_name LIKE ? OR m.match_date LIKE ?
               ORDER BY m.created_at DESC LIMIT 30""",
            (like, like, like)
        ) as cur:
            return await cur.fetchall()


async def delete_match(mid: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM matches WHERE id=?", (mid,))
        await db.commit()
    _invalidate_matches_cache()


async def update_match(mid: int, **kwargs):
    if not kwargs:
        return
    sets = ", ".join(f"{k}=?" for k in kwargs)
    vals = list(kwargs.values()) + [mid]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE matches SET {sets} WHERE id=?", vals)
        await db.commit()
    _invalidate_matches_cache()


async def reverse_player_stats(player_id: int, result: str):
    """معکوس‌کردن اثر یک نتیجه‌ی قبلی روی آمار بازیکن (برای ویرایش/حذف مسابقه). زیر صفر نمی‌ره."""
    col = {"win": "wins", "loss": "losses", "draw": "draws"}.get(result)
    if col:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(f"UPDATE players SET {col}=MAX(0,{col}-1) WHERE id=?", (player_id,))
            await db.commit()
        _invalidate_players_cache()


async def correct_match_result(mid: int, new_result: str, reason: str, updated_by: int):
    """
    ویرایش نتیجه‌ی یک مسابقه‌ی از قبل ثبت‌شده: اگه قبلاً نتیجه داشته،
    اول اثرش رو از آمار دو بازیکن برمی‌داره، بعد نتیجه‌ی جدید رو ثبت و آمار رو
    دوباره اعمال می‌کنه. اگه مسابقه پیدا نشه، None برمی‌گردونه.
    """
    m = await get_match(mid)
    if m is None:
        return None
    stat_map = {"white": ("win", "loss"), "black": ("loss", "win"), "draw": ("draw", "draw")}
    if new_result not in stat_map:
        raise ValueError(f"نتیجه‌ی نامعتبر: {new_result}")

    if m["result"] in stat_map:
        old_white_stat, old_black_stat = stat_map[m["result"]]
        await reverse_player_stats(m["white_player_id"], old_white_stat)
        await reverse_player_stats(m["black_player_id"], old_black_stat)

    white_stat, black_stat = stat_map[new_result]
    await set_match_result(mid, new_result, reason, updated_by)
    await update_player_stats(m["white_player_id"], white_stat)
    await update_player_stats(m["black_player_id"], black_stat)
    return m


async def delete_match_safely(mid: int):
    """
    حذف یک مسابقه: اگه از قبل نتیجه داشته، اول اثرش رو از آمار بازیکن‌ها
    برمی‌داره تا برد/باخت/مساوی‌ها بعد از حذف درست بمونن. اگه پیدا نشه None.
    """
    m = await get_match(mid)
    if m is None:
        return None
    stat_map = {"white": ("win", "loss"), "black": ("loss", "win"), "draw": ("draw", "draw")}
    if m["result"] in stat_map:
        white_stat, black_stat = stat_map[m["result"]]
        await reverse_player_stats(m["white_player_id"], white_stat)
        await reverse_player_stats(m["black_player_id"], black_stat)
    await delete_match(mid)
    return m


async def get_player_match_history(player_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT m.*, wp.full_name as white_name, bp.full_name as black_name
               FROM matches m
               LEFT JOIN players wp ON m.white_player_id=wp.id
               LEFT JOIN players bp ON m.black_player_id=bp.id
               WHERE m.white_player_id=? OR m.black_player_id=?
               ORDER BY m.created_at DESC""",
            (player_id, player_id)
        ) as cur:
            return await cur.fetchall()


async def have_played_before(p1: int, p2: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id FROM matches WHERE (white_player_id=? AND black_player_id=?) OR (white_player_id=? AND black_player_id=?)",
            (p1, p2, p2, p1)
        ) as cur:
            return (await cur.fetchone()) is not None


# ─── Messages ─────────────────────────────────────────────────
async def send_message_db(sender_id, receiver_id, text, msg_type="direct"):
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO messages(sender_id,receiver_id,text,sent_at,msg_type) VALUES (?,?,?,?,?)",
            (sender_id, receiver_id, text, now, msg_type)
        )
        await db.commit()


async def get_messages_for(receiver_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM messages WHERE receiver_id=? ORDER BY sent_at DESC",
            (receiver_id,)
        ) as cur:
            return await cur.fetchall()


async def get_all_messages():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM messages ORDER BY sent_at DESC") as cur:
            return await cur.fetchall()


async def mark_message_read(msg_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE messages SET is_read=1 WHERE id=?", (msg_id,))
        await db.commit()


# ─── Announcements ────────────────────────────────────────────
async def create_announcement(text: str, file_id="", file_type=""):
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO announcements(text,file_id,file_type,sent_at) VALUES (?,?,?,?)",
            (text, file_id, file_type, now)
        )
        await db.commit()
        return cur.lastrowid


async def get_all_announcements():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM announcements ORDER BY sent_at DESC") as cur:
            return await cur.fetchall()


async def delete_announcement(ann_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM announcements WHERE id=?", (ann_id,))
        await db.commit()


# ─── News ─────────────────────────────────────────────────────
async def create_news(text: str):
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO news(text,sent_at) VALUES (?,?)", (text, now))
        await db.commit()


async def get_all_news():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM news ORDER BY sent_at DESC") as cur:
            return await cur.fetchall()


# ─── Tasks ────────────────────────────────────────────────────
async def create_task(assigned_to, assigned_by, title, desc) -> int:
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO tasks(assigned_to,assigned_by,title,description,assigned_at) VALUES (?,?,?,?,?)",
            (assigned_to, assigned_by, title, desc, now)
        )
        await db.commit()
        return cur.lastrowid


async def get_tasks_for(admin_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM tasks WHERE assigned_to=? ORDER BY assigned_at DESC",
            (admin_id,)
        ) as cur:
            return await cur.fetchall()


async def get_all_tasks():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM tasks ORDER BY assigned_at DESC") as cur:
            return await cur.fetchall()


async def update_task_status(task_id: int, status: str, reason: str = ""):
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE tasks SET status=?,fail_reason=?,completed_at=? WHERE id=?",
            (status, reason, now, task_id)
        )
        await db.commit()


async def get_task(task_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)) as cur:
            return await cur.fetchone()


# ─── Feedback ─────────────────────────────────────────────────
async def create_feedback(sender_id, fb_type, title, content):
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO feedback(sender_id,fb_type,title,content,sent_at) VALUES (?,?,?,?,?)",
            (sender_id, fb_type, title, content, now)
        )
        await db.commit()


async def get_all_feedback():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM feedback ORDER BY sent_at DESC") as cur:
            return await cur.fetchall()


async def reply_feedback(fb_id: int, reply: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE feedback SET reply=? WHERE id=?", (reply, fb_id))
        await db.commit()


# ─── Action Logs ─────────────────────────────────────────────
async def log_action(admin_id, action_type, description, target_id=None, snapshot=None):
    """لاگِ اقدامات صرفاً برای تاریخچه/گزارش‌گیریه — هیچ کدی نتیجه‌ی این
    نوشتن رو نمی‌خونه، پس دلیلی نداره کاربر رو معطلِ ثبتش کنیم. با ۶۶ جای
    صدا زده‌شدن توی کل پروژه (روی تقریباً هر اقدامِ واقعیِ ادمین)، awaited
    بودنش قبلاً یعنی یک رفت‌وبرگشتِ اضافه‌ی شبکه‌ای درست وسطِ هر اقدام،
    درست قبل از این‌که کاربر پیامِ تاییدیه رو ببینه.

    snapshot (اختیاری): برای اقدام‌هایی که واقعاً ردیف رو از دیتابیس پاک
    می‌کنن (نه فقط status رو عوض می‌کنن)، یه JSON از حالتِ قبل از حذف؛
    تا دکمه‌ی «خنثی‌سازی» بعداً بتونه دقیقاً همون رکورد رو برگردونه."""
    now = datetime.now().isoformat()

    async def _write():
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO action_logs(admin_id,action_type,description,target_id,logged_at,snapshot) "
                "VALUES (?,?,?,?,?,?)",
                (admin_id, action_type, description, target_id, now, snapshot)
            )
            await db.commit()

    _fire_and_forget(_write())


async def get_action_logs(period="all", admin_id=None, page=0, page_size=10):
    """لاگِ اقدامات رو صفحه‌بندی‌شده برمی‌گردونه: (ردیف‌ها, تعداد کل).
    page از ۰ شروع می‌شه؛ حتی اگه تعداد کل نتایج خیلی زیاد باشه (مثلاً
    ده‌ها هزار ردیف)، فقط همون صفحه‌ی درخواستی از دیتابیس خونده می‌شه.

    FIX: چون دیتابیس روی Turso (اتصال شبکه‌ای) است، هر db.execute یعنی یک
    رفت‌وبرگشتِ کاملِ HTTP. کوئریِ COUNT(*) و کوئریِ SELECT صفحه‌ی فعلی به‌هم
    وابسته نیستن، پس قبلاً پشتِ‌سرِهم اجرا می‌شدن، حالا هم‌زمان (asyncio.gather)."""
    from datetime import timedelta
    now = datetime.now()
    conditions = []
    params = []
    if period == "today":
        d = now.strftime("%Y-%m-%d")
        conditions.append("logged_at LIKE ?")
        params.append(f"{d}%")
    elif period == "week":
        d = (now - timedelta(days=7)).isoformat()
        conditions.append("logged_at >= ?")
        params.append(d)
    elif period == "month":
        d = (now - timedelta(days=30)).isoformat()
        conditions.append("logged_at >= ?")
        params.append(d)
    if admin_id:
        conditions.append("admin_id = ?")
        params.append(admin_id)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    offset = max(page, 0) * page_size
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        count_cur, rows_cur = await asyncio.gather(
            db.execute(f"SELECT COUNT(*) AS c FROM action_logs {where}", params),
            db.execute(
                f"SELECT * FROM action_logs {where} ORDER BY logged_at DESC LIMIT ? OFFSET ?",
                params + [page_size, offset]
            ),
        )
        count_row = await count_cur.fetchone()
        total = count_row["c"] if count_row else 0
        rows = await rows_cur.fetchall()
        return rows, total


async def search_action_logs(term: str = "", hour_from=None, hour_to=None, admin_id=None, page=0, page_size=10):
    """جستجو در لاگ اقدامات: term توی توضیحات/نوع اقدام/تاریخ-ساعت خام و
    همچنین نام/یوزرنیم مدیرِ ثبت‌کننده جستجو می‌شه. hour_from/hour_to
    (هر دو ۰ تا ۲۳) یه فیلترِ بازه‌ی ساعتِ رخداد رو اضافه می‌کنه — با
    پشتیبانی از بازه‌ی پیچشی (مثلاً ۲۲ تا ۳ بامداد). admin_id اگه داده
    بشه، جستجو فقط توی اقدامات همون مدیرِ مشخص انجام می‌شه (مثلاً از
    صفحه‌ی پروفایل یه مدیر خاص).
    برمی‌گردونه: (ردیف‌ها, تعداد کل)."""
    term = (term or "").strip()
    conditions = []
    params = []

    if term:
        like = f"%{term}%"
        admin_ids = []
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT telegram_id FROM admins WHERE display_name LIKE ? OR full_name LIKE ? OR username LIKE ?",
                (like, like, like)
            ) as cur:
                admin_ids = [r["telegram_id"] for r in await cur.fetchall()]

        sub = ["description LIKE ?", "action_type LIKE ?", "logged_at LIKE ?"]
        sub_params = [like, like, like]
        if admin_ids:
            placeholders = ",".join("?" * len(admin_ids))
            sub.append(f"admin_id IN ({placeholders})")
            sub_params.extend(admin_ids)
        conditions.append("(" + " OR ".join(sub) + ")")
        params.extend(sub_params)

    if hour_from is not None and hour_to is not None:
        if hour_from <= hour_to:
            conditions.append("CAST(substr(logged_at,12,2) AS INTEGER) BETWEEN ? AND ?")
            params.extend([hour_from, hour_to])
        else:
            conditions.append(
                "(CAST(substr(logged_at,12,2) AS INTEGER) >= ? OR CAST(substr(logged_at,12,2) AS INTEGER) <= ?)"
            )
            params.extend([hour_from, hour_to])

    if admin_id:
        conditions.append("admin_id = ?")
        params.append(admin_id)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    offset = max(page, 0) * page_size
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        # FIX: مثل get_action_logs — COUNT و SELECT صفحه به‌هم وابسته نیستن،
        # پس هم‌زمان اجرا می‌شن (این یکی، برخلاف بالا، نمی‌شد از قبل موازی
        # کرد چون هنوز باید بعد از کوئریِ admin_ids بالاتر منتظر می‌موند).
        count_cur, rows_cur = await asyncio.gather(
            db.execute(f"SELECT COUNT(*) AS c FROM action_logs {where}", params),
            db.execute(
                f"SELECT * FROM action_logs {where} ORDER BY logged_at DESC LIMIT ? OFFSET ?",
                params + [page_size, offset]
            ),
        )
        count_row = await count_cur.fetchone()
        total = count_row["c"] if count_row else 0
        rows = await rows_cur.fetchall()
        return rows, total


# ─── هشدار حذف مشکوک: خنثی‌سازیِ اقدام‌های یک ادمین در یک روز مشخص ───
# نوع اقدام‌هایی که می‌دونیم چطور برمی‌گردن. برای اونایی که فقط status
# رو عوض کردن (اخراج/تعلیق/حذف از مسابقه/حذف تیم/حذف تورنمنت)، برگردوندن
# status به «active» کافیه. برای حذف مسابقه که واقعاً ردیف رو پاک می‌کنه،
# از snapshot ثبت‌شده‌ی وقتِ حذف استفاده می‌کنیم.
UNDOABLE_ACTIONS = {
    "kick_player", "eliminate_player", "suspend_player",
    "delete_team", "delete_tournament", "kick_admin", "delete_match",
}


async def get_admin_actions_on_date(admin_id: int, date_str: str):
    """همه‌ی ردیف‌های action_logs یک ادمین توی یک روز میلادی مشخص
    (فرمت 'YYYY-MM-DD') — به ترتیب وقوع (قدیمی‌ترین اول)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM action_logs WHERE admin_id=? AND logged_at LIKE ? ORDER BY id ASC",
            (admin_id, f"{date_str}%")
        ) as cur:
            return await cur.fetchall()


async def mark_action_undone(log_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE action_logs SET undone=1 WHERE id=?", (log_id,))
        await db.commit()


async def reinsert_match(row: dict):
    """برگردوندنِ یک مسابقه‌ی حذف‌شده، دقیقاً با همون id و همون مقادیر
    (از روی snapshot ثبت‌شده‌ی وقتِ حذف)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT OR IGNORE INTO matches
               (id, white_player_id, black_player_id, result, draw_reason, match_date,
                tournament_id, created_by, created_at, updated_by, updated_at, is_pinned)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (row.get("id"), row.get("white_player_id"), row.get("black_player_id"),
             row.get("result"), row.get("draw_reason"), row.get("match_date"),
             row.get("tournament_id"), row.get("created_by"), row.get("created_at"),
             row.get("updated_by"), row.get("updated_at"), row.get("is_pinned"))
        )
        await db.commit()


async def undo_admin_actions(admin_id: int, date_str: str):
    """تمام اقدام‌های قابل‌برگشتِ یک ادمین در یک روز مشخص رو خنثی می‌کنه.
    برمی‌گردونه: (لیستِ خنثی‌شده‌ها, لیستِ ردشده‌ها) — هر کدوم لیستی از
    ردیف‌های action_logs."""
    rows = await get_admin_actions_on_date(admin_id, date_str)
    reverted, skipped = [], []
    for r in rows:
        if r["undone"] or r["action_type"] not in UNDOABLE_ACTIONS:
            if r["action_type"] not in UNDOABLE_ACTIONS:
                skipped.append(r)
            continue
        at = r["action_type"]
        tid = r["target_id"]
        try:
            if at in ("kick_player", "eliminate_player", "suspend_player") and tid:
                await update_player(tid, status="active")
            elif at == "delete_team" and tid:
                await update_team(tid, status="active")
            elif at == "delete_tournament" and tid:
                await update_tournament(tid, status="active")
            elif at == "kick_admin" and tid:
                await revive_admin(tid)
            elif at == "delete_match" and tid and r["snapshot"]:
                await reinsert_match(json.loads(r["snapshot"]))
            else:
                skipped.append(r)
                continue
            await mark_action_undone(r["id"])
            reverted.append(r)
        except Exception:
            logger.exception(f"undo_admin_actions failed for log id={r['id']}")
            skipped.append(r)
    return reverted, skipped


# ─── Access Requests ─────────────────────────────────────────
async def create_access_request(telegram_id, username, full_name, role, message=""):
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO access_requests(telegram_id,username,full_name,role,message,requested_at) VALUES (?,?,?,?,?,?)",
            (telegram_id, username, full_name, role, message, now)
        )
        await db.commit()
        return cur.lastrowid


async def get_pending_requests():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM access_requests WHERE status='pending' ORDER BY requested_at DESC"
        ) as cur:
            return await cur.fetchall()


async def get_access_request(req_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM access_requests WHERE id=?", (req_id,)) as cur:
            return await cur.fetchone()


async def update_access_request(req_id: int, status: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE access_requests SET status=? WHERE id=?", (status, req_id))
        await db.commit()


# ─── Teams ────────────────────────────────────────────────────
import random
import string


async def create_team(name, slogan, requester_name, created_by) -> int:
    now = datetime.now().isoformat()
    code = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO teams(name,slogan,team_code,requester_name,created_by,created_at) VALUES (?,?,?,?,?,?)",
            (name, slogan, code, requester_name, created_by, now)
        )
        await db.commit()
        return cur.lastrowid


async def get_all_teams():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM teams WHERE status='active' ORDER BY name") as cur:
            return await cur.fetchall()


async def get_team(team_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM teams WHERE id=?", (team_id,)) as cur:
            return await cur.fetchone()


async def get_team_members(team_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT tm.*, p.full_name, p.status as player_status, c.name as class_name
               FROM team_members tm
               JOIN players p ON tm.player_id=p.id
               LEFT JOIN classes c ON p.class_id=c.id
               WHERE tm.team_id=?""",
            (team_id,)
        ) as cur:
            return await cur.fetchall()


async def add_team_member(team_id: int, player_id: int, level="", is_reserve=0):
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO team_members(team_id,player_id,level,is_reserve,joined_at) VALUES (?,?,?,?,?)",
            (team_id, player_id, level, is_reserve, now)
        )
        await db.commit()


async def remove_team_member(team_id: int, player_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM team_members WHERE team_id=? AND player_id=?",
            (team_id, player_id)
        )
        await db.commit()


async def update_team(team_id: int, **kwargs):
    if not kwargs:
        return
    sets = ", ".join(f"{k}=?" for k in kwargs)
    vals = list(kwargs.values()) + [team_id]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE teams SET {sets} WHERE id=?", vals)
        await db.commit()


async def delete_team(team_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE teams SET status='deleted' WHERE id=?", (team_id,))
        await db.commit()


async def add_team_warning(team_id: int, reason: str, issued_by: int):
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.batch():
            await db.execute("UPDATE teams SET warnings=warnings+1 WHERE id=?", (team_id,))
            await db.execute(
                "INSERT INTO warnings_log(target_type,target_id,reason,issued_by,issued_at) VALUES (?,?,?,?,?)",
                ("team", team_id, reason, issued_by, now)
            )
        await db.commit()


async def get_team_stats(team_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """SELECT
               SUM(CASE WHEN (team1_id=? AND result='team1') OR (team2_id=? AND result='team2') THEN 1 ELSE 0 END) as wins,
               SUM(CASE WHEN (team1_id=? AND result='team2') OR (team2_id=? AND result='team1') THEN 1 ELSE 0 END) as losses,
               SUM(CASE WHEN result='draw' THEN 1 ELSE 0 END) as draws
               FROM team_matches WHERE team1_id=? OR team2_id=?""",
            (team_id,) * 6
        ) as cur:
            row = await cur.fetchone()
            return {"wins": row[0] or 0, "losses": row[1] or 0, "draws": row[2] or 0}


# ─── Backups ──────────────────────────────────────────────────
async def save_backup_record(label: str, period: str, fmt: str, file_data: str):
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO backups(label,period,format,file_data,created_at) VALUES (?,?,?,?,?)",
            (label, period, fmt, file_data, now)
        )
        await db.commit()


async def get_all_backups():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT id,label,period,format,created_at FROM backups ORDER BY created_at DESC") as cur:
            return await cur.fetchall()


async def get_backup(backup_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM backups WHERE id=?", (backup_id,)) as cur:
            return await cur.fetchone()


# ─── New Year / Reset ─────────────────────────────────────────
async def reset_active_data():
    """Archive and clear all active data"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
        DELETE FROM team_match_boards;
        DELETE FROM team_matches;
        DELETE FROM team_members;
        DELETE FROM matches;
        DELETE FROM warnings_log;
        DELETE FROM teams;
        DELETE FROM players;
        DELETE FROM classes;
        UPDATE tournaments SET status='archived';
        """)
        await db.commit()
    _invalidate_players_cache()
    _invalidate_classes_cache()
    _invalidate_matches_cache()
    _invalidate_tournaments_cache()


# ─── Security: Queue & Block (صف انتظار و بلاک) ────────────────
async def set_request_status(req_id: int, status: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE access_requests SET status=? WHERE id=?", (status, req_id))
        await db.commit()


async def get_queued_requests():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM access_requests WHERE status='queued' ORDER BY requested_at DESC"
        ) as cur:
            return await cur.fetchall()


async def get_queued_request_by_uid(telegram_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM access_requests WHERE telegram_id=? AND status='queued' ORDER BY requested_at DESC LIMIT 1",
            (telegram_id,)
        ) as cur:
            return await cur.fetchone()


async def block_user(telegram_id: int, username: str, full_name: str, reason: str, blocked_by: int):
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO blocked_users(telegram_id,username,full_name,reason,blocked_by,blocked_at) VALUES (?,?,?,?,?,?)",
            (telegram_id, username, full_name, reason, blocked_by, now)
        )
        await db.commit()
    _invalidate_blocked_cache(telegram_id)


async def unblock_user(telegram_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM blocked_users WHERE telegram_id=?", (telegram_id,))
        await db.commit()
    _invalidate_blocked_cache(telegram_id)


async def get_blocked_user(telegram_id: int):
    """این تابع روی *هر تک آپدیت* (هر پیام، هر دکمه، از هر نفر) قبل از
    هر چیز دیگه‌ای در block_gate صدا زده می‌شه — پرتکرارترین کوئریِ کل
    ربات، و تا امروز اصلاً کش نمی‌شد. یعنی هر کلیک، صرف‌نظر از این‌که
    چیکار می‌خواسته بکنه، اول باید منتظرِ یک رفت‌وبرگشتِ کاملِ شبکه‌ای به
    Turso می‌موند فقط برای همین یک چک. چند ثانیه تاخیر در دیدنِ بلاکِ
    تازه قابل‌قبوله (خودِ عملِ بلاک هم فوری invalidate می‌شه)."""
    cached = _cache_get(_blocked_cache, telegram_id)
    if cached is not _CACHE_MISS:
        return cached
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM blocked_users WHERE telegram_id=?", (telegram_id,)) as cur:
            row = await cur.fetchone()
    _cache_set(_blocked_cache, telegram_id, row)
    return row


async def get_all_blocked():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM blocked_users ORDER BY blocked_at DESC") as cur:
            return await cur.fetchall()


async def get_security_snapshot(top_n: int = 5):
    """یه نمای‌کلی از وضعیتِ امنیتی برای تحلیل: صفِ انتظار، بلاک‌شده‌ها، و
    غریبه‌هایی که بیشترین تعداد اقدام رو (بدون تأیید) ثبت کردن — یعنی
    کسایی که مدام دارن سعی می‌کنن، صرف‌نظر از این‌که الان بلاک/صف/آزادن."""
    queued = await get_queued_requests()
    blocked = await get_all_blocked()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT telegram_id,
                      MAX(username) AS username,
                      MAX(full_name) AS full_name,
                      COUNT(*) AS action_count,
                      MIN(ts) AS first_seen,
                      MAX(ts) AS last_active
               FROM stranger_log
               GROUP BY telegram_id
               ORDER BY action_count DESC
               LIMIT ?""",
            (top_n,)
        ) as cur:
            top_strangers = await cur.fetchall()
    blocked_ids = {b["telegram_id"] for b in blocked}
    return {
        "queued": queued,
        "blocked": blocked,
        "top_strangers": [dict(r) | {"is_blocked": r["telegram_id"] in blocked_ids} for r in top_strangers],
    }


# ─── Restore (بازگردانی بکاپ) ──────────────────────────────────
async def get_class_by_name(name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM classes WHERE name=?", (name,)) as cur:
            return await cur.fetchone()


async def get_or_create_class(name: str) -> int:
    """کلاس رو با نام پیدا می‌کنه، اگه نبود می‌سازه و شناسه رو برمی‌گردونه."""
    name = (name or "").strip()
    if not name:
        return None
    row = await get_class_by_name(name)
    if row:
        return row["id"]
    await create_class(name)
    row = await get_class_by_name(name)
    return row["id"] if row else None


async def get_player_by_name(full_name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM players WHERE lower(trim(full_name))=lower(trim(?))", (full_name,)
        ) as cur:
            return await cur.fetchone()


async def restore_upsert_player(full_name: str, class_id=None, status=None, warnings=0,
                                 is_elite=0, is_special=0, wins=0, losses=0, draws=0,
                                 created_at=None) -> tuple:
    """بازیکن رو از روی نام کامل پیدا یا ایجاد می‌کنه و اطلاعات بکاپ رو روش اعمال می‌کنه.
    خروجی: (player_id, created: bool)"""
    full_name = (full_name or "").strip()
    if not full_name:
        return None, False
    existing = await get_player_by_name(full_name)
    now = created_at or datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        if existing:
            await db.execute(
                """UPDATE players SET class_id=COALESCE(?, class_id), status=COALESCE(?, status),
                   warnings=?, is_elite=?, is_special=?, wins=?, losses=?, draws=? WHERE id=?""",
                (class_id, status, warnings, is_elite, is_special, wins, losses, draws, existing["id"])
            )
            await db.commit()
            _invalidate_players_cache()
            return existing["id"], False
        else:
            cur = await db.execute(
                """INSERT INTO players(full_name,class_id,status,warnings,is_elite,is_special,
                   wins,losses,draws,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (full_name, class_id, status or "active", warnings, is_elite, is_special,
                 wins, losses, draws, now)
            )
            await db.commit()
            _invalidate_players_cache()
            return cur.lastrowid, True


async def get_tournament_by_name(name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM tournaments WHERE name=?", (name,)) as cur:
            return await cur.fetchone()


async def get_or_create_tournament(name: str, status: str = "active", is_default: bool = False) -> tuple:
    """خروجی: (tournament_id, created: bool)"""
    name = (name or "").strip()
    if not name:
        return None, False
    existing = await get_tournament_by_name(name)
    if existing:
        if status:
            await update_tournament(existing["id"], status=status)
        if is_default:
            await set_default_tournament(existing["id"])
        return existing["id"], False
    tid = await create_tournament(name)
    if status and status != "active":
        await update_tournament(tid, status=status)
    if is_default:
        await set_default_tournament(tid)
    return tid, True


async def insert_match_raw(white_id, black_id, result, draw_reason, match_date,
                            tournament_id, created_by, created_at) -> int:
    """درج مستقیم مسابقه با حفظ زمان اصلی (برای بازگردانی بکاپ)."""
    now = created_at or datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """INSERT INTO matches(white_player_id,black_player_id,result,draw_reason,
               match_date,tournament_id,created_by,created_at) VALUES (?,?,?,?,?,?,?,?)""",
            (white_id, black_id, result, draw_reason, match_date, tournament_id, created_by, now)
        )
        await db.commit()
        _invalidate_matches_cache()
        return cur.lastrowid


# ─── AI Assistant — Chat Sessions & Messages ───────────────────
async def ai_create_session(user_id: int, role: str) -> int:
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO ai_chat_sessions(user_id,role,title,started_at,last_message_at) VALUES (?,?,?,?,?)",
            (user_id, role, "", now, now)
        )
        await db.commit()
        return cur.lastrowid


async def ai_add_message(session_id: int, sender: str, text: str):
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.batch():
            await db.execute(
                "INSERT INTO ai_chat_messages(session_id,sender,text,sent_at) VALUES (?,?,?,?)",
                (session_id, sender, text, now)
            )
            await db.execute("UPDATE ai_chat_sessions SET last_message_at=? WHERE id=?", (now, session_id))
        await db.commit()


async def ai_set_session_title(session_id: int, title: str):
    title = (title or "").strip()[:60]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE ai_chat_sessions SET title=? WHERE id=?", (title, session_id))
        await db.commit()


async def ai_get_session(session_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM ai_chat_sessions WHERE id=?", (session_id,)) as cur:
            return await cur.fetchone()


async def ai_get_sessions_for_user(user_id: int, limit: int = 20):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM ai_chat_sessions WHERE user_id=? ORDER BY last_message_at DESC LIMIT ?",
            (user_id, limit)
        ) as cur:
            return await cur.fetchall()


async def ai_get_sessions_filtered(user_id: int = None, period: str = "all", limit: int = 50):
    """برای پنل مدیر ارشد: سوابق چت یک ادمین خاص در یک بازه‌ی زمانی."""
    # BUG FIX (امنیت): قبلاً user_id/تاریخ‌ها/limit مستقیم با f-string توی
    # متنِ SQL جاگذاری می‌شدن؛ int()-کست‌کردنِ user_id و limit فعلاً جلوی
    # inject واقعی رو می‌گرفت، ولی الگوش خطرناکه. الان همه‌چیز پارامتریه.
    from datetime import timedelta
    now = datetime.now()
    conditions = []
    params = []
    if user_id is not None:
        conditions.append("user_id = ?")
        params.append(int(user_id))
    if period == "today":
        conditions.append("started_at LIKE ?")
        params.append(now.strftime("%Y-%m-%d") + "%")
    elif period == "week":
        conditions.append("started_at >= ?")
        params.append((now - timedelta(days=7)).isoformat())
    elif period == "month":
        conditions.append("started_at >= ?")
        params.append((now - timedelta(days=30)).isoformat())
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    params.append(int(limit))
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            f"SELECT * FROM ai_chat_sessions {where} ORDER BY started_at DESC LIMIT ?", params
        ) as cur:
            return await cur.fetchall()


async def ai_get_messages(session_id: int, limit: int = 200):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM ai_chat_messages WHERE session_id=? ORDER BY sent_at ASC LIMIT ?",
            (session_id, limit)
        ) as cur:
            return await cur.fetchall()


# ─── Chess mini-app ─────────────────────────────────────────────
async def create_chess_request(requester_id: int, target_id: int, time_control: int = 300, requester_color: str = "random"):
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO chess_requests(requester_id,target_id,status,time_control,requester_color,created_at) VALUES (?,?,?,?,?,?)",
            (requester_id, target_id, "pending", time_control, requester_color, now)
        )
        await db.commit()
        return cur.lastrowid


async def get_chess_request(req_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM chess_requests WHERE id=?", (req_id,)) as cur:
            return await cur.fetchone()


async def set_chess_request_status(req_id: int, status: str):
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE chess_requests SET status=?, responded_at=? WHERE id=?",
            (status, now, req_id)
        )
        await db.commit()


async def has_pending_chess_request(requester_id: int, target_id: int) -> bool:
    """
    باگ قبلی: اگر طرف مقابل هیچ‌وقت به یک درخواست پاسخ نمی‌داد (نه قبول نه رد)،
    آن ردیف برای همیشه status='pending' می‌ماند و کاربر تا ابد نمی‌توانست درخواست
    جدیدی بفرستد؛ پیام «درخواست قبلی هنوز در انتظار پاسخ است» نشان داده می‌شد
    درحالی‌که از نظر کاربر اصلاً بازی/درخواستی در جریان نبود.
    الان درخواست‌های خیلی قدیمی (بیشتر از CHESS_REQUEST_EXPIRY_MINUTES دقیقه)
    به‌صورت خودکار منقضی می‌شوند و دیگر مانع ارسال درخواست تازه نیستند.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, created_at FROM chess_requests WHERE requester_id=? AND target_id=? AND status='pending'",
            (requester_id, target_id)
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            return False

        cutoff = (datetime.now() - timedelta(minutes=CHESS_REQUEST_EXPIRY_MINUTES)).isoformat()
        created_at = row["created_at"]
        if created_at and created_at < cutoff:
            now = datetime.now().isoformat()
            await db.execute(
                "UPDATE chess_requests SET status='expired', responded_at=? WHERE id=?",
                (now, row["id"])
            )
            await db.commit()
            return False
        return True


async def expire_other_chess_requests(user_a: int, user_b: int, exclude_req_id: int):
    """وقتی بین دو نفر بازی‌ای ساخته می‌شود (یا دیگر لازم نیست)، هر درخواست
    pending دیگری بین همین دو نفر (در هر دو جهت) را منقضی می‌کند تا برای
    همیشه به‌صورت یتیم روی «در انتظار پاسخ» باقی نماند."""
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """UPDATE chess_requests SET status='expired', responded_at=?
               WHERE status='pending' AND id!=?
                 AND ((requester_id=? AND target_id=?) OR (requester_id=? AND target_id=?))""",
            (now, exclude_req_id, user_a, user_b, user_b, user_a)
        )
        await db.commit()


async def create_chess_game(token, white_id, black_id, white_name, black_name, fen, time_control=300, ai_level=None):
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """INSERT INTO chess_games
               (token, white_id, black_id, white_name, black_name, fen, status,
                white_time, black_time, created_at, last_move_at, ai_level)
               VALUES (?,?,?,?,?,?,'active',?,?,?,?,?)""",
            (token, white_id, black_id, white_name, black_name, fen, time_control, time_control, now, now, ai_level)
        )
        await db.commit()
        return cur.lastrowid


async def get_chess_game(token: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM chess_games WHERE token=?", (token,)) as cur:
            return await cur.fetchone()


async def get_active_chess_game_for(telegram_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM chess_games WHERE (white_id=? OR black_id=?) AND status='active' ORDER BY id DESC LIMIT 1",
            (telegram_id, telegram_id)
        ) as cur:
            return await cur.fetchone()


async def get_all_active_chess_games():
    """همه‌ی بازی‌های شطرنج زنده‌ی در حال انجام — شاملِ بازی‌های «هوش
    مصنوعی» هم می‌شود (برخلافِ get_active_chess_games_excluding که فقط
    برای پیشنهادِ تماشا به شخص ثالث، بازی‌های تک‌نفره را کنار می‌گذارد).
    برای بخشِ «📋 بازی‌های فعال» در منوی شطرنج که باید همه‌ی ترکیب‌ها
    (مدیر×مدیر، مدیر×پیشوا، هرکدام×هوش‌مصنوعی) را یک‌جا نشان بدهد."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM chess_games WHERE status='active' ORDER BY id DESC"
        ) as cur:
            return await cur.fetchall()


async def get_active_chess_games_excluding(telegram_id: int):
    """همه‌ی بازی‌های شطرنج زنده‌ای که الان در جریانند و طرف داده‌شده در
    آن‌ها بازیکن نیست — برای پیشنهاد «تماشا» به شخص ثالث در پنل شطرنج زنده.
    بازی‌های تک‌نفره‌ی «بازی با هوش مصنوعی» (ai_level پر شده) جزو بازی‌های
    قابل‌تماشا حساب نمی‌شوند، چون فقط تمرینِ شخصی‌اند."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT * FROM chess_games WHERE status='active' AND white_id!=? AND black_id!=?
               AND ai_level IS NULL ORDER BY id DESC""",
            (telegram_id, telegram_id)
        ) as cur:
            return await cur.fetchall()


async def set_chess_game_messages(token: str, white_msg_id=None, black_msg_id=None):
    """آی‌دیِ پیام تلگرامیِ حاوی دکمه‌ی «ورود به بازی» برای هر طرف را ذخیره
    می‌کند، تا وقتی بازی تمام شد بتوان همان پیام را به یک پنل «بازی جدید /
    منوی اصلی» ویرایش کرد (به‌جای این‌که دکمه‌ی قدیمی برای همیشه بماند)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE chess_games SET white_msg_id=?, black_msg_id=? WHERE token=?",
            (white_msg_id, black_msg_id, token)
        )
        await db.commit()


async def update_chess_game_move(token, fen, pgn, last_from, last_to, white_time, black_time):
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """UPDATE chess_games SET fen=?, pgn=?, last_move_from=?, last_move_to=?,
               white_time=?, black_time=?, last_move_at=?, draw_offer_by=NULL WHERE token=?""",
            (fen, pgn, last_from, last_to, white_time, black_time, now, token)
        )
        await db.commit()


async def finish_chess_game(token, status, winner_id, white_elo_change=None, black_elo_change=None):
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """UPDATE chess_games SET status=?, winner_id=?, finished_at=?,
               white_elo_change=?, black_elo_change=?, draw_offer_by=NULL WHERE token=?""",
            (status, winner_id, now, white_elo_change, black_elo_change, token)
        )
        await db.commit()


async def get_chess_games_log(period="all", limit=100):
    """لیستِ بازی‌های شطرنج زنده‌ی *تمام‌شده‌ی* مدیران، برای پنل «پیگیری
    بازی‌های مدیران» در پنل مدیر ارشد. period مثل get_action_logs عمل
    می‌کند (today/week/month/all) و بر اساس finished_at فیلتر می‌شود —
    نه created_at — چون تاریخِ «اتفاق افتادنِ نتیجه» مهم است، نه شروع بازی.
    فقط بازی‌های status != 'active' برمی‌گردند (یعنی واقعاً یک نتیجه/دلیل
    پایان دارند)؛ بازی‌های در حال انجام اینجا جایی ندارند.
    مرتب‌سازی: جدیدترین (بر اساس finished_at) اول."""
    # BUG FIX (امنیت): مثل بالا — تاریخ‌ها الان پارامتری‌ان، نه f-string.
    from datetime import timedelta
    now = datetime.now()
    conditions = ["status != 'active'"]
    params = []
    if period == "today":
        conditions.append("finished_at LIKE ?")
        params.append(now.strftime("%Y-%m-%d") + "%")
    elif period == "week":
        conditions.append("finished_at >= ?")
        params.append((now - timedelta(days=7)).isoformat())
    elif period == "month":
        conditions.append("finished_at >= ?")
        params.append((now - timedelta(days=30)).isoformat())
    where = "WHERE " + " AND ".join(conditions)
    params.append(limit)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            f"SELECT * FROM chess_games {where} ORDER BY finished_at DESC LIMIT ?", params
        ) as cur:
            return await cur.fetchall()


async def get_chess_games_log_paginated(period="all", admin_id=None, page=0, page_size=8):
    """نسخه‌ی صفحه‌بندی‌شده‌ی get_chess_games_log — برای بخشِ «لیستِ بازی‌ها»یِ
    قابل‌دسترس برای همه‌ی نقش‌ها (نه فقط پیشوا)، با یک فیلترِ اضافیِ
    اختیاری: فقط بازی‌هایی که یک مدیر/پیشوایِ مشخص در آن‌ها (چه سفید چه
    سیاه) شرکت داشته. period دقیقاً مثلِ get_chess_games_log عمل می‌کند
    (today/week/month/all) و روی finished_at فیلتر می‌شود. فقط بازی‌های
    status != 'active' برمی‌گردند. مرتب‌سازی: جدیدترین اول.

    خروجی: تاپلِ (rows_of_this_page, total_count) — total_count برای
    ساختِ صفحه‌بندی (تعدادِ کل صفحات) لازم است، چون ممکن است هزاران بازی
    ثبت شده باشد و همه را یک‌جا نمی‌شود نشان داد.
    """
    from datetime import timedelta
    now = datetime.now()
    conditions = ["status != 'active'"]
    params = []
    if period == "today":
        conditions.append("finished_at LIKE ?")
        params.append(now.strftime("%Y-%m-%d") + "%")
    elif period == "week":
        conditions.append("finished_at >= ?")
        params.append((now - timedelta(days=7)).isoformat())
    elif period == "month":
        conditions.append("finished_at >= ?")
        params.append((now - timedelta(days=30)).isoformat())
    if admin_id is not None:
        conditions.append("(white_id=? OR black_id=?)")
        params.extend([admin_id, admin_id])
    where = "WHERE " + " AND ".join(conditions)
    page = max(0, page)
    page_size = max(1, page_size)
    offset = page * page_size
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(f"SELECT COUNT(*) AS c FROM chess_games {where}", params) as cur:
            row = await cur.fetchone()
            total = row["c"] if row else 0
        async with db.execute(
            f"SELECT * FROM chess_games {where} ORDER BY finished_at DESC LIMIT ? OFFSET ?",
            params + [page_size, offset],
        ) as cur:
            rows = await cur.fetchall()
        return rows, total


async def set_chess_draw_offer(token, by_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE chess_games SET draw_offer_by=? WHERE token=?", (by_id, token))
        await db.commit()


async def clear_chess_draw_offer(token):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE chess_games SET draw_offer_by=NULL WHERE token=?", (token,))
        await db.commit()


async def get_chess_ai_games_for_user(user_id: int, period: str = "all", limit: int = 100):
    """لیستِ بازی‌های «شطرنج زنده مقابل هوش مصنوعی» یک کاربر (مدیر/پیشوا)،
    برای پنلِ «سوابق چتِ بازی با هوش مصنوعی» در پنل مدیر ارشد — چه بازی
    هنوز فعال باشد چه تمام‌شده (بر خلافِ get_chess_games_log که فقط
    تمام‌شده‌ها را می‌دهد، چون آنجا هدف نتیجه‌ی بازی است نه سابقه‌ی چت).
    period مثل get_chess_games_log (today/week/month/all) عمل می‌کند ولی
    بر اساسِ created_at فیلتر می‌شود، چون بازیِ فعال هنوز finished_at ندارد.
    مرتب‌سازی: قدیمی‌ترین اول (برای ساختِ یک تراسکریپتِ زمانیِ پشتِ‌سرِهم)."""
    from datetime import timedelta
    now = datetime.now()
    conditions = ["ai_level IS NOT NULL", "(white_id=? OR black_id=?)"]
    params = [user_id, user_id]
    if period == "today":
        conditions.append("created_at LIKE ?")
        params.append(now.strftime("%Y-%m-%d") + "%")
    elif period == "week":
        conditions.append("created_at >= ?")
        params.append((now - timedelta(days=7)).isoformat())
    elif period == "month":
        conditions.append("created_at >= ?")
        params.append((now - timedelta(days=30)).isoformat())
    where = "WHERE " + " AND ".join(conditions)
    params.append(limit)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            f"SELECT * FROM chess_games {where} ORDER BY created_at ASC LIMIT ?", params
        ) as cur:
            return await cur.fetchall()


async def add_chess_chat_message(token: str, sender_id: int, sender_name: str, text: str):
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO chess_chat(token, sender_id, sender_name, text, sent_at) VALUES (?,?,?,?,?)",
            (token, sender_id, sender_name, text, now)
        )
        await db.commit()
        return cur.lastrowid


async def get_chess_chat_messages(token: str, after_id: int = 0):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM chess_chat WHERE token=? AND id>? ORDER BY id ASC",
            (token, after_id)
        ) as cur:
            return await cur.fetchall()
