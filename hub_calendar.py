"""
hub_calendar.py — تقویم و تعطیلی‌های رسمیِ ۳ سالِ پیشِ رو برای «پنل من».

بدونِ هیچ وابستگیِ بیرونی (jdatetime لازم نیست) تا هم تست‌پذیر باشه هم روی
هر محیطی بالا بیاد:
  • تبدیلِ شمسی ⇄ میلادی (الگوریتمِ jalaali، بدونِ جدولِ سال‌به‌سال)
  • تبدیلِ قمری (هجریِ جدولی / civil) ⇄ میلادی
  • تعطیلیِ رسمیِ ثابتِ شمسی (نوروز، ۱۲ فروردین، ۱۴ و ۱۵ خرداد، ۲۲ بهمن، ۲۹ اسفند)
  • تعطیلیِ مناسبت‌های قمری (تاسوعا، عاشورا، اربعین، ... غدیر)

⚠️ نکته‌ی مهمِ صداقت: تعطیلیِ قمری در ایران بر اساسِ رؤیتِ هلال اعلام می‌شه و
ممکنه با محاسبه‌ی جدولی تا ±۱ روز فرق کنه. برای همین یک «تنظیمِ تصحیح» (hijri_offset،
از ۲- تا ۲+ روز) هست که مدیر ارشد از پنل می‌تونه عوضش کنه، و هر روز رو هم می‌شه
دستی (از جدول calendar_days) به‌عنوان تعطیل/رویداد ثبت یا لغو کرد.
"""

from datetime import date, timedelta
import math

PERSIAN_MONTHS = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
                  "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]
# شنبه=۰ ... جمعه=۶
PERSIAN_WEEKDAYS = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه"]
_PY_TO_FA = {5: 0, 6: 1, 0: 2, 1: 3, 2: 4, 3: 5, 4: 6}

_BREAKS = [-61, 9, 38, 199, 426, 686, 756, 818, 1111, 1181, 1210, 1635, 2060,
           2097, 2192, 2262, 2324, 2394, 2456, 3178]


