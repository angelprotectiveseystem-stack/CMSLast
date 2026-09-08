"""
chess_analysis.py — تحلیلِ پس از بازی برای شطرنج زنده، به سبکِ «Game Review»ِ
chess.com: از اولِ بازی هر حرکت را بررسی می‌کند، آن را برچسب می‌زند
(بلاندر/اشتباه/نادقیق/خوب/عالی/بهترین‌حرکت/حرکتِ‌عالی/درخشان/کتابی)، برای
هر حرکت امتیازِ موقعیت و — وقتی حرکتِ بهتری وجود داشته — پیشنهادِ آن حرکت
را برمی‌گرداند.

بدون وابستگی به موتورِ بیرونی (مثل Stockfish)؛ از همان موتورِ ساده‌ی
negamax+alpha-beta که برای «بازی با هوش مصنوعی» ساخته شده (chess_ai.py)
استفاده می‌شود — چون این پروژه هیچ باینریِ موتورِ شطرنجی نصب‌شده روی
Railway ندارد و اضافه‌کردنِ Stockfish نیازمندِ تغییرِ فرآیندِ دیپلوی است.
دقتِ این تحلیل بنابراین «حرفه‌ای واقعی» نیست، ولی برای بازی‌های دوستانه/
تورنمنتیِ همین ربات، تصویرِ کاملاً معناداری از کیفیتِ حرکت‌ها می‌دهد.

analyze_game() یک تابعِ sync و CPU-bound است (برای هر حرکتِ بازی یک
جست‌وجوی negamax اجرا می‌کند)؛ فراخوان (game_server.py) باید آن را با
asyncio.to_thread اجرا کند تا event loop اصلی را بلاک نکند.
"""

import math

import chess as pychess

from chess_ai import PIECE_VALUES, search_moves

# ─── عمقِ جست‌وجو ────────────────────────────────────────────────
# برای بازی‌های خیلی طولانی عمق را کم می‌کنیم تا کلِ تحلیل در زمانِ
# معقولی (چند ثانیه تا حدودِ نیم‌دقیقه) روی سرورِ Railway تمام شود.
def _search_depth(n_plies: int) -> int:
    if n_plies <= 30:
        return 3
    return 2


# اولین چند نیم‌حرکتِ هر بازی («کتابی»/تئوری) با جست‌وجوی سبک‌تری بررسی
# می‌شوند — هم برای سرعت، هم چون تشخیصِ «بهترین حرکتِ تئوری» با این موتورِ
# ساده معنای چندانی ندارد؛ chess.com هم این حرکت‌ها را جدا برچسب می‌زند.
_BOOK_PLIES = 6
_BOOK_DEPTH = 1


# ─── برچسب‌ها (کلید، عنوانِ فارسی، ایموجی، رنگ) ───────────────────
_BEST      = ("best",       "بهترین حرکت", "⭐", "#4da3ff")
_EXCELLENT = ("excellent",  "عالی",        "💚", "#3fd68f")
_GOOD      = ("good",       "خوب",         "✔️", "#8fce5a")
_INACCURACY = ("inaccuracy", "نادقیق",     "❓", "#f0b93f")
_MISTAKE   = ("mistake",    "اشتباه",      "❗", "#f0834a")
_BLUNDER   = ("blunder",    "بلاندر",      "❌", "#f0546e")
_BRILLIANT = ("brilliant",  "درخشان",      "💎", "#26c2c2")
_GREAT     = ("great",      "حرکتِ عالی (تنها راه)", "🌟", "#5b7cfa")
_BOOK      = ("book",       "کتابی (تئوری)", "📖", "#9aa4c7")

# آستانه‌های سنتی‌پاون‌ازدست‌رفته (cp_loss) برای برچسب‌های معمولی —
# هرچه کمتر، دقیق‌تر. عدد بالا سقفِ آن دسته است.
_THRESHOLDS = [
    (10,  _BEST),
    (25,  _EXCELLENT),
    (60,  _GOOD),
    (120, _INACCURACY),
    (300, _MISTAKE),
]


def _classify_by_loss(cp_loss: int):
    for ceiling, label in _THRESHOLDS:
        if cp_loss <= ceiling:
            return label
    return _BLUNDER


