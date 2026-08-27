import turso_db as aiosqlite
import json
import logging
from datetime import datetime
from config import DB_PATH, STATUS_NORMAL, ROLE_PISHVA

logger = logging.getLogger(__name__)


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
        """)

        # ─── Lightweight migrations (add columns if missing) ──────────
        # از ALTER TABLE استفاده می‌کنیم چون ستون‌های جدید بعد از اولین
        # اجرای init_db اضافه شدن. اگه ستون از قبل باشه، خطا رو نادیده می‌گیریم.
        for stmt in (
            "ALTER TABLE matches ADD COLUMN claimed_by INTEGER",
            "ALTER TABLE matches ADD COLUMN claimed_at TEXT",
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
            "pishva_display_name": "پیشوا",
            "team_mode_enabled": "0",
            "team_registration_enabled": "1",
            "managers_can_create_teams": "0",
            "announcement_group_id": "",
            "bot_update_mode": "0",
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
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM system_settings WHERE key=?", (key,)) as cur:
            row = await cur.fetchone()
            return row[0] if row else default


async def set_setting(key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO system_settings(key, value) VALUES (?, ?)",
            (key, value)
        )
        await db.commit()


# ─── Admins ───────────────────────────────────────────────────
async def get_admin(telegram_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM admins WHERE telegram_id=?", (telegram_id,)) as cur:
            return await cur.fetchone()


async def get_all_admins():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM admins ORDER BY joined_at DESC") as cur:
            return await cur.fetchall()


async def get_active_admins():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM admins WHERE is_active=1") as cur:
            return await cur.fetchall()


async def create_admin(telegram_id, username, full_name, role):
    now = datetime.now().isoformat()
    default_perms = json.dumps({
        "notifications": True, "news": True, "match_management": True,
        "view_players": True, "issue_warning": True, "request_ban": True,
        "direct_ban": False, "assign_task": False, "report": True,
        "bot_active": True, "settings_access": False, "senior_admin": False,
        "edit_delete_match": True, "communications": True,
    })
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO admins(telegram_id,username,full_name,display_name,role,joined_at,last_active,permissions) VALUES (?,?,?,?,?,?,?,?)",
            (telegram_id, username, full_name, full_name, role, now, now, default_perms)
        )
        await db.commit()


async def update_admin_activity(telegram_id):
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE admins SET last_active=? WHERE telegram_id=?", (now, telegram_id))
        await db.commit()


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


async def update_admin_display_name(telegram_id: int, name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE admins SET display_name=? WHERE telegram_id=?", (name, telegram_id))
        await db.commit()


async def add_admin_warning(telegram_id: int, reason: str, issued_by: int):
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE admins SET warnings=warnings+1 WHERE telegram_id=?", (telegram_id,))
        await db.execute(
            "INSERT INTO warnings_log(target_type,target_id,reason,issued_by,issued_at) VALUES (?,?,?,?,?)",
            ("admin", telegram_id, reason, issued_by, now)
        )
        await db.commit()


async def kick_admin(telegram_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE admins SET is_active=0 WHERE telegram_id=?", (telegram_id,))
        await db.commit()


# ─── Classes ─────────────────────────────────────────────────
async def get_all_classes():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM classes ORDER BY name") as cur:
            return await cur.fetchall()


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


async def rename_class(class_id: int, new_name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE classes SET name=? WHERE id=?", (new_name, class_id))
        await db.commit()


# ─── Players ─────────────────────────────────────────────────
async def get_all_players():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT p.*, c.name as class_name FROM players p LEFT JOIN classes c ON p.class_id=c.id ORDER BY p.full_name"
        ) as cur:
            return await cur.fetchall()


async def get_active_players():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT p.*, c.name as class_name FROM players p LEFT JOIN classes c ON p.class_id=c.id WHERE p.status='active' ORDER BY p.full_name"
        ) as cur:
            return await cur.fetchall()


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
        return cur.lastrowid


async def update_player_stats(player_id: int, result: str):
    """result: 'win','loss','draw'"""
    col = {"win": "wins", "loss": "losses", "draw": "draws"}.get(result)
    if col:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(f"UPDATE players SET {col}={col}+1 WHERE id=?", (player_id,))
            await db.commit()


async def update_player(player_id: int, **kwargs):
    if not kwargs:
        return
    sets = ", ".join(f"{k}=?" for k in kwargs)
    vals = list(kwargs.values()) + [player_id]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE players SET {sets} WHERE id=?", vals)
        await db.commit()


async def add_player_warning(player_id: int, reason: str, issued_by: int):
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE players SET warnings=warnings+1 WHERE id=?", (player_id,))
        await db.execute(
            "INSERT INTO warnings_log(target_type,target_id,reason,issued_by,issued_at) VALUES (?,?,?,?,?)",
            ("player", player_id, reason, issued_by, now)
        )
        await db.commit()


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
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT p.*, c.name as class_name FROM players p LEFT JOIN classes c ON p.class_id=c.id WHERE p.status='active' AND p.warnings < 3 ORDER BY p.full_name"
        ) as cur:
            return await cur.fetchall()


# ─── Tournaments ─────────────────────────────────────────────
async def get_all_tournaments():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM tournaments ORDER BY created_at DESC") as cur:
            return await cur.fetchall()


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
        return cur.lastrowid


async def update_tournament(tid: int, **kwargs):
    if not kwargs:
        return
    sets = ", ".join(f"{k}=?" for k in kwargs)
    vals = list(kwargs.values()) + [tid]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE tournaments SET {sets} WHERE id=?", vals)
        await db.commit()


async def set_default_tournament(tid: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE tournaments SET is_default=0")
        await db.execute("UPDATE tournaments SET is_default=1 WHERE id=?", (tid,))
        await db.commit()


async def get_tournament_stats(tid: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) as total, SUM(CASE WHEN result IS NOT NULL THEN 1 ELSE 0 END) as done FROM matches WHERE tournament_id=?",
            (tid,)
        ) as cur:
            row = await cur.fetchone()
            total = row[0] or 0
            done = row[1] or 0
        async with db.execute(
            "SELECT COUNT(DISTINCT white_player_id)+COUNT(DISTINCT black_player_id) FROM matches WHERE tournament_id=?",
            (tid,)
        ) as cur2:
            pass
        return {"total": total, "done": done}


# ─── Matches ─────────────────────────────────────────────────
async def create_match(white_id, black_id, match_date, tournament_id, created_by) -> int:
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO matches(white_player_id,black_player_id,match_date,tournament_id,created_by,created_at) VALUES (?,?,?,?,?,?)",
            (white_id, black_id, match_date, tournament_id, created_by, now)
        )
        await db.commit()
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


async def set_match_result(mid: int, result: str, draw_reason: str, updated_by: int):
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE matches SET result=?,draw_reason=?,updated_by=?,updated_at=? WHERE id=?",
            (result, draw_reason, updated_by, now, mid)
        )
        await db.commit()


async def record_match_result(mid: int, result: str, reason: str, updated_by: int):
    """
    ثبت نتیجه‌ی مسابقه + آپدیت آمار بازیکن‌ها، با دو تا محافظ:

    1) idempotency guard: اگه مسابقه از قبل نتیجه داشته باشه (مثلاً به‌خاطر
       دوبار تپ کردن ادمین)، هیچ نوشتنی انجام نمی‌ده و False برمی‌گردونه.
    2) اگه وسط کار (بین قدم‌ها) خطا بخوریم، دقیقاً می‌فهمیم کدوم قدم شکست
       خورده (تو لاگ ثبت می‌شه) و exception دوباره raise می‌شه تا لایه‌ی
       بالاتر (matches.py) بتونه به پیشوا هشدار بده که این مسابقه ممکنه
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
    from datetime import timedelta
    now = datetime.now()
    where = ""
    if period == "today":
        d = now.strftime("%Y-%m-%d")
        where = f"WHERE m.match_date='{d}'"
    elif period == "week":
        d = (now - timedelta(days=7)).isoformat()
        where = f"WHERE m.created_at>='{d}'"
    elif period == "month":
        d = (now - timedelta(days=30)).isoformat()
        where = f"WHERE m.created_at>='{d}'"
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            f"""SELECT m.*, wp.full_name as white_name, bp.full_name as black_name
               FROM matches m
               LEFT JOIN players wp ON m.white_player_id=wp.id
               LEFT JOIN players bp ON m.black_player_id=bp.id
               {where} ORDER BY m.created_at DESC LIMIT 50"""
        ) as cur:
            return await cur.fetchall()


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


