"""
chess_ai.py — موتور ساده‌ی شطرنج برای «بازی با هوش مصنوعی» در شطرنج زنده.

بدون وابستگی به موتور بیرونی (مثل Stockfish)؛ فقط از کتابخانه‌ی chess
(که از قبل در requirements.txt هست) برای تولید حرکت‌های مجاز استفاده
می‌شود. جست‌وجو: negamax با هرسِ alpha-beta + ارزیابیِ ماده + جدول‌های
موقعیتیِ استاندارد و ساده (piece-square tables).

سه سطح سختی تعریف شده که هرکدام عمق جست‌وجو و احتمال «حرکت تصادفی به‌جای
بهترین حرکت» متفاوتی دارند (سطح آسان عمداً گاهی ضعیف بازی می‌کند).

choose_move() یک تابع sync و CPU-bound است؛ فراخوان (game_server.py) باید
آن را با asyncio.to_thread اجرا کند تا event loop اصلی ربات را بلاک نکند.
"""

import random

import chess as pychess

from config import CHESS_AI_ID

AI_ID = CHESS_AI_ID

AI_LEVELS = {
    "easy":   {"label": "🟢 آسان",  "depth": 1, "random_prob": 0.45},
    "medium": {"label": "🟡 متوسط", "depth": 2, "random_prob": 0.12},
    "hard":   {"label": "🔴 سخت",   "depth": 3, "random_prob": 0.0},
}


def ai_display_name(level: str) -> str:
    info = AI_LEVELS.get(level, AI_LEVELS["medium"])
    return f"🤖 هوش مصنوعی ({info['label']})"


# ─── ارزیابیِ موقعیت ────────────────────────────────────────────
PIECE_VALUES = {
    pychess.PAWN: 100, pychess.KNIGHT: 320, pychess.BISHOP: 330,
    pychess.ROOK: 500, pychess.QUEEN: 900, pychess.KING: 0,
}

_PAWN_PST = [
    0,  0,  0,  0,  0,  0,  0,  0,
    50, 50, 50, 50, 50, 50, 50, 50,
    10, 10, 20, 30, 30, 20, 10, 10,
    5,  5, 10, 25, 25, 10,  5,  5,
    0,  0,  0, 20, 20,  0,  0,  0,
    5, -5,-10,  0,  0,-10, -5,  5,
    5, 10, 10,-20,-20, 10, 10,  5,
    0,  0,  0,  0,  0,  0,  0,  0,
]
_KNIGHT_PST = [
    -50,-40,-30,-30,-30,-30,-40,-50,
    -40,-20,  0,  0,  0,  0,-20,-40,
    -30,  0, 10, 15, 15, 10,  0,-30,
    -30,  5, 15, 20, 20, 15,  5,-30,
    -30,  0, 15, 20, 20, 15,  0,-30,
    -30,  5, 10, 15, 15, 10,  5,-30,
    -40,-20,  0,  5,  5,  0,-20,-40,
    -50,-40,-30,-30,-30,-30,-40,-50,
]
_BISHOP_PST = [
    -20,-10,-10,-10,-10,-10,-10,-20,
    -10,  0,  0,  0,  0,  0,  0,-10,
    -10,  0,  5, 10, 10,  5,  0,-10,
    -10,  5,  5, 10, 10,  5,  5,-10,
    -10,  0, 10, 10, 10, 10,  0,-10,
    -10, 10, 10, 10, 10, 10, 10,-10,
    -10,  5,  0,  0,  0,  0,  5,-10,
    -20,-10,-10,-10,-10,-10,-10,-20,
]
_ROOK_PST = [
    0,  0,  0,  0,  0,  0,  0,  0,
    5, 10, 10, 10, 10, 10, 10,  5,
   -5,  0,  0,  0,  0,  0,  0, -5,
   -5,  0,  0,  0,  0,  0,  0, -5,
   -5,  0,  0,  0,  0,  0,  0, -5,
   -5,  0,  0,  0,  0,  0,  0, -5,
   -5,  0,  0,  0,  0,  0,  0, -5,
    0,  0,  0,  5,  5,  0,  0,  0,
]
_QUEEN_PST = [
    -20,-10,-10, -5, -5,-10,-10,-20,
    -10,  0,  0,  0,  0,  0,  0,-10,
    -10,  0,  5,  5,  5,  5,  0,-10,
    -5,  0,  5,  5,  5,  5,  0, -5,
     0,  0,  5,  5,  5,  5,  0, -5,
    -10,  5,  5,  5,  5,  5,  0,-10,
    -10,  0,  5,  0,  0,  0,  0,-10,
    -20,-10,-10, -5, -5,-10,-10,-20,
]
_KING_PST = [
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -20,-30,-30,-40,-40,-30,-30,-20,
    -10,-20,-20,-20,-20,-20,-20,-10,
     20, 20,  0,  0,  0,  0, 20, 20,
     20, 30, 10,  0,  0, 10, 30, 20,
]
_PST = {
    pychess.PAWN: _PAWN_PST, pychess.KNIGHT: _KNIGHT_PST, pychess.BISHOP: _BISHOP_PST,
    pychess.ROOK: _ROOK_PST, pychess.QUEEN: _QUEEN_PST, pychess.KING: _KING_PST,
}


