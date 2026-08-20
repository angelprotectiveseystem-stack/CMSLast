"""
elo.py — سیستم رتبه‌بندی Elo برای شطرنج
"""
import aiosqlite
import logging
from config import DB_PATH

logger = logging.getLogger(__name__)

# ─── ثابت‌های Elo ─────────────────────────────────────────────
ELO_DEFAULT = 1200      # امتیاز اولیه هر بازیکن
ELO_K_NEW = 40          # ضریب K برای بازیکنان جدید (کمتر از ۱۰ بازی)
ELO_K_NORMAL = 20       # ضریب K برای بازیکنان معمولی
ELO_K_MASTER = 10       # ضریب K برای بازیکنان قوی (بالای ۲۴۰۰)


def get_k_factor(rating: float, games_played: int) -> int:
    if games_played < 10:
        return ELO_K_NEW
    if rating >= 2400:
        return ELO_K_MASTER
    return ELO_K_NORMAL


def expected_score(rating_a: float, rating_b: float) -> float:
    """احتمال پیروزی بازیکن A مقابل B"""
    return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))


def calculate_new_ratings(
    rating_white: float, rating_black: float,
    games_white: int, games_black: int,
    result: str  # "white", "black", "draw"
) -> tuple:
    """محاسبه امتیاز جدید هر دو بازیکن"""
    ea = expected_score(rating_white, rating_black)
    eb = expected_score(rating_black, rating_white)

    if result == "white":
        sa, sb = 1.0, 0.0
    elif result == "black":
        sa, sb = 0.0, 1.0
    else:  # draw
        sa, sb = 0.5, 0.5

    ka = get_k_factor(rating_white, games_white)
    kb = get_k_factor(rating_black, games_black)

    new_white = round(rating_white + ka * (sa - ea))
    new_black = round(rating_black + kb * (sb - eb))

    change_white = new_white - rating_white
    change_black = new_black - rating_black

    return new_white, new_black, change_white, change_black


def get_elo_title(rating: float) -> str:
    """عنوان بر اساس امتیاز Elo"""
    if rating >= 2500:
        return "♟️ گرندمستر"
    elif rating >= 2400:
        return "🥇 استاد بین‌المللی"
    elif rating >= 2200:
        return "🥈 استاد فیده"
    elif rating >= 2000:
        return "🥉 کاندیدا استاد"
    elif rating >= 1800:
        return "💎 متخصص"
    elif rating >= 1600:
        return "🔵 کلاس A"
    elif rating >= 1400:
        return "🟢 کلاس B"
    elif rating >= 1200:
        return "🟡 کلاس C"
    else:
        return "🔰 مبتدی"


def get_elo_bar(rating: float) -> str:
    """نوار گرافیکی امتیاز Elo"""
    # بازه ۸۰۰ تا ۲۸۰۰
    pct = max(0, min(100, (rating - 800) / 20))
    filled = int(15 * pct / 100)
    bar = "█" * filled + "░" * (15 - filled)
    return f"[{bar}] {int(rating)}"


