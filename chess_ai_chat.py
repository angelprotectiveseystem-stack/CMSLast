"""
chess_ai_chat.py — چت زنده با حریفِ هوش‌مصنوعیِ «بازی با هوش مصنوعی» در شطرنج زنده.

معماری:
  - این ماژول هیچ حرکتی انتخاب نمی‌کند (آن کار همیشه با chess_ai.choose_move
    انجام می‌شود)؛ فقط وقتی طرفِ انسانی (یا یک تماشاگر) توی چتِ داخلِ بازی
    پیام می‌فرستد و حریف AI_ID است، یک پاسخِ متنیِ کوتاه و آگاه از وضعیتِ
    زنده‌ی صفحه می‌سازد و به‌عنوانِ پیامِ AI_ID در همان چت ذخیره می‌کند.

  - نکته‌ی مهم دربارهٔ دقتِ وضعیت: به مدل فقط یک خلاصه‌ی کیفی (مثلاً «سفید
    کمی جلوتره») داده نمی‌شود، چون مدل‌های زبانی در بازسازیِ ذهنیِ دقیقِ
    جای مهره‌ها از رویِ یک لیستِ حرکاتِ الجبری معمولاً ضعیف عمل می‌کنند و
    همین باعثِ جواب‌های نادرست دربارهٔ نوبت/حرکت/مهره‌ها می‌شد. برای همین
    اینجا داده‌ی خام و صریح داده می‌شود: دیاگرامِ کاملِ صفحه (خانه‌به‌خانه،
    با برچسبِ ردیف/ستون)، FEN دقیق، لیستِ شماره‌دارِ همه‌ی حرکت‌ها، لیستِ
    دقیقِ مهره‌های ازدست‌رفته‌ی هر طرف، و زمانِ باقی‌مانده‌ی هر دو طرف —
    و به مدل صریحاً گفته می‌شود که این‌ها را عیناً به‌عنوانِ واقعیتِ صفحه
    بپذیرد و هیچ محاسبه/حدسِ شطرنجیِ خودش را جایگزینِ آن‌ها نکند.

  - از همان زیرساختِ Gemini که برای دستیارِ مدیریتی (ai_assistant.py) از قبل
    تنظیم شده استفاده می‌شود (همان کلید/مدل/فال‌بک/retry) — چیزِ جدیدی
    ست نمی‌شود.
  - fire-and-forget است: از /api/chat (game_server.py) با asyncio.create_task
    صدا زده می‌شود تا ریکوئستِ اصلیِ کاربر منتظرِ جوابِ Gemini نماند؛ هر
    خطایی فقط لاگ می‌شود و به کاربر برنمی‌گردد، چون این صرفاً گپ‌وگفته و
    نباید جریانِ اصلیِ بازی را مختل کند.
"""
import logging
import re

import chess as pychess

import database as db
from chess_ai import AI_ID
from ai_assistant import GEMINI_API_KEY, _call_gemini

logger = logging.getLogger(__name__)

CHAT_REPLY_MAX_LEN = 300
RECENT_CHAT_LIMIT = 10
MOVE_HISTORY_PLY_LIMIT = 60  # آخرین ۶۰ نیم‌حرکت (۳۰ حرکتِ کامل) — برای بازی‌های طولانی‌تر

LEVEL_PERSONA = {
    "easy": (
        "سطح سختیت پایینه (آسان) و گاهی عمداً حرکتِ ضعیف می‌زنی — این را خودت "
        "به‌رو نیاور و به کاربر نگو مگر صراحتاً بپرسد؛ فقط در لحنت زیادی مغرور "
        "یا قهرمانانه نباش."
    ),
    "medium": "سطح سختیت متوسطه — بازیِ محکم ولی نه بی‌نقص داری.",
    "hard": "سطح سختیت بالاست (سخت) — تحلیلِ عمیق‌تر و بازیِ دقیق و بی‌رحمانه‌تری داری.",
}

