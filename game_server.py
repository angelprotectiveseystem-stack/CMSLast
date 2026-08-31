"""
game_server.py
سرور وب مینی‌اپ شطرنج — سرو کردن فایل‌های استاتیک وب‌اپ و API بازی زنده.
این سرور به‌صورت هم‌زمان با ربات (در همان event loop) با aiohttp اجرا می‌شود.
"""

import hashlib
import hmac
import json
import logging
import os
import secrets
import time
import uuid
from urllib.parse import parse_qsl

import chess as pychess
from aiohttp import web

import database as db
from config import BOT_TOKEN, WEBAPP_PORT

logger = logging.getLogger(__name__)

WEBAPP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "webapp")
INIT_DATA_MAX_AGE = 24 * 3600  # ثانیه


def _verify_init_data(init_data: str):
    """اعتبارسنجی امضای initData تلگرام طبق مستندات رسمی WebApp.
    اگر معتبر باشد، دیکشنری user را برمی‌گرداند؛ در غیر این صورت None."""
    if not init_data or not BOT_TOKEN:
        return None
    try:
        pairs = dict(parse_qsl(init_data, strict_parsing=True))
    except ValueError:
        return None
    recv_hash = pairs.pop("hash", None)
    if not recv_hash:
        return None
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    computed = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(computed, recv_hash):
        return None
    auth_date = int(pairs.get("auth_date", "0"))
    if time.time() - auth_date > INIT_DATA_MAX_AGE:
        return None
    user_raw = pairs.get("user")
    if not user_raw:
        return None
    try:
        return json.loads(user_raw)
    except Exception:
        return None


async def _resolve_user_id(request_json):
    """کاربر فراخوان را از initData استخراج می‌کند. برای تست محلی، اگر initData
    خالی بود و DEBUG_ALLOW_UNSAFE فعال بود، user_id مستقیم را می‌پذیرد (فقط توسعه)."""
    init_data = request_json.get("init_data") or ""
    user = _verify_init_data(init_data)
    if user and "id" in user:
        return user["id"], user.get("first_name") or user.get("username") or "بازیکن"
    return None, None


def _game_to_state(game, viewer_id):
    return {
        "fen": game["fen"],
        "status": game["status"],
        "white_id": game["white_id"],
        "black_id": game["black_id"],
        "white_name": game["white_name"],
        "black_name": game["black_name"],
        "white_time": game["white_time"],
        "black_time": game["black_time"],
        "winner_id": game["winner_id"],
        "last_move": (
            {"from": game["last_move_from"], "to": game["last_move_to"]}
            if game["last_move_from"] else None
        ),
        "you_id": viewer_id,
    }


def _apply_clock_decay(game):
    """قبل از پاسخ‌دادن، زمان طرف نوبت‌دار را بر اساس فاصله از آخرین حرکت کم می‌کند
    تا کلاک‌ها بدون نیاز به تایمر سمت سرور جداگانه به‌روز بمانند."""
    if game["status"] != "active":
        return dict(game)
    board = pychess.Board(game["fen"])
    elapsed = 0
    try:
        from datetime import datetime
        last = datetime.fromisoformat(game["last_move_at"])
        elapsed = max(0, (datetime.now() - last).total_seconds())
    except Exception:
        elapsed = 0
    g = dict(game)
    if board.turn == pychess.WHITE:
        g["white_time"] = max(0, game["white_time"] - elapsed)
    else:
        g["black_time"] = max(0, game["black_time"] - elapsed)
    return g


routes = web.RouteTableDef()


@routes.get("/webapp/{tail:.*}")
async def static_files(request):
    tail = request.match_info["tail"] or "index.html"
    path = os.path.normpath(os.path.join(WEBAPP_DIR, tail))
    if not path.startswith(WEBAPP_DIR):
        raise web.HTTPForbidden()
    if os.path.isdir(path):
        path = os.path.join(path, "index.html")
    if not os.path.isfile(path):
        raise web.HTTPNotFound()
    return web.FileResponse(path)


@routes.get("/webapp")
async def webapp_root(request):
    return web.FileResponse(os.path.join(WEBAPP_DIR, "index.html"))