def _evaluate(board: pychess.Board) -> int:
    """ارزیابیِ موقعیت از دیدِ سفید (مثبت یعنی برتریِ سفید)."""
    if board.is_checkmate():
        return -999999 if board.turn == pychess.WHITE else 999999
    if board.is_stalemate() or board.is_insufficient_material():
        return 0
    score = 0
    for square, piece in board.piece_map().items():
        idx = square if piece.color == pychess.WHITE else pychess.square_mirror(square)
        val = PIECE_VALUES[piece.piece_type] + _PST[piece.piece_type][idx]
        score += val if piece.color == pychess.WHITE else -val
    return score


def evaluate_fen(fen: str) -> int:
    """ارزیابیِ یک وضعیت از روی FEN، از دیدِ سفید (برای تصمیمِ هوش مصنوعی
    دربارهٔ قبول/ردِ پیشنهاد تساوی، بدون نیاز به جست‌وجوی کامل)."""
    return _evaluate(pychess.Board(fen))


def _order_moves(board: pychess.Board):
    """حرکت‌های ضربه‌ای را اول می‌گذارد تا هرسِ alpha-beta مؤثرتر باشد."""
    moves = list(board.legal_moves)
    moves.sort(key=lambda m: 1 if board.is_capture(m) else 0, reverse=True)
    return moves


def _negamax(board: pychess.Board, depth: int, alpha: int, beta: int, sign: int) -> int:
    if depth == 0 or board.is_game_over():
        return sign * _evaluate(board)
    best = -10 ** 9
    for move in _order_moves(board):
        board.push(move)
        val = -_negamax(board, depth - 1, -beta, -alpha, -sign)
        board.pop()
        if val > best:
            best = val
        if best > alpha:
            alpha = best
        if alpha >= beta:
            break
    return best


def choose_move(board: pychess.Board, level: str = "medium"):
    """بهترین حرکت را برای نوبتِ فعلیِ روی صفحه برمی‌گرداند (یا None اگر
    حرکت مجازی وجود نداشته باشد). sync و CPU-bound — با asyncio.to_thread
    صدا زده شود."""
    info = AI_LEVELS.get(level, AI_LEVELS["medium"])
    legal = list(board.legal_moves)
    if not legal:
        return None
    if random.random() < info["random_prob"]:
        return random.choice(legal)

    depth = info["depth"]
    sign = 1 if board.turn == pychess.WHITE else -1
    alpha, beta = -10 ** 9, 10 ** 9
    best_move, best_val = None, -10 ** 9
    for move in _order_moves(board):
        board.push(move)
        val = -_negamax(board, depth - 1, -beta, -alpha, -sign)
        board.pop()
        if val > best_val:
            best_val, best_move = val, move
        if best_val > alpha:
            alpha = best_val
    return best_move or random.choice(legal)