async def update_match(mid: int, **kwargs):
    if not kwargs:
        return
    sets = ", ".join(f"{k}=?" for k in kwargs)
    vals = list(kwargs.values()) + [mid]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE matches SET {sets} WHERE id=?", vals)
        await db.commit()


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
async def log_action(admin_id, action_type, description, target_id=None):
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO action_logs(admin_id,action_type,description,target_id,logged_at) VALUES (?,?,?,?,?)",
            (admin_id, action_type, description, target_id, now)
        )
        await db.commit()


async def get_action_logs(period="all", admin_id=None):
    from datetime import timedelta
    now = datetime.now()
    conditions = []
    if period == "today":
        d = now.strftime("%Y-%m-%d")
        conditions.append(f"logged_at LIKE '{d}%'")
    elif period == "week":
        d = (now - timedelta(days=7)).isoformat()
        conditions.append(f"logged_at >= '{d}'")
    elif period == "month":
        d = (now - timedelta(days=30)).isoformat()
        conditions.append(f"logged_at >= '{d}'")
    if admin_id:
        conditions.append(f"admin_id = {admin_id}")
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(f"SELECT * FROM action_logs {where} ORDER BY logged_at DESC LIMIT 100") as cur:
            return await cur.fetchall()


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
        DELETE FROM players;
        DELETE FROM classes;
        DELETE FROM matches;
        DELETE FROM teams;
        DELETE FROM team_members;
        DELETE FROM team_matches;
        DELETE FROM team_match_boards;
        DELETE FROM warnings_log;
        UPDATE tournaments SET status='archived';
        """)
        await db.commit()


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


async def unblock_user(telegram_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM blocked_users WHERE telegram_id=?", (telegram_id,))
        await db.commit()


async def get_blocked_user(telegram_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM blocked_users WHERE telegram_id=?", (telegram_id,)) as cur:
            return await cur.fetchone()


async def get_all_blocked():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM blocked_users ORDER BY blocked_at DESC") as cur:
            return await cur.fetchall()


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
            return existing["id"], False
        else:
            cur = await db.execute(
                """INSERT INTO players(full_name,class_id,status,warnings,is_elite,is_special,
                   wins,losses,draws,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (full_name, class_id, status or "active", warnings, is_elite, is_special,
                 wins, losses, draws, now)
            )
            await db.commit()
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
        return cur.lastrowid