# ─── عملیات دیتابیس Elo ──────────────────────────────────────
async def ensure_elo_table():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS player_elo (
                player_id INTEGER PRIMARY KEY,
                rating REAL DEFAULT 1200,
                peak_rating REAL DEFAULT 1200,
                games_played INTEGER DEFAULT 0,
                elo_wins INTEGER DEFAULT 0,
                elo_losses INTEGER DEFAULT 0,
                elo_draws INTEGER DEFAULT 0,
                last_updated TEXT,
                FOREIGN KEY(player_id) REFERENCES players(id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS elo_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id INTEGER,
                match_id INTEGER,
                old_rating REAL,
                new_rating REAL,
                change REAL,
                opponent_id INTEGER,
                result TEXT,
                recorded_at TEXT
            )
        """)
        await db.commit()


async def get_player_elo(player_id: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM player_elo WHERE player_id=?", (player_id,)
        ) as cur:
            row = await cur.fetchone()
            if row:
                return dict(row)
            return {
                "player_id": player_id,
                "rating": ELO_DEFAULT,
                "peak_rating": ELO_DEFAULT,
                "games_played": 0,
                "elo_wins": 0,
                "elo_losses": 0,
                "elo_draws": 0,
            }


async def update_elo_after_match(
    white_id: int, black_id: int,
    result: str, match_id: int
):
    """آپدیت Elo پس از ثبت نتیجه مسابقه"""
    from datetime import datetime
    now = datetime.now().isoformat()

    white_elo = await get_player_elo(white_id)
    black_elo = await get_player_elo(black_id)

    new_w, new_b, chg_w, chg_b = calculate_new_ratings(
        white_elo["rating"], black_elo["rating"],
        white_elo["games_played"], black_elo["games_played"],
        result
    )

    async with aiosqlite.connect(DB_PATH) as db:
        # Update/Insert white
        await db.execute("""
            INSERT INTO player_elo(player_id, rating, peak_rating, games_played,
                elo_wins, elo_losses, elo_draws, last_updated)
            VALUES (?, ?, ?, 1,
                ?, 0, ?,
                ?)
            ON CONFLICT(player_id) DO UPDATE SET
                rating=?,
                peak_rating=MAX(peak_rating, ?),
                games_played=games_played+1,
                elo_wins=elo_wins+?,
                elo_losses=elo_losses+?,
                elo_draws=elo_draws+?,
                last_updated=?
        """, (
            white_id, new_w, new_w,
            1 if result == "white" else 0,
            1 if result == "draw" else 0,
            now,
            new_w, new_w,
            1 if result == "white" else 0,
            1 if result == "black" else 0,
            1 if result == "draw" else 0,
            now
        ))

        # Update/Insert black
        await db.execute("""
            INSERT INTO player_elo(player_id, rating, peak_rating, games_played,
                elo_wins, elo_losses, elo_draws, last_updated)
            VALUES (?, ?, ?, 1,
                ?, 0, ?,
                ?)
            ON CONFLICT(player_id) DO UPDATE SET
                rating=?,
                peak_rating=MAX(peak_rating, ?),
                games_played=games_played+1,
                elo_wins=elo_wins+?,
                elo_losses=elo_losses+?,
                elo_draws=elo_draws+?,
                last_updated=?
        """, (
            black_id, new_b, new_b,
            1 if result == "black" else 0,
            1 if result == "draw" else 0,
            now,
            new_b, new_b,
            1 if result == "black" else 0,
            1 if result == "white" else 0,
            1 if result == "draw" else 0,
            now
        ))

        # History for white
        await db.execute("""
            INSERT INTO elo_history(player_id, match_id, old_rating, new_rating,
                change, opponent_id, result, recorded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (white_id, match_id, white_elo["rating"], new_w, chg_w, black_id,
              "win" if result == "white" else "loss" if result == "black" else "draw", now))

        # History for black
        await db.execute("""
            INSERT INTO elo_history(player_id, match_id, old_rating, new_rating,
                change, opponent_id, result, recorded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (black_id, match_id, black_elo["rating"], new_b, chg_b, white_id,
              "win" if result == "black" else "loss" if result == "white" else "draw", now))

        await db.commit()

    return new_w, new_b, chg_w, chg_b


async def get_elo_leaderboard(limit: int = 10) -> list:
    """جدول رتبه‌بندی Elo"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT pe.*, p.full_name, c.name as class_name
            FROM player_elo pe
            JOIN players p ON pe.player_id = p.id
            LEFT JOIN classes c ON p.class_id = c.id
            WHERE p.status = 'active'
            ORDER BY pe.rating DESC
            LIMIT ?
        """, (limit,)) as cur:
            return await cur.fetchall()


async def get_player_elo_history(player_id: int, limit: int = 10) -> list:
    """تاریخچه تغییرات Elo یک بازیکن"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT eh.*, p.full_name as opponent_name
            FROM elo_history eh
            LEFT JOIN players p ON eh.opponent_id = p.id
            WHERE eh.player_id = ?
            ORDER BY eh.recorded_at DESC
            LIMIT ?
        """, (player_id, limit)) as cur:
            return await cur.fetchall()