@routes.get("/api/state")
async def api_state(request):
    token = request.query.get("token")
    game = await db.get_chess_game(token) if token else None
    if not game:
        return web.json_response({"ok": False, "error": "بازی پیدا نشد یا منقضی شده است."})
    viewer_id = request.query.get("uid")
    game = _apply_clock_decay(game)
    if game["status"] == "active":
        loser = None
        if game["white_time"] <= 0:
            loser, winner = game["white_id"], game["black_id"]
        elif game["black_time"] <= 0:
            loser, winner = game["black_id"], game["white_id"]
        if loser:
            await db.finish_chess_game(token, "timeout", winner)
            game["status"] = "timeout"
            game["winner_id"] = winner
    return web.json_response({"ok": True, "state": _game_to_state(game, viewer_id)})


@routes.post("/api/move")
async def api_move(request):
    body = await request.json()
    token = body.get("token")
    user_id, _ = await _resolve_user_id(body)
    game = await db.get_chess_game(token) if token else None
    if not game:
        return web.json_response({"ok": False, "error": "بازی پیدا نشد."})
    if game["status"] != "active":
        return web.json_response({"ok": False, "error": "بازی تمام شده است."})
    if user_id is None:
        return web.json_response({"ok": False, "error": "احراز هویت ناموفق بود."})
    if user_id not in (game["white_id"], game["black_id"]):
        return web.json_response({"ok": False, "error": "شما در این بازی نیستید."})

    game = _apply_clock_decay(game)
    board = pychess.Board(game["fen"])
    is_white_turn = board.turn == pychess.WHITE
    turn_id = game["white_id"] if is_white_turn else game["black_id"]
    if user_id != turn_id:
        return web.json_response({"ok": False, "error": "نوبت شما نیست."})

    frm, to, promo = body.get("from"), body.get("to"), body.get("promotion")
    uci = frm + to + (promo if promo else "")
    try:
        move = pychess.Move.from_uci(uci)
    except Exception:
        return web.json_response({"ok": False, "error": "حرکت نامعتبر."})
    if move not in board.legal_moves:
        return web.json_response({"ok": False, "error": "حرکت غیرمجاز است."})

    board.push(move)
    status, winner = "active", None
    if board.is_checkmate():
        status = "checkmate"
        winner = user_id
    elif board.is_stalemate() or board.is_insufficient_material() or board.is_seventyfive_moves() or board.is_fivefold_repetition():
        status = "draw"

    await db.update_chess_game_move(
        token, board.fen(), "", frm, to,
        game["white_time"], game["black_time"]
    )
    if status != "active":
        await db.finish_chess_game(token, status, winner)

    fresh = await db.get_chess_game(token)
    return web.json_response({"ok": True, "state": _game_to_state(fresh, user_id)})


@routes.post("/api/resign")
async def api_resign(request):
    body = await request.json()
    token = body.get("token")
    user_id, _ = await _resolve_user_id(body)
    game = await db.get_chess_game(token) if token else None
    if not game or game["status"] != "active":
        return web.json_response({"ok": False, "error": "بازی فعالی یافت نشد."})
    if user_id not in (game["white_id"], game["black_id"]):
        return web.json_response({"ok": False, "error": "شما در این بازی نیستید."})
    winner = game["black_id"] if user_id == game["white_id"] else game["white_id"]
    await db.finish_chess_game(token, "resigned", winner)
    fresh = await db.get_chess_game(token)
    return web.json_response({"ok": True, "state": _game_to_state(fresh, user_id)})


@routes.post("/api/draw_offer")
async def api_draw_offer(request):
    body = await request.json()
    token = body.get("token")
    user_id, _ = await _resolve_user_id(body)
    game = await db.get_chess_game(token) if token else None
    if not game or game["status"] != "active":
        return web.json_response({"ok": False})
    await db.set_chess_draw_offer(token, user_id)
    return web.json_response({"ok": True})


@routes.post("/api/game_over")
async def api_game_over(request):
    # فقط تاییدیه سمت کلاینت برای نمایش سریع‌تر مودال؛ وضعیت واقعی
    # از روی حرکت آخر در /api/move محاسبه و ذخیره شده است.
    return web.json_response({"ok": True})


def new_game_token():
    return uuid.uuid4().hex + secrets.token_hex(4)


async def start_game_server():
    app = web.Application()
    app.add_routes(routes)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", WEBAPP_PORT)
    await site.start()
    logger.info(f"Chess mini-app server running on port {WEBAPP_PORT}")
    return runner
