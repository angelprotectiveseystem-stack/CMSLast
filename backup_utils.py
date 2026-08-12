import io
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from datetime import datetime, timedelta
import database as db
from helpers import now_shamsi


async def gather_backup_data(period: str) -> dict:
    now = datetime.now()
    if period == "today":
        since = now.strftime("%Y-%m-%d")
    elif period == "week":
        since = (now - timedelta(days=7)).isoformat()
    elif period == "month":
        since = (now - timedelta(days=30)).isoformat()
    else:
        since = None

    players = await db.get_all_players()
    matches = await db.get_matches_by_filter(period if period != "all" else "all")
    tournaments = await db.get_all_tournaments()
    teams = await db.get_all_teams()

    return {
        "players": players,
        "matches": matches,
        "tournaments": tournaments,
        "teams": teams,
        "generated_at": now_shamsi(),
        "period": period,
    }


async def generate_excel_backup(period: str) -> io.BytesIO:
    data = await gather_backup_data(period)
    wb = openpyxl.Workbook()

    header_font = Font(bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill("solid", fgColor="1F3864")
    center = Alignment(horizontal="center", vertical="center")
    thin = Side(style="thin", color="AAAAAA")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    def style_header(ws, headers):
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = center
            cell.border = border

    def style_row(ws, row_num, values):
        fill = PatternFill("solid", fgColor="EBF1FF") if row_num % 2 == 0 else PatternFill("solid", fgColor="FFFFFF")
        for col, v in enumerate(values, 1):
            cell = ws.cell(row=row_num, column=col, value=v)
            cell.fill = fill
            cell.border = border
            cell.alignment = Alignment(horizontal="right", vertical="center")

    # Sheet 1: Players
    ws1 = wb.active
    ws1.title = "بازیکنان"
    ws1.sheet_view.rightToLeft = True
    headers = ["ردیف", "نام کامل", "کلاس", "وضعیت", "برد", "مساوی", "باخت", "اخطار", "تاریخ ثبت"]
    style_header(ws1, headers)
    for i, p in enumerate(data["players"], 1):
        style_row(ws1, i + 1, [
            i, p["full_name"], (p['class_name'] or ''),
            p["status"], p["wins"], p["draws"], p["losses"], p["warnings"],
            str(p["created_at"] or "")[:10]
        ])
    for col in ws1.columns:
        ws1.column_dimensions[col[0].column_letter].width = 16

    # Sheet 2: Matches
    ws2 = wb.create_sheet("مسابقات")
    ws2.sheet_view.rightToLeft = True
    headers2 = ["ردیف", "بازیکن سفید", "بازیکن سیاه", "نتیجه", "علت تساوی", "تاریخ", "تورنمنت"]
    style_header(ws2, headers2)
    result_map = {"white": "برد سفید", "black": "برد سیاه", "draw": "تساوی", None: "بدون نتیجه"}
    for i, m in enumerate(data["matches"], 1):
        style_row(ws2, i + 1, [
            i, m["white_name"], m["black_name"],
            result_map.get(m["result"], str(m["result"])),
            m.get("draw_reason", "") or "",
            str(m["match_date"] or ""),
            str(m.get("tournament_id", "") or ""),
        ])
    for col in ws2.columns:
        ws2.column_dimensions[col[0].column_letter].width = 18

    # Sheet 3: Tournaments
    ws3 = wb.create_sheet("تورنمنت‌ها")
    ws3.sheet_view.rightToLeft = True
    headers3 = ["ردیف", "نام", "وضعیت", "پیش‌فرض", "تاریخ ایجاد"]
    style_header(ws3, headers3)
    for i, t in enumerate(data["tournaments"], 1):
        style_row(ws3, i + 1, [
            i, t["name"], t["status"],
            "بله" if t["is_default"] else "خیر",
            str(t["created_at"] or "")[:10]
        ])

    # Info Sheet
    ws4 = wb.create_sheet("اطلاعات بکاپ")
    ws4.sheet_view.rightToLeft = True
    ws4["A1"] = "🏆 سیستم فرماندهی شطرنج"
    ws4["A1"].font = Font(bold=True, size=14)
    ws4["A2"] = f"تاریخ تهیه بکاپ: {data['generated_at']}"
    ws4["A3"] = f"بازه زمانی: {data['period']}"
    ws4["A4"] = f"تعداد بازیکنان: {len(data['players'])}"
    ws4["A5"] = f"تعداد مسابقات: {len(data['matches'])}"
    ws4["A6"] = f"تعداد تورنمنت‌ها: {len(data['tournaments'])}"

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


async def generate_word_backup(period: str) -> io.BytesIO:
    data = await gather_backup_data(period)
    doc = Document()

    # Title
    title = doc.add_heading("🏆 سیستم فرماندهی شطرنج — گزارش بکاپ", 0)
    title.alignment = 1  # center
    doc.add_paragraph(f"📅 تاریخ تهیه: {data['generated_at']}")
    doc.add_paragraph(f"📊 بازه زمانی: {data['period']}")
    doc.add_paragraph("─" * 60)

    # Players
    doc.add_heading("👤 بازیکنان", level=1)
    if data["players"]:
        table = doc.add_table(rows=1, cols=7)
        table.style = "Table Grid"
        hdr = table.rows[0].cells
        for i, h in enumerate(["نام", "کلاس", "وضعیت", "برد", "مساوی", "باخت", "اخطار"]):
            hdr[i].text = h
            hdr[i].paragraphs[0].runs[0].font.bold = True
        for p in data["players"]:
            row = table.add_row().cells
            row[0].text = p["full_name"]
            row[1].text = (p['class_name'] or '')
            row[2].text = p["status"]
            row[3].text = str(p["wins"])
            row[4].text = str(p["draws"])
            row[5].text = str(p["losses"])
            row[6].text = str(p["warnings"])

    doc.add_paragraph()

    # Matches
    doc.add_heading("♟️ مسابقات", level=1)
    if data["matches"]:
        table2 = doc.add_table(rows=1, cols=5)
        table2.style = "Table Grid"
        hdr2 = table2.rows[0].cells
        for i, h in enumerate(["سفید", "سیاه", "نتیجه", "علت تساوی", "تاریخ"]):
            hdr2[i].text = h
            hdr2[i].paragraphs[0].runs[0].font.bold = True
        result_map = {"white": "برد سفید", "black": "برد سیاه", "draw": "تساوی", None: "—"}
        for m in data["matches"]:
            row = table2.add_row().cells
            row[0].text = m["white_name"] or ""
            row[1].text = m["black_name"] or ""
            row[2].text = result_map.get(m["result"], str(m["result"] or ""))
            row[3].text = m.get("draw_reason", "") or ""
            row[4].text = str(m["match_date"] or "")

    doc.add_paragraph()

    # Tournaments
    doc.add_heading("🏅 تورنمنت‌ها", level=1)
    for t in data["tournaments"]:
        doc.add_paragraph(
            f"• {t['name']} | وضعیت: {t['status']} | {'پیش‌فرض ✅' if t['is_default'] else ''}"
        )

    doc.add_paragraph("─" * 60)
    doc.add_paragraph(f"تعداد کل بازیکنان: {len(data['players'])}")
    doc.add_paragraph(f"تعداد کل مسابقات: {len(data['matches'])}")

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf
