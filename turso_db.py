"""
لایه سازگاری بین کد فعلی (که با سینتکس aiosqlite نوشته شده) و Turso.
هدف: بدون تغییر دادن منطق فایل database.py، فقط دیتابیس زیرینش عوض بشه.

فقط کافیه در بالای database.py این خط عوض بشه:
    import aiosqlite   ->   import turso_db as aiosqlite

بقیه کد (aiosqlite.connect, db.execute, db.row_factory, cur.fetchall و ...)
دقیقاً همون‌طور که هست کار می‌کنه.
"""

import logging
import os
from libsql_client import create_client

logger = logging.getLogger("turso_db")

_client = None


def _get_client():
    global _client
    if _client is None:
        url = os.getenv("TURSO_URL")
        token = os.getenv("TURSO_AUTH_TOKEN")
        if not url or not token:
            raise RuntimeError(
                "متغیرهای TURSO_URL و TURSO_AUTH_TOKEN تنظیم نشدن. "
                "این‌ها باید در Railway -> Variables اضافه شده باشن."
            )
        # با وب‌سوکت (libsql://) یک اتصال باز باقی می‌مونه و همه کوئری‌ها روش رد می‌شن
        # که خیلی سریع‌تر از HTTP هست (هر کوئری با HTTP یعنی یک هندشیک TLS جدید).
        # می‌تونی با متغیر محیطی TURSO_FORCE_HTTP=1 به حالت قبلی (HTTP) برگردی
        # اگه هاست مشکل هندشیک وب‌سوکت داشت.
        if os.getenv("TURSO_FORCE_HTTP") == "1" and url.startswith("libsql://"):
            url = "https://" + url[len("libsql://"):]
        _client = create_client(url=url, auth_token=token)
    return _client


class Row:
    """فقط برای سازگاری با aiosqlite.Row - این کلاس عملاً استفاده نمیشه،
    چون ردیف‌ها همیشه هم با ایندکس و هم با اسم ستون قابل دسترسی هستن."""
    pass


class _ResultRow:
    def __init__(self, columns, values):
        self._columns = list(columns)
        self._values = list(values)

    def __getitem__(self, key):
        if isinstance(key, str):
            return self._values[self._columns.index(key)]
        return self._values[key]

    def get(self, key, default=None):
        """سازگاری با کدی که ردیف رو مثل دیکشنری صدا می‌زنه (admin.get(...) و مشابه).
        sqlite3.Row/aiosqlite.Row هم این متد رو ندارن، ولی چون کد پروژه جاهای زیادی
        فرض کرده ردیف‌ها دیکشنری‌ان، این‌جا اضافه‌ش می‌کنیم تا دیگه با
        AttributeError کرش نکنه."""
        try:
            return self[key]
        except (ValueError, IndexError):
            return default

    def keys(self):
        return self._columns

    def __contains__(self, key):
        return key in self._columns

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)

    def __repr__(self):
        return f"Row({dict(zip(self._columns, self._values))})"


class _Cursor:
    def __init__(self, result):
        self._rows = (
            [_ResultRow(result.columns, row) for row in result.rows]
            if result.rows else []
        )
        self._i = 0
        self.lastrowid = getattr(result, "last_insert_rowid", None)

    async def fetchone(self):
        if self._i < len(self._rows):
            row = self._rows[self._i]
            self._i += 1
            return row
        return None

    async def fetchall(self):
        rows = self._rows[self._i:]
        self._i = len(self._rows)
        return rows

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


def _split_sql_script(script: str):
    return [s.strip() for s in script.split(";") if s.strip()]