def _is_sacrifice(board_before: pychess.Board, move: pychess.Move) -> bool:
    """تشخیصِ تقریبیِ «فداکاریِ ماده»: آیا مهره‌ای که جابه‌جا شده، در خانه‌ی
    مقصد بدونِ مدافعِ کافی در معرضِ گرفته‌شدن با مهره‌ای ارزان‌تر قرار
    می‌گیرد؟ اگر بله، و این حرکت با همه‌ی این‌حال بهترینِ روی صفحه باشد،
    نامزدِ برچسبِ «درخشان» است — دقیقاً همان الگویی که در chess.com یک
    حرکتِ !! را از یک حرکتِ ساده‌ی ⭐ جدا می‌کند."""
    piece = board_before.piece_at(move.from_square)
    if not piece or piece.piece_type in (pychess.PAWN, pychess.KING):
        return False
    board_after = board_before.copy(stack=False)
    board_after.push(move)
    to_sq = move.to_square
    attackers = board_after.attackers(not piece.color, to_sq)
    if not attackers:
        return False
    defenders = board_after.attackers(piece.color, to_sq)
    my_value = PIECE_VALUES.get(piece.piece_type, 0)
    cheapest_attacker = min(
        PIECE_VALUES.get(board_after.piece_at(sq).piece_type, 0) for sq in attackers
    )
    return cheapest_attacker < my_value and not defenders


# ─── توضیحِ ریزِ فارسی برای هر برچسب ──────────────────────────────
# چند نسخه‌ی متفاوت برای هر دسته تا با تکرار در طولِ یک بازیِ طولانی
# یکنواخت/ماشینی به‌نظر نرسد؛ به‌صورتِ شبه‌تصادفی (بر اساسِ شماره‌ی نیم‌حرکت)
# انتخاب می‌شود تا نتیجه برای یک بازیِ مشخص همیشه ثابت بماند.
_TEXT_TEMPLATES = {
    "brilliant": [
        "یک فداکاریِ محاسبه‌شده! {san} به‌ظاهر مهره می‌دهد ولی دقیقاً بهترین حرکتِ روی صفحه است.",
        "درخشان! {san} ماده را قربانی می‌کند تا موقعیتی به‌مراتب برتر به‌دست بیاید.",
    ],
    "great": [
        "{san} تنها راهِ واقعی برای حفظِ موقعیت بود — حرکاتِ دیگر به‌سرعت وضعیت را خراب می‌کردند.",
        "پیدا کردنِ {san} کارِ سختی بود؛ باقیِ حرکت‌ها به‌وضوح ضعیف‌تر بودند.",
    ],
    "best": [
        "{san} دقیقاً همان چیزی‌ست که موتور هم انتخاب می‌کرد.",
        "انتخابِ دقیق! {san} بهترین ادامه‌ی ممکن در این موقعیت بود.",
    ],
    "excellent": [
        "{san} حرکتِ بسیار قوی‌ای بود، هرچند یک گزینه‌ی ناچیز بهتر هم وجود داشت.",
        "تقریباً بی‌نقص — {san} فقط کسری از دقتِ کامل فاصله داشت.",
    ],
    "good": [
        "{san} حرکتِ معقولی بود و موقعیت را حفظ می‌کند.",
        "حرکتِ خوبی‌ست؛ گزینه‌ی بهتری هم بود ولی {san} مشکلی ایجاد نمی‌کند.",
    ],
    "inaccuracy": [
        "{san} چندان دقیق نبود — حریف حالا فرصتِ کمی بهتری در اختیار دارد.",
        "کمی نادقیق. {san} بخشی از برتری را از دست می‌دهد.",
    ],
    "mistake": [
        "{san} اشتباهی بود که به حریف امتیاز می‌دهد.",
        "این حرکت موقعیت را به‌وضوح بدتر می‌کند؛ {san} فرصتِ خوبی را از دست داد.",
    ],
    "blunder": [
        "بلاندر بزرگ! {san} مادّه یا موقعیتِ تعیین‌کننده‌ای را واگذار می‌کند.",
        "اشتباهِ فاحش — {san} می‌توانست همین‌جا سرنوشتِ بازی را عوض کند.",
    ],
    "book": [
        "{san} یک حرکتِ شناخته‌شده‌ی افتتاحیه است.",
        "حرکتِ تئوریِ استاندارد؛ {san} هنوز در چارچوبِ خط‌های شناخته‌شده است.",
    ],
}


def _pick_text(key: str, ply: int, san: str, extra: str = "") -> str:
    options = _TEXT_TEMPLATES.get(key) or ["{san}"]
    text = options[ply % len(options)].format(san=san)
    if extra:
        text += " " + extra
    return text


def _cp_to_win_pct(cp: float) -> float:
    """تبدیلِ سنتی‌پاون (از دیدِ سفید) به درصدِ تقریبیِ شانسِ بردِ سفید —
    برای رسمِ نوارِ ارزیابی با یک منحنیِ نرم (نه خطیِ کورکورانه)، دقیقاً
    مثلِ نوارِ ارزیابیِ chess.com/lichess."""
    return 50 + 50 * (2 / (1 + math.exp(-0.00368 * cp)) - 1)


