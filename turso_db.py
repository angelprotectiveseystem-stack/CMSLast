"""
لایه سازگاری بین کد فعلی (که با سینتکس aiosqlite نوشته شده) و Turso.
هدف: بدون تغییر دادن منطق فایل database.py، فقط دیتابیس زیرینش عوض بشه.

فقط کافیه در بالای database.py این خط عوض بشه:
    import aiosqlite   ->   import turso_db as aiosqlite

بقیه کد (aiosqlite.connect, db.execute, db.row_factory, cur.fetchall و ...)
دقیقاً همون‌طور که هست کار می‌کنه.
"""

import os
from libsql_client import create_client

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
        # به جای پروتکل وب‌سوکت (libsql:// / wss://) از HTTP ساده استفاده می‌کنیم،
        # چون بعضی هاست‌ها مثل Railway با هندشیک وب‌سوکت به Turso مشکل دارن.
        if url.startswith("libsql://"):
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
            if self._params is None:
                result = await client.execute(self._query)
            else:
                result = await client.execute(self._query, list(self._params))
            self._cursor = _Cursor(result)
        return self._cursor

    def __await__(self):
        return self._run().__await__()

    async def __aenter__(self):
        return await self._run()

    async def __aexit__(self, *exc):
        return False


class _Connection:
    def __init__(self):
        self.row_factory = None  # نادیده گرفته میشه، همیشه فعاله

    def execute(self, query, params=None):
        return _ExecuteAwaitable(query, params)

    async def executescript(self, script):
        client = _get_client()
        for stmt in _split_sql_script(script):
            await client.execute(stmt)

    async def commit(self):
        # Turso هر دستور رو فوری ثبت می‌کنه، نیازی به commit جدا نیست
        pass

    async def close(self):
        pass


class _ConnectCM:
    async def __aenter__(self):
        return _Connection()

    async def __aexit__(self, *exc):
        return False


def connect(path=None):
    """امضای تابع مثل aiosqlite.connect(DB_PATH) هست ولی آرگومانش
    نادیده گرفته میشه چون آدرس دیتابیس از TURSO_URL خونده میشه."""
    return _ConnectCM()