class _ExecuteAwaitable:
    """می‌تونه هم await بشه (await db.execute(...))
    هم به‌عنوان async context manager استفاده بشه (async with db.execute(...) as cur:)
    - دقیقاً مثل رفتار cursor در aiosqlite."""

    def __init__(self, query, params):
        self._query = query
        self._params = params
        self._cursor = None

    async def _run(self):
        if self._cursor is None:
            client = _get_client()
            try:
                if self._params is None:
                    result = await client.execute(self._query)
                else:
                    result = await client.execute(self._query, list(self._params))
            except Exception as exc:
                # کتابخانه‌ی libsql_client وقتی Turso یک خطای SQL برمی‌گردونه
                # (مثلاً "no such column"، "UNIQUE constraint failed"، تعداد
                # پارامترهای اشتباه و ...) به‌جای خطای واضح، یک KeyError('result')
                # خام پرت می‌کنه که دلیل واقعی رو مخفی می‌کنه. این‌جا کوئری و
                # پارامترها رو لاگ می‌کنیم تا خطای واقعی توی لاگ‌ها معلوم بشه،
                # بعد یک خطای خواناتر بالا می‌بریم.
                logger.error(
                    "Turso query failed | query=%r | params=%r | error=%r",
                    self._query, self._params, exc,
                )
                raise RuntimeError(
                    f"Turso query failed: {exc!r}\n"
                    f"query={self._query!r}\n"
                    f"params={self._params!r}"
                ) from exc
            self._cursor = _Cursor(result)
        return self._cursor

    def __await__(self):
        return self._run().__await__()

    async def __aenter__(self):
        return await self._run()

    async def __aexit__(self, *exc):
        return False


class _NoopAwaitable:
    """داخل یک batch برگردونده می‌شه چون کوئری واقعی هنوز اجرا نشده
    (تا پایان بلاک batch صف می‌مونه). await کردنش فقط یک cursor خالی می‌ده."""

    async def _run(self):
        return _Cursor(type("R", (), {"columns": [], "rows": [], "last_insert_rowid": None})())

    def __await__(self):
        return self._run().__await__()

    async def __aenter__(self):
        return await self._run()

    async def __aexit__(self, *exc):
        return False


class _Connection:
    def __init__(self):
        self.row_factory = None  # نادیده گرفته میشه، همیشه فعاله
        self._batch_stmts = None  # وقتی None نیست یعنی داخل یک batch هستیم

    def execute(self, query, params=None):
        if self._batch_stmts is not None:
            # داخل یک batch: به‌جای رفتن به شبکه، فقط صف می‌کنیم.
            # نتیجه‌ای برای برگردوندن نیست (batch فقط برای نوشتن‌هاست).
            self._batch_stmts.append((query, params))
            return _NoopAwaitable()
        return _ExecuteAwaitable(query, params)

    def batch(self):
        """استفاده: async with conn.batch(): چند تا execute پشت‌سرهم.
        همه‌ی کوئری‌ها با یک درخواست شبکه (نه یکی‌یکی) اجرا می‌شن.
        نکته: نتیجه‌ی هر execute داخل بلاک batch در دسترس نیست، چون
        همه با هم در انتهای بلاک اجرا می‌شن. برای کوئری‌هایی که فقط
        نوشتن هستن (insert/update/delete) استفاده کن، نه select."""
        return _BatchCM(self)

    async def executescript(self, script):
        client = _get_client()
        for stmt in _split_sql_script(script):
            try:
                await client.execute(stmt)
            except Exception as exc:
                logger.error("Turso executescript failed | stmt=%r | error=%r", stmt, exc)
                raise RuntimeError(f"Turso executescript failed: {exc!r}\nstmt={stmt!r}") from exc

    async def commit(self):
        # Turso هر دستور رو فوری ثبت می‌کنه، نیازی به commit جدا نیست
        pass

    async def close(self):
        pass


class _BatchCM:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        self._conn._batch_stmts = []
        return self._conn

    async def __aexit__(self, exc_type, exc, tb):
        stmts = self._conn._batch_stmts
        self._conn._batch_stmts = None
        if exc_type is not None or not stmts:
            return False  # خطا شد یا چیزی صف نشده، چیزی رو اجرا نکن
        client = _get_client()
        import libsql_client
        batch_items = [
            libsql_client.Statement(q, list(p) if p is not None else [])
            for q, p in stmts
        ]
        try:
            await client.batch(batch_items)
        except Exception as exc:
            logger.error("Turso batch failed | stmts=%r | error=%r", stmts, exc)
            raise RuntimeError(f"Turso batch failed: {exc!r}\nstmts={stmts!r}") from exc
        return False


class _ConnectCM:
    async def __aenter__(self):
        return _Connection()

    async def __aexit__(self, *exc):
        return False


def connect(path=None):
    """امضای تابع مثل aiosqlite.connect(DB_PATH) هست ولی آرگومانش
    نادیده گرفته میشه چون آدرس دیتابیس از TURSO_URL خونده میشه."""
    return _ConnectCM()
