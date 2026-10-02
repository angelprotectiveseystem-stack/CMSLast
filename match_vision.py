"""
خواندنِ نتایجِ مسابقه از «عکسِ برگه» (فقط برای مدیر ارشد، از هاب).

جریان:
  ۱) extract_matches(): عکس + فهرستِ اسمِ بازیکنان → Gemini (بینایی) → فهرستِ ردیف‌ها
     (سفید / سیاه / نتیجه / متنِ خامِ نتیجه).
  ۲) build_review(): اسم‌های خوانده‌شده را با بازیکنانِ واقعی تطبیق می‌دهد و برای هر ردیف
     وضعیت می‌سازد: ok (مطمئن) / ambiguous (چند گزینه) / unknown (پیدا نشد).

هیچ‌چیزی اینجا در دیتابیس نوشته نمی‌شود. ثبتِ نهایی فقط بعد از بازبینیِ مدیر ارشد
(hub_api: /hub/api/match/scan/commit).
"""

import base64
import difflib
import json
import logging
import re

import httpx

logger = logging.getLogger(__name__)

MAX_ROWS = 80
MAX_ROSTER_IN_PROMPT = 400
REQUEST_TIMEOUT = 75          # خواندنِ عکس از متن کندتر است
ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}
RESULTS = ("white", "black", "draw", "unknown")

_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "matches": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "white": {"type": "STRING"},
                    "black": {"type": "STRING"},
                    "result": {"type": "STRING", "enum": list(RESULTS)},
                    "raw_result": {"type": "STRING"},
                    "note": {"type": "STRING"},
                },
                "required": ["white", "black", "result"],
            },
        },
        "date_text": {"type": "STRING"},
        "sheet_note": {"type": "STRING"},
    },
    "required": ["matches"],
}

_PROMPT = """این یک عکس از «برگه‌ی نتایجِ مسابقاتِ شطرنج» در یک مدرسه است (متن ممکن است فارسی، دست‌نویس یا چاپی، و راست‌به‌چپ باشد).

کار: هر بازیِ نوشته‌شده در برگه را به‌صورت یک ردیف استخراج کن.

قواعد:
- «white» = بازیکنِ سفید، «black» = بازیکنِ سیاه. اگر ستون/برچسبِ «سفید/سیاه» هست از همان استفاده کن؛ اگر نیست، اولین اسمِ هر ردیف سفید و دومی سیاه است.
- نتیجه را فقط از روی چیزی که در برگه نوشته شده تعیین کن:
  • "white": سفید برده (مثلاً 1-0، 1:0، «برد سفید»، یا کنارِ اسمِ سفید علامتِ برد/دایره)
  • "black": سیاه برده (0-1، 0:1، «برد سیاه»)
  • "draw": تساوی (½-½، 1/2، «مساوی»، «تساوی»)
  • "unknown": نتیجه خالی، ناخوانا، یا مطمئن نیستی. حدس نزن.
- «raw_result»: همان متنی که برای نتیجه در برگه دیدی (مثلاً "1-0")، عیناً.
- اسم‌ها را «همان‌طور که روی برگه نوشته شده» بنویس. فهرستِ بازیکنانِ زیر فقط کمک است تا دست‌خطِ مبهم را بهتر بخوانی؛ اگر اسمی در فهرست نبود، همان چیزی را که خوانده‌ای بنویس و چیزی از خودت نساز.
- ردیفِ ناقص (فقط یک اسم) را با اسمِ خالی ("") برای طرفِ ناموجود بیاور و در «note» توضیح بده.
- «note»: فقط اگر ردیف مبهم/خط‌خورده/ناخوانا بود، یک جمله‌ی کوتاه. وگرنه خالی.
- «date_text»: اگر تاریخ روی برگه هست عیناً بنویس، وگرنه خالی.
- «sheet_note»: اگر مشکلِ کلی داری (عکس تار، بخشی از برگه بریده‌شده)، کوتاه بنویس. وگرنه خالی.
- ردیف‌های تکراری یا سرستون‌ها را وارد نکن. ترتیبِ برگه را حفظ کن.

خروجی فقط JSON باشد.
"""