_PIECE_NAME_FA = {
    pychess.PAWN: "پیاده", pychess.KNIGHT: "اسب", pychess.BISHOP: "فیل",
    pychess.ROOK: "رخ", pychess.QUEEN: "وزیر", pychess.KING: "شاه",
}
_STARTING_COUNTS = {
    pychess.PAWN: 8, pychess.KNIGHT: 2, pychess.BISHOP: 2, pychess.ROOK: 2, pychess.QUEEN: 1,
}


def _board_diagram(board: pychess.Board) -> str:
    """دیاگرامِ خانه‌به‌خانه‌ی صفحه با برچسبِ ردیف (۸ تا ۱) و ستون (a تا h)،
    تا مدل مجبور نباشد از رویِ حرکت‌ها خودش صفحه را در ذهن بسازد. حروفِ
    بزرگ = سفید، حروفِ کوچک = سیاه، نقطه = خانه‌ی خالی."""
    rows = str(board).split("\n")  # python-chess: رتبه‌ی ۸ در سطرِ اول
    lines = [f"{8 - i}  {row}" for i, row in enumerate(rows)]
    lines.append("   a b c d e f g h")
    return "\n".join(lines)


def _captured_summary(board: pychess.Board) -> str:
    """لیستِ دقیقِ مهره‌های ازدست‌رفته‌ی هر طرف (نه فقط یک عددِ کلی)، از رویِ
    شمارشِ واقعیِ مهره‌های روی صفحه در برابرِ چیدمانِ استاندارد."""
    have = {pychess.WHITE: {}, pychess.BLACK: {}}
    for _sq, piece in board.piece_map().items():
        have[piece.color][piece.piece_type] = have[piece.color].get(piece.piece_type, 0) + 1

    parts = []
    for color, label in ((pychess.WHITE, "سفید"), (pychess.BLACK, "سیاه")):
        lost = []
        for pt, start_n in _STARTING_COUNTS.items():
            n_lost = start_n - have[color].get(pt, 0)
            if n_lost > 0:
                lost.append(f"{n_lost} {_PIECE_NAME_FA[pt]}")
        parts.append(f"{label}: {'، '.join(lost) if lost else 'هیچ‌چیز از دست نداده'}")
    return " | ".join(parts)


def _numbered_moves(pgn: str) -> str:
    """لیستِ کاملِ حرکت‌ها به‌فرمِ استانداردِ شماره‌گذاری‌شده (مثلِ ۱. e4 e5
    ۲. Nf3 ...)، تا رابطه‌ی نوبت↔شماره‌ی حرکت برای مدل روشن باشد. اگه بریده
    شود (بازیِ خیلی طولانی)، شماره‌ی حرکت‌ها همچنان واقعی می‌ماند (نه از ۱
    شروع می‌شود) — وگرنه خودش یک منبعِ جدیدِ گمراهی برای مدل می‌شد."""
    moves = [m for m in (pgn or "").split(",") if m]
    if not moves:
        return "(هنوز حرکتی زده نشده)"
    total = len(moves)
    start_idx = 0
    prefix = ""
    if total > MOVE_HISTORY_PLY_LIMIT:
        start_idx = total - MOVE_HISTORY_PLY_LIMIT
        prefix = f"(… {start_idx} نیم‌حرکتِ اول حذف شد؛ ادامه از همون‌جا با شماره‌ی واقعی) "
    sliced = moves[start_idx:]

    out = []
    i, idx = 0, start_idx
    while i < len(sliced):
        move_num = idx // 2 + 1
        if idx % 2 == 0:
            white_m = sliced[i]
            black_m = sliced[i + 1] if i + 1 < len(sliced) else None
            pair = white_m + (f" {black_m}" if black_m else "")
            out.append(f"{move_num}.{pair}")
            i += 2
            idx += 2
        else:
            # بریده‌شده وسطِ یک جفت، درست از نوبتِ سیاه شروع می‌شود
            out.append(f"{move_num}...{sliced[i]}")
            i += 1
            idx += 1
    return prefix + " ".join(out)


def _fmt_clock(seconds) -> str:
    try:
        seconds = int(seconds)
    except (TypeError, ValueError):
        return "؟"
    m, s = divmod(max(seconds, 0), 60)
    return f"{m}:{s:02d}"


def _build_board(game: dict) -> pychess.Board:
    """بازسازیِ صفحه از رویِ تاریخچه‌ی SAN ذخیره‌شده (game['pgn'])."""
    board = pychess.Board()
    pgn = game.get("pgn") or ""
    if pgn:
        for san in pgn.split(","):
            if not san:
                continue
            try:
                board.push_san(san)
            except Exception:
                break  # اگه یه SAN مشکل داشت، همون‌جا متوقف شو نه اینکه کرش کنه
    return board


def _game_status_note(board: pychess.Board) -> str:
    if board.is_checkmate():
        return "کیش‌ومات شده!"
    if board.is_stalemate():
        return "پات (استیل‌میت) شده — مساوی."
    if board.is_check():
        return "کیش شده!"
    return "بازی عادی در جریان است (نه کیش، نه مات)."


def _system_prompt(game: dict, board: pychess.Board, ai_is_white: bool, recent_chat) -> str:
    level = game.get("ai_level") or "medium"
    persona = LEVEL_PERSONA.get(level, LEVEL_PERSONA["medium"])
    my_color = "سفید" if ai_is_white else "سیاه"
    opp_name = (game.get("black_name") if ai_is_white else game.get("white_name")) or "حریف"
    turn_is_white = board.turn == pychess.WHITE
    turn_who = "خودت" if (turn_is_white == ai_is_white) else opp_name

    last_from, last_to = game.get("last_move_from"), game.get("last_move_to")
    last_move_note = f"آخرین حرکتِ روی صفحه: از {last_from} به {last_to}." if (last_from and last_to) else "هنوز حرکتی انجام نشده."

    chat_block = ""
    if recent_chat:
        lines = [f"- {m['sender_name']}: {m['text']}" for m in recent_chat[-RECENT_CHAT_LIMIT:]]
        chat_block = "\n\nتاریخچه‌ی همین چت (اخیرترین‌ها):\n" + "\n".join(lines)

    return (
        "تو حریفِ هوش‌مصنوعیِ یک بازیِ زنده‌ی شطرنج، توی یک مینی‌اپِ تلگرامی هستی. "
        f"با مهره‌های {my_color} بازی می‌کنی؛ طرفِ مقابلت «{opp_name}» است. {persona}\n\n"
        "وظیفه‌ات فقط چت‌کردنه، نه انتخابِ حرکت (حرکت‌ها با یک موتورِ جداگانه انتخاب "
        "می‌شوند و ربطی به این گفتگو ندارند). طوری جواب بده که انگار همین لحظه واقعاً "
        "پشتِ صفحه نشسته‌ای و داری بازی می‌کنی. کوتاه (۱ تا ۲ جمله‌ی کوتاه، مناسبِ حبابِ "
        "چتِ موبایل)، محاوره‌ای و به فارسی جواب بده — سخنرانی نکن.\n\n"
        "⚠️ وضعیتِ زیر، واقعیتِ دقیق و قطعیِ همین لحظه‌ی صفحه است (از روی خودِ داده‌های "
        "بازی محاسبه شده، نه حدس). هر سوالی دربارهٔ نوبت، حرکت‌ها، وضعیتِ کیش/مات، یا "
        "این‌که کدوم مهره کجاست را فقط دقیقاً از رویِ همین اطلاعات جواب بده — هیچ‌وقت خودت "
        "روی حرکت‌ها محاسبه/تحلیل نکن و جای مهره‌ای را حدس نزن؛ اگه چیزی بیرون از این "
        "داده‌هاست (مثلاً حرکتِ بعدیِ خودت که هنوز محاسبه نشده)، صادقانه بگو الان نمی‌دونی، "
        "بلوف نزن.\n\n"
        "وضعیتِ فعلیِ بازی:\n"
        f"- نوبتِ {turn_who} است.\n"
        f"- {_game_status_note(board)}\n"
        f"- {last_move_note}\n"
        f"- زمانِ باقی‌مانده: سفید {_fmt_clock(game.get('white_time'))} / سیاه {_fmt_clock(game.get('black_time'))}\n"
        f"- مهره‌های ازدست‌رفته: {_captured_summary(board)}\n"
        f"- دیاگرامِ کاملِ صفحه (حروفِ بزرگ=سفید، کوچک=سیاه، نقطه=خالی):\n{_board_diagram(board)}\n"
        f"- FEN دقیق: {board.fen()}\n"
        f"- همه‌ی حرکت‌ها تا الان (شماره‌گذاری‌شده): {_numbered_moves(game.get('pgn'))}"
        f"{chat_block}\n\n"
        "قوانین:\n"
        "- هیچ‌وقت لو نده که مدلِ زبانی/هوش‌مصنوعیِ زیرساختی هستی یا نامِ سازنده/شرکتِ "
        "پشتِ مدل را ببری؛ خودت را فقط همان حریفِ رباتیِ همین بازی بدان.\n"
        "- هیچ‌وقت حرکتِ بعدیِ خودت یا نتیجه‌ی نهاییِ بازی را از قبل لو نده یا قول قطعی نده.\n"
        "- اگر طرف شوخی/طعنه/فحشِ رفیقانه زد، بی‌تعارف و با همون لحن جواب بده؛ فقط از "
        "خط‌قرمزهای معمول (توهینِ قومی/مذهبی/جنسیتی/ظاهری، تهدیدِ واقعی) رد نشو.\n"
        "- اگر سوالِ فنیِ واقعی درباره‌ی قوانینِ شطرنج پرسید (مثلاً آنپاسان، رخ‌بازی)، درست "
        "و کوتاه راهنمایی‌اش کن.\n"
        "- فقط متنِ ساده برگردان؛ بدون مارک‌داون و حداکثر یک ایموجی."
    )


async def maybe_reply_to_chat(token: str, game: dict, human_text: str):
    """اگر حریفِ این بازی هوش‌مصنوعی باشد، یک جوابِ چتِ طبیعی می‌سازد و در همان
    چتِ بازی ذخیره می‌کند. fire-and-forget — هر خطا فقط لاگ می‌شود."""
    if AI_ID not in (game.get("white_id"), game.get("black_id")):
        return
    if not GEMINI_API_KEY:
        return
    if game.get("status") != "active":
        return

    ai_is_white = game.get("white_id") == AI_ID
    ai_name = (game.get("white_name") if ai_is_white else game.get("black_name")) or "🤖 هوش مصنوعی"

    try:
        # وضعیتِ کاملاً تازه از دیتابیس (نه همون game که موقعِ ارسالِ چتِ کاربر
        # پاس داده شده)، تا اگه بینِ ارسالِ پیام و اجرای این تسکِ پس‌زمینه یک
        # حرکتِ دیگه (مثلاً حرکتِ هوش‌مصنوعی که بلافاصله بعدِ حرکتِ انسان انجام
        # می‌شود) ثبت شده باشد، همیشه از روی آخرین وضعیتِ واقعی جواب بدهیم.
        fresh_game = await db.get_chess_game(token)
        if fresh_game:
            game = fresh_game

        board = _build_board(game)
        recent_chat = await db.get_chess_chat_messages(token, 0)
        system_prompt = _system_prompt(game, board, ai_is_white, recent_chat)
        contents = [
            {"role": "user", "parts": [{"text": system_prompt}]},
            {"role": "model", "parts": [{"text": "باشه، آماده‌ام."}]},
            {"role": "user", "parts": [{"text": human_text}]},
        ]
        data = await _call_gemini(contents, None)
        parts = data["candidates"][0]["content"]["parts"]
        reply_text = "".join(p.get("text", "") for p in parts).strip()
        if not reply_text:
            return
        reply_text = re.sub(r"\s+", " ", reply_text).strip()[:CHAT_REPLY_MAX_LEN]
        await db.add_chess_chat_message(token, AI_ID, ai_name, reply_text)
    except Exception:
        logger.exception("Chess AI chat reply failed for token=%s", token)
