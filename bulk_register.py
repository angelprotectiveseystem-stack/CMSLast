import re
from telegram.ext import ConversationHandler
import database as db
import keyboards as kb
from helpers import box
from config import (
    ST_BULK_REG_TEXT, ST_BULK_REG_PREVIEW,
    ST_BULK_REG_EDIT_NUM, ST_BULK_REG_EDIT_VALUE
)


def parse_bulk_line(line, classes_by_name):
    line = line.strip()
    if not line:
        return None
    if "/" not in line:
        return {"raw": line, "name": None, "class_name": None,
                "class_id": None, "error": "فرمت نامعتبر (بدون /)"}
    name_part, class_part = line.split("/", 1)
    name = name_part.strip()
    m = re.search(r"\d+", class_part)
    class_name = m.group() if m else None
    class_id = classes_by_name.get(class_name) if class_name else None
    error = None
    if not name:
        error = "نام خالی است"
    elif not class_name:
        error = "کلاس مشخص نیست"
    elif not class_id:
        error = f"کلاس «{class_name}» ثبت نشده"
    return {"raw": line, "name": name, "class_name": class_name,
            "class_id": class_id, "error": error}


def render_preview(items):
    lines = [box("📋 پیش‌نمایش ثبت‌نام گروهی"), ""]
    ok_count = 0
    err_count = 0
    for i, it in enumerate(items, start=1):
        if it["error"]:
            lines.append(f"⚠️ {i}. {it['raw']} — {it['error']}")
            err_count += 1
        else:
            lines.append(f"{i}. {it['name']} — کلاس {it['class_name']}")
            ok_count += 1
    lines.append("")
    lines.append(f"✅ آماده ثبت: {ok_count} | ⚠️ مشکل‌دار: {err_count}")
    return "\n".join(lines)


async def bulk_register_start(update, ctx):
    query = update.callback_query
    await query.answer()
    ctx.user_data.pop("bulk_items", None)
    await query.edit_message_text(
        f"{box('📋 ثبت‌نام گروهی')}\n\n"
        "لیست دانش‌آموزها را با رعایت ساختار و شکل توضیح داده شده ارسال نمایید:\n\n"
        "`نام کامل/کلاس`\n\n"
        "مثال:\n`محمد خانی/۹۰۱`\n`عرشیا نجفی/۷۰۲`",
        parse_mode="Markdown"
    )
    return ST_BULK_REG_TEXT


async def bulk_register_text_received(update, ctx):
    text = update.message.text
    classes = await db.get_all_classes()
    classes_by_name = {c["name"]: c["id"] for c in classes}
    lines = [l for l in text.split("\n") if l.strip()]
    items = []
    for line in lines:
        parsed = parse_bulk_line(line, classes_by_name)
        if parsed:
            items.append(parsed)
    if not items:
        await update.message.reply_text("❗ چیزی شناسایی نشد. دوباره لیست رو بفرست:")
        return ST_BULK_REG_TEXT
    ctx.user_data["bulk_items"] = items
    await update.message.reply_text(
        render_preview(items), reply_markup=kb.kb_bulk_preview(), parse_mode="Markdown"
    )
    return ST_BULK_REG_PREVIEW


async def bulk_confirm(update, ctx):
    query = update.callback_query
    await query.answer()
    items = ctx.user_data.get("bulk_items", [])
    ok_items = [it for it in items if not it["error"]]
    count = 0
    for it in ok_items:
        pid = await db.create_player(it["name"], it["class_id"])
        await db.log_action(query.from_user.id, "bulk_create_player", f"ثبت گروهی: {it['name']}", pid)
        count += 1
    ctx.user_data.pop("bulk_items", None)
    await query.edit_message_text(
        f"✅ {count} بازیکن با موفقیت ثبت شد.",
        reply_markup=kb.kb_players_menu("pishva")
    )
    return ConversationHandler.END


async def bulk_cancel(update, ctx):
    query = update.callback_query
    await query.answer()
    ctx.user_data.pop("bulk_items", None)
    await query.edit_message_text(
        "❌ ثبت‌نام گروهی لغو شد.",
        reply_markup=kb.kb_players_menu("pishva")
    )
    return ConversationHandler.END


async def bulk_edit_start(update, ctx):
    query = update.callback_query
    await query.answer()
    items = ctx.user_data.get("bulk_items", [])
    await query.edit_message_text(
        f"✏️ شماره‌ی خطی که می‌خواهید اصلاح کنید را بنویسید (عددی بین ۱ تا {len(items)}):"
    )
    return ST_BULK_REG_EDIT_NUM


async def bulk_edit_num_received(update, ctx):
    text = update.message.text.strip()
    items = ctx.user_data.get("bulk_items", [])
    if not text.isdigit() or not (1 <= int(text) <= len(items)):
        await update.message.reply_text(f"❌ عدد نامعتبره. یه عدد بین ۱ تا {len(items)} بفرست:")
        return ST_BULK_REG_EDIT_NUM
    idx = int(text) - 1
    ctx.user_data["bulk_edit_idx"] = idx
    current = items[idx]["raw"]
    await update.message.reply_text(
        f"خط {text} الان اینه:\n`{current}`\n\nخط درست رو بفرست (مثلاً: نام کامل/۹۰۱):",
        parse_mode="Markdown"
    )
    return ST_BULK_REG_EDIT_VALUE


async def bulk_edit_value_received(update, ctx):
    new_line = update.message.text.strip()
    idx = ctx.user_data.get("bulk_edit_idx")
    items = ctx.user_data.get("bulk_items", [])
    if idx is None or idx >= len(items):
        await update.message.reply_text("❌ خطا. دوباره از منوی بازیکنان شروع کن.")
        return ConversationHandler.END
    classes = await db.get_all_classes()
    classes_by_name = {c["name"]: c["id"] for c in classes}
    items[idx] = parse_bulk_line(new_line, classes_by_name)
    ctx.user_data["bulk_items"] = items
    await update.message.reply_text(
        render_preview(items), reply_markup=kb.kb_bulk_preview(), parse_mode="Markdown"
    )
    return ST_BULK_REG_PREVIEW