# ───────────────────────── نرمال‌سازیِ اسم ─────────────────────────
_AR2FA = str.maketrans({"ي": "ی", "ى": "ی", "ك": "ک", "ۀ": "ه", "ة": "ه", "أ": "ا", "إ": "ا", "ؤ": "و"})
_JUNK = re.compile(r"[\u200c\u200d\u200e\u200f\u0640\u064b-\u065f\u0670]")   # ZWNJ، کشیده، اعراب
_NONWORD = re.compile(r"[^\w\s]", re.UNICODE)


def normalize_name(s: str) -> str:
    s = str(s or "").translate(_AR2FA)
    s = _JUNK.sub("", s)
    s = _NONWORD.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip().lower()


def _score(q: str, cand: str) -> float:
    """شباهتِ دو اسمِ نرمال‌شده، ۰ تا ۱."""
    if not q or not cand:
        return 0.0
    if q == cand:
        return 1.0
    qt, ct = set(q.split()), set(cand.split())
    # همه‌ی کلماتِ یکی داخلِ دیگری (مثلاً «علی رضایی» در برابرِ «علی رضایی نژاد»)
    contain = 0.0
    if qt and ct and (qt <= ct or ct <= qt):
        contain = 0.9 if min(len(qt), len(ct)) >= 2 else 0.72
    ratio = difflib.SequenceMatcher(None, q, cand).ratio()
    # ترتیبِ جابه‌جا («رضایی علی» ↔ «علی رضایی»)
    sorted_ratio = difflib.SequenceMatcher(None, " ".join(sorted(qt)), " ".join(sorted(ct))).ratio()
    return max(contain, ratio, sorted_ratio)


def match_player(name: str, roster: list) -> dict:
    """roster: [{id, name, cls, norm}] → {status, id, name, cands:[{id,name,cls,score}]}"""
    q = normalize_name(name)
    if not q:
        return {"status": "unknown", "id": None, "name": "", "cands": []}
    scored = sorted(((_score(q, r["norm"]), r) for r in roster), key=lambda x: -x[0])
    top = scored[:3]
    cands = [{"id": r["id"], "name": r["name"], "cls": r["cls"], "score": round(s, 2)} for s, r in top if s >= 0.45]
    if not cands:
        return {"status": "unknown", "id": None, "name": "", "cands": []}
    best = cands[0]
    second = cands[1]["score"] if len(cands) > 1 else 0.0
    # دو بازیکنِ هم‌نامِ دقیق → حتماً مبهم (نباید خودکار انتخاب شود)
    twins = sum(1 for _s, r in scored if r["norm"] == q) > 1
    if not twins and best["score"] >= 0.86 and (best["score"] == 1.0 or best["score"] - second >= 0.08):
        return {"status": "ok", "id": best["id"], "name": best["name"], "cands": cands}
    return {"status": "ambiguous", "id": None, "name": "", "cands": cands}


def make_roster(players) -> list:
    return [{"id": p["id"], "name": p["full_name"], "cls": p["class_name"] or "", "norm": normalize_name(p["full_name"])}
            for p in players]


# ───────────────────────── تماس با Gemini ─────────────────────────
def decode_image(data: str, mime: str = ""):
    """data: base64 خام یا data-URL → (bytes, mime). خطای ValueError با پیامِ فارسی."""
    s = str(data or "").strip()
    if s.startswith("data:"):
        head, _, s = s.partition(",")
        m = re.match(r"data:([\w/+.-]+);base64", head)
        if m:
            mime = mime or m.group(1)
    mime = (mime or "image/jpeg").lower()
    if mime == "image/jpg":
        mime = "image/jpeg"
    if mime not in ALLOWED_MIME:
        raise ValueError("فرمتِ عکس پشتیبانی نمی‌شود (JPG، PNG یا WebP).")
    try:
        raw = base64.b64decode(s, validate=False)
    except Exception:
        raise ValueError("عکس نامعتبر است.")
    if len(raw) < 2000:
        raise ValueError("عکس خالی یا بسیار کوچک است.")
    if len(raw) > 6 * 1024 * 1024:
        raise ValueError("حجمِ عکس زیاد است.")
    return raw, mime


def _thinking_for(model: str) -> dict:
    # خواندنِ دست‌خط به کمی «فکر» نیاز دارد (برخلافِ دستیار که minimal است)
    return {"thinkingLevel": "low"} if model.startswith("gemini-3") else {"thinkingBudget": 1024}


