"""
chess_ai_chat.py — چت زنده با حریفِ هوش‌مصنوعیِ «بازی با هوش مصنوعی» در شطرنج زنده.

معماری:
  - این ماژول هیچ حرکتی انتخاب نمی‌کند (آن کار همیشه با chess_ai.choose_move
    انجام می‌شود)؛ فقط وقتی طرفِ انسانی (یا یک تماشاگر) توی چتِ داخلِ بازی
    پیام می‌فرستد و حریف AI_ID است، یک پاسخِ متنیِ کوتاه و آگاه از وضعیتِ
    زنده‌ی صفحه (FEN بازسازی‌شده از رویِ تاریخچه، حرکت‌های اخیر، نوبت، سطح
    سختی) می‌سازد و به‌عنوانِ پیامِ AI_ID در همان چت ذخیره می‌کند.
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
RECENT_MOVES_LIMIT = 16

LEVEL_PERSONA = {
    "easy": (
        "سطح سختیت پایینه (آسان) و گاهی عمداً حرکتِ ضعیف می‌زنی — این را خودت "
        "به‌رو نیاور و به کاربر نگو مگر صراحتاً بپرسد؛ فقط در لحنت زیادی مغرور "
        "یا قهرمانانه نباش."
    ),
    "medium": "سطح سختیت متوسطه — بازیِ محکم ولی نه بی‌نقص داری.",
    "hard": "سطح سختیت بالاست (سخت) — تحلیلِ عمیق‌تر و بازیِ دقیق و بی‌رحمانه‌تری داری.",
}


def _material_summary(board: pychess.Board) -> str:
    """توصیفِ کیفیِ کوتاهِ تعادلِ مادیِ مهره‌ها، تا مدل مجبور نباشد خودش FEN
    را تحلیل کند و بداند دقیقاً کدام طرف الان جلوتر است."""
    values = {pychess.PAWN: 1, pychess.KNIGHT: 3, pychess.BISHOP: 3, pychess.ROOK: 5, pychess.QUEEN: 9}
    white = black = 0
    for _square, piece in board.piece_map().items():
        v = values.get(piece.piece_type, 0)
        if piece.color == pychess.WHITE:
            white += v
        else:
            black += v
    diff = white - black
    if abs(diff) <= 1:
        return "مادیِ مهره‌ها تقریباً برابر است."
    leader = "سفید" if diff > 0 else "سیاه"
    return f"{leader} حدود {abs(diff)} واحدِ پیاده برتریِ مادی دارد."


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


def _system_prompt(game: dict, board: pychess.Board, ai_is_white: bool, recent_chat) -> str:
    level = game.get("ai_level") or "medium"
    persona = LEVEL_PERSONA.get(level, LEVEL_PERSONA["medium"])
    my_color = "سفید" if ai_is_white else "سیاه"
    opp_name = (game.get("black_name") if ai_is_white else game.get("white_name")) or "حریف"
    turn_is_white = board.turn == pychess.WHITE
    turn_who = "خودت" if (turn_is_white == ai_is_white) else opp_name
    moves = [m for m in (game.get("pgn") or "").split(",") if m]
    moves_str = " ".join(moves[-RECENT_MOVES_LIMIT:]) if moves else "(هنوز حرکتی زده نشده)"
    check_note = " کیش شده!" if board.is_check() else ""

    chat_block = ""
    if recent_chat:
        lines = [f"- {m['sender_name']}: {m['text']}" for m in recent_chat[-RECENT_CHAT_LIMIT:]]
        chat_block = "\n\nتاریخچه‌ی همین چت (اخیرترین‌ها):\n" + "\n".join(lines)

    return (
        "تو حریفِ هوش‌مصنوعیِ یک بازیِ زنده‌ی شطرنج، توی یک مینی‌اپِ تلگرامی هستی. "
        f"با مهره‌های {my_color} بازی می‌کنی؛ طرفِ مقابلت «{opp_name}» است. {persona}\n\n"
        "وظیفه‌ات فقط چت‌کردنه، نه انتخابِ حرکت (حرکت‌ها با یک موتورِ جداگانه انتخاب "
        "می‌شوند و ربطی به این گفتگو ندارند). طوری جواب بده که انگار همین لحظه واقعاً "
        "پشتِ صفحه نشسته‌ای و داری بازی می‌کنی — به وضعیتِ فعلیِ صفحه، حرکتِ آخر، و حرفِ "
        "طرف واکنشِ طبیعی نشان بده. کوتاه (۱ تا ۲ جمله‌ی کوتاه، مناسبِ حبابِ چتِ موبایل)، "
        "محاوره‌ای و به فارسی جواب بده — سخنرانی نکن.\n\n"
        "وضعیتِ فعلیِ بازی:\n"
        f"- نوبتِ {turn_who} است.{check_note}\n"
        f"- {_material_summary(board)}\n"
        f"- حرکت‌های اخیر (SAN): {moves_str}"
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