def _jal_cal(jy):
    gy = jy + 621
    leap_j = -14
    jp = _BREAKS[0]
    jump = 0
    for i in range(1, len(_BREAKS)):
        jm = _BREAKS[i]
        jump = jm - jp
        if jy < jm:
            break
        leap_j += (jump // 33) * 8 + (jump % 33) // 4
        jp = jm
    n = jy - jp
    leap_j += (n // 33) * 8 + ((n % 33) + 3) // 4
    if jump % 33 == 4 and jump - n == 4:
        leap_j += 1
    leap_g = gy // 4 - ((gy // 100 + 1) * 3) // 4 - 150
    march = 20 + leap_j - leap_g
    if jump - n < 6:
        n = n - jump + ((jump + 4) // 33) * 33
    leap = (((n + 1) % 33) - 1) % 4
    if leap == -1:
        leap = 4
    return leap, gy, march


def is_jalali_leap(jy):
    return _jal_cal(jy)[0] == 0


def jalali_month_length(jy, jm):
    if jm <= 6:
        return 31
    if jm <= 11:
        return 30
    return 30 if is_jalali_leap(jy) else 29


def jalali_to_date(jy, jm, jd):
    _, gy, march = _jal_cal(jy)
    base = date(gy, 3, march).toordinal()
    return date.fromordinal(base + (jm - 1) * 31 - (jm // 7) * (jm - 7) + jd - 1)


def date_to_jalali(g):
    gy = g.year
    jy = gy - 621
    leap, _, march = _jal_cal(jy)
    jdn1f = date(gy, 3, march).toordinal()
    k = g.toordinal() - jdn1f
    if k >= 0:
        if k <= 185:
            return jy, 1 + k // 31, k % 31 + 1
        k -= 186
    else:
        jy -= 1
        k += 179
        if leap == 1:
            k += 1
    return jy, 7 + k // 30, k % 30 + 1


def weekday_fa(g):
    """اندیس روز هفته‌ی فارسی: شنبه=۰ ... جمعه=۶."""
    return _PY_TO_FA[g.weekday()]


def jstr(jy, jm, jd):
    return f"{jy:04d}/{jm:02d}/{jd:02d}"


# ─── قمری (هجریِ جدولی) ──────────────────────────────────────────
_ISLAMIC_EPOCH = 1948439.5  # 1 Muharram 1 AH (civil)


def _islamic_to_jd(y, m, d):
    return d + math.ceil(29.5 * (m - 1)) + (y - 1) * 354 + math.floor((3 + 11 * y) / 30) + _ISLAMIC_EPOCH - 1


def _jd_to_islamic(jd):
    jd = math.floor(jd) + 0.5
    y = math.floor((30 * (jd - _ISLAMIC_EPOCH) + 10646) / 10631)
    m = min(12, math.ceil((jd - (29 + _islamic_to_jd(y, 1, 1))) / 29.5) + 1)
    d = int(jd - _islamic_to_jd(y, m, 1)) + 1
    return y, m, d


def _date_to_jd(g):
    return g.toordinal() + 1721424.5


def date_to_hijri(g, offset=0):
    """(سال, ماه, روز)ِ قمری برای یک تاریخ میلادی؛ offset روزِ تصحیح (رؤیتِ هلال)."""
    return _jd_to_islamic(_date_to_jd(g + timedelta(days=offset)))


def _hijri_month_length(y, m):
    return int(_islamic_to_jd(y + (m // 12), (m % 12) + 1, 1) - _islamic_to_jd(y, m, 1))


# ─── تعطیلی‌های رسمی ────────────────────────────────────────────
_SOLAR_HOLIDAYS = {
    (1, 1): "آغاز نوروز",
    (1, 2): "تعطیلی نوروز",
    (1, 3): "تعطیلی نوروز",
    (1, 4): "تعطیلی نوروز",
    (1, 12): "روز جمهوری اسلامی",
    (1, 13): "روز طبیعت (سیزده‌بدر)",
    (3, 14): "رحلت امام خمینی",
    (3, 15): "قیام ۱۵ خرداد",
    (11, 22): "پیروزی انقلاب اسلامی",
    (12, 29): "ملی شدن صنعت نفت",
}

# (ماهِ قمری, روز) → عنوان. روز = 0 یعنی «آخرین روزِ ماه».
_LUNAR_HOLIDAYS = {
    (1, 9): "تاسوعای حسینی",
    (1, 10): "عاشورای حسینی",
    (2, 20): "اربعین حسینی",
    (2, 28): "رحلت پیامبر و شهادت امام حسن (ع)",
    (2, 0): "شهادت امام رضا (ع)",
    (3, 17): "میلاد پیامبر (ص) و امام صادق (ع)",
    (6, 3): "شهادت حضرت فاطمه (س)",
    (7, 13): "ولادت امام علی (ع) و روز پدر",
    (7, 27): "مبعث پیامبر (ص)",
    (8, 15): "ولادت امام زمان (عج)",
    (9, 21): "شهادت امام علی (ع)",
    (10, 1): "عید سعید فطر",
    (10, 2): "تعطیلی عید فطر",
    (10, 25): "شهادت امام صادق (ع)",
    (12, 10): "عید سعید قربان",
    (12, 18): "عید سعید غدیر خم",
}


def official_holidays(start, end, hijri_offset=0):
    """{date: [عنوان, ...]} برای بازه‌ی [start, end] (شاملِ هر دو سر)."""
    out = {}
    d = start
    while d <= end:
        titles = []
        jy, jm, jd = date_to_jalali(d)
        t = _SOLAR_HOLIDAYS.get((jm, jd))
        if t:
            titles.append(t)
        hy, hm, hd = date_to_hijri(d, hijri_offset)
        t = _LUNAR_HOLIDAYS.get((hm, hd))
        if t is None and (hm, 0) in _LUNAR_HOLIDAYS and hd == _hijri_month_length(hy, hm):
            t = _LUNAR_HOLIDAYS[(hm, 0)]
        if t:
            titles.append(t)
        if titles:
            out[d] = titles
        d += timedelta(days=1)
    return out


def month_grid(jy, jm, hijri_offset=0):
    """ساختارِ یک ماهِ شمسی: طول، محلِ روزِ اول در هفته، و برای هر روز
    (تاریخ میلادی، جمعه‌بودن، تعطیلی‌های رسمی)."""
    n = jalali_month_length(jy, jm)
    first = jalali_to_date(jy, jm, 1)
    last = jalali_to_date(jy, jm, n)
    hol = official_holidays(first, last, hijri_offset)
    days = []
    for i in range(1, n + 1):
        g = jalali_to_date(jy, jm, i)
        wd = weekday_fa(g)
        days.append({
            "d": i, "g": g.isoformat(), "wd": wd,
            "weekend": wd == 6,
            "official": hol.get(g, []),
        })
    return {"year": jy, "month": jm, "month_name": PERSIAN_MONTHS[jm - 1],
            "length": n, "first_wd": weekday_fa(first), "days": days}


def upcoming_holidays(today, years=3, hijri_offset=0):
    """همه‌ی تعطیلی‌های رسمیِ (غیرِ جمعه) از امروز تا ۳ سال بعد + جمعه‌ها جدا شمرده نمی‌شن."""
    end = date(today.year + years, today.month, min(today.day, 28)) + timedelta(days=(today.day - min(today.day, 28)))
    hol = official_holidays(today, end, hijri_offset)
    items = []
    for g in sorted(hol):
        jy, jm, jd = date_to_jalali(g)
        wd = weekday_fa(g)
        items.append({
            "j": jstr(jy, jm, jd), "g": g.isoformat(),
            "jy": jy, "jm": jm, "jd": jd,
            "month_name": PERSIAN_MONTHS[jm - 1],
            "wd": wd, "wd_name": PERSIAN_WEEKDAYS[wd],
            "titles": hol[g], "on_friday": wd == 6,
        })
    return items