def _parse_json(text: str) -> dict:
    t = str(text or "").strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.I).strip()
    try:
        d = json.loads(t)
    except Exception:
        m = re.search(r"\{.*\}", t, re.S)
        if not m:
            raise
        d = json.loads(m.group(0))
    return d if isinstance(d, dict) else {}


class VisionError(Exception):
    """code: no_key | failed — message فارسی و قابل‌نمایش به مدیر."""
    def __init__(self, code, message):
        super().__init__(message)
        self.code, self.message = code, message


async def extract_matches(image_bytes: bytes, mime: str, roster_names: list) -> dict:
    import ai_assistant
    import net_utils
    if not ai_assistant.GEMINI_API_KEY:
        raise VisionError("no_key", "کلید Gemini تنظیم نشده (GEMINI_API_KEY).")

    names = [n for n in roster_names if n][:MAX_ROSTER_IN_PROMPT]
    prompt = _PROMPT + "\nفهرستِ بازیکنانِ ثبت‌شده (فقط برای کمک به خواندن):\n" + "\n".join(names)
    contents = [{"role": "user", "parts": [
        {"inlineData": {"mimeType": mime, "data": base64.b64encode(image_bytes).decode("ascii")}},
        {"text": prompt},
    ]}]
    headers = {"Content-Type": "application/json", "x-goog-api-key": ai_assistant.GEMINI_API_KEY}
    client = net_utils.get_gemini_client()
    last = None
    for model in ai_assistant.MODEL_CHAIN:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        for with_schema in (True, False):
            gen = {"responseMimeType": "application/json", "maxOutputTokens": 8192,
                   "thinkingConfig": _thinking_for(model)}
            if with_schema:
                gen["responseSchema"] = _SCHEMA
            try:
                resp = await client.post(url, headers=headers, timeout=REQUEST_TIMEOUT,
                                         json={"contents": contents, "generationConfig": gen})
                resp.raise_for_status()
                parts = (resp.json().get("candidates") or [{}])[0].get("content", {}).get("parts", [])
                text = "".join(p.get("text", "") for p in parts if isinstance(p, dict))
                data = _parse_json(text)
                if "matches" not in data:
                    raise ValueError("no matches key")
                return data
            except httpx.HTTPStatusError as e:
                last = e
                code = e.response.status_code
                logger.warning("match_vision: %s -> %s (schema=%s)", model, code, with_schema)
                if code == 400 and with_schema:
                    continue            # همین مدل را بدونِ schema امتحان کن
                break                   # مدلِ بعدی
            except (httpx.TimeoutException, httpx.TransportError) as e:
                last = e
                logger.warning("match_vision: %s transport/timeout: %r", model, e)
                break
            except Exception as e:      # JSON خراب، ساختارِ غیرمنتظره
                last = e
                logger.warning("match_vision: %s bad output: %r", model, e)
                break
    raise VisionError("failed", "خواندنِ عکس انجام نشد؛ چند لحظه بعد دوباره امتحان کنید یا عکسِ واضح‌تری بفرستید.")


# ───────────────────────── ساختنِ خروجیِ بازبینی ─────────────────────────
def build_review(data: dict, roster: list) -> dict:
    items = []
    for i, r in enumerate((data.get("matches") or [])[:MAX_ROWS]):
        if not isinstance(r, dict):
            continue
        res = r.get("result") if r.get("result") in RESULTS else "unknown"
        w, b = match_player(r.get("white"), roster), match_player(r.get("black"), roster)
        issues = []
        if w["status"] != "ok":
            issues.append("white")
        if b["status"] != "ok":
            issues.append("black")
        if res == "unknown":
            issues.append("result")
        if w["id"] and w["id"] == b["id"]:
            issues.append("same")
        items.append({
            "i": i,
            "w_raw": str(r.get("white") or "")[:60], "b_raw": str(r.get("black") or "")[:60],
            "res": res, "raw_result": str(r.get("raw_result") or "")[:20], "note": str(r.get("note") or "")[:160],
            "w": w, "b": b, "issues": issues,
        })
    return {"items": items, "date_text": str(data.get("date_text") or "")[:40],
            "sheet_note": str(data.get("sheet_note") or "")[:200]}