def _accuracy_from_losses(losses) -> float:
    """درصدِ دقتِ تقریبیِ یک طرف از رویِ میانگینِ سنتی‌پاون‌ازدست‌رفته‌اش.
    این یک فرمولِ ساده‌شده‌ی خودمان است (نه پیاده‌سازیِ دقیقِ الگوریتمِ
    داخلیِ chess.com/lichess که منتشر نشده)، calibrate‌شده طوری‌که ۰
    ازدست‌رفته = ۱۰۰٪ و هرچه میانگین بالاتر برود دقت نرم به سمتِ صفر میل
    می‌کند."""
    if not losses:
        return 100.0
    avg = sum(losses) / len(losses)
    acc = 100 * math.exp(-avg / 220.0)
    return round(max(0.0, min(100.0, acc)), 1)


def analyze_game(moves_san, depth: int = None):
    """moves_san: لیستِ حرکت‌ها به‌صورتِ SAN (همان چیزی که در ستونِ pgn
    دیتابیس، جدا‌شده با کاما، ذخیره می‌شود). خروجی: دیکشنری شاملِ لیستِ
    تحلیلِ هر نیم‌حرکت + دقتِ کلیِ هر طرف."""
    board = pychess.Board()
    n = len(moves_san)
    base_depth = depth or _search_depth(n)

    plies = []
    losses = {"w": [], "b": []}

    for i, raw_san in enumerate(moves_san):
        mover_white = board.turn == pychess.WHITE
        side = "w" if mover_white else "b"
        try:
            move = board.parse_san((raw_san or "").strip())
        except Exception:
            # اگر یک حرکتِ ناسازگار/خراب در تاریخچه بود، تحلیل را همان‌جا
            # متوقف می‌کنیم به‌جای این‌که کل درخواست با خطا شکست بخورد.
            break

        is_book = i < _BOOK_PLIES
        search_depth = _BOOK_DEPTH if is_book else base_depth
        values = search_moves(board, search_depth)
        if not values:
            break

        best_move = max(values, key=values.get)
        best_val = values[best_move]
        sorted_vals = sorted(values.values(), reverse=True)
        second_val = sorted_vals[1] if len(sorted_vals) > 1 else best_val
        played_val = values.get(move, best_val)
        cp_loss = max(0, best_val - played_val)
        is_best = move == best_move
        gap_to_second = best_val - second_val

        san_played = board.san(move)
        best_san = None if is_best else board.san(best_move)
        best_uci = None if is_best else best_move.uci()
        is_capture = board.is_capture(move)
        sacrifice = is_best and not is_book and _is_sacrifice(board, move)

        if is_book and cp_loss <= 40:
            label = _BOOK
        elif sacrifice and cp_loss <= 15:
            label = _BRILLIANT
        elif is_best and gap_to_second >= 150 and i >= _BOOK_PLIES:
            label = _GREAT
        else:
            label = _classify_by_loss(cp_loss)

        key, title, icon, color = label
        board.push(move)
        gives_check = board.is_check()
        is_mate = board.is_checkmate()

        eval_cp_white = played_val if mover_white else -played_val
        losses[side].append(cp_loss)

        extra = ""
        if gives_check and not is_mate:
            extra = "و کیش هم می‌دهد."
        elif is_mate:
            extra = "و کیش‌ومات می‌کند!"

        plies.append({
            "ply": i,
            "side": side,
            "san": san_played,
            "uci": move.uci(),
            "from": pychess.square_name(move.from_square),
            "to": pychess.square_name(move.to_square),
            "is_capture": is_capture,
            "gives_check": gives_check,
            "is_mate": is_mate,
            "fen_after": board.fen(),
            "eval_cp": eval_cp_white,
            "win_pct": round(_cp_to_win_pct(eval_cp_white), 1),
            "cp_loss": cp_loss,
            "classification": key,
            "label": title,
            "icon": icon,
            "color": color,
            "text": _pick_text(key, i, san_played, extra),
            "best_san": best_san,
            "best_uci": best_uci,
            "best_from": pychess.square_name(best_move.from_square) if not is_best else None,
            "best_to": pychess.square_name(best_move.to_square) if not is_best else None,
        })

    return {
        "plies": plies,
        "white_accuracy": _accuracy_from_losses(losses["w"]),
        "black_accuracy": _accuracy_from_losses(losses["b"]),
        "white_blunders": sum(1 for p in plies if p["side"] == "w" and p["classification"] == "blunder"),
        "black_blunders": sum(1 for p in plies if p["side"] == "b" and p["classification"] == "blunder"),
        "white_mistakes": sum(1 for p in plies if p["side"] == "w" and p["classification"] == "mistake"),
        "black_mistakes": sum(1 for p in plies if p["side"] == "b" and p["classification"] == "mistake"),
        "white_brilliants": sum(1 for p in plies if p["side"] == "w" and p["classification"] == "brilliant"),
        "black_brilliants": sum(1 for p in plies if p["side"] == "b" and p["classification"] == "brilliant"),
    }
