import os

# ─── Bot Token ───────────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

# ─── Bot Identity ──────────────────────────────────────────────
BOT_USERNAME = os.environ.get("BOT_USERNAME", "")

# ─── Pishva (Supreme Admin) ───────────────────────────────────
PISHVA_ID = int(os.environ.get("PISHVA_ID", "8355972109"))
PISHVA_USERNAME = os.environ.get("PISHVA_USERNAME", "@apex_aryan_forge")
PISHVA_PASSWORD = os.environ.get("PISHVA_PASSWORD", "ss99ss89sa")
NEW_YEAR_PASSWORD = os.environ.get("NEW_YEAR_PASSWORD", "998989")

# ─── Database ─────────────────────────────────────────────────
DB_PATH = os.environ.get("DB_PATH", "chess_bot.db")

# ─── System Status Codes ──────────────────────────────────────
STATUS_NORMAL = "normal"
STATUS_BAD = "bad"
STATUS_DANGER = "danger"
STATUS_APS = "aps"

# ─── Roles ───────────────────────────────────────────────────
ROLE_PISHVA = "pishva"
ROLE_TOURNAMENT_MANAGER = "tournament_manager"
ROLE_SECURITY_MANAGER = "security_manager"

# ─── Warning Limits ───────────────────────────────────────────
PLAYER_MAX_WARNINGS = 3
ADMIN_MAX_WARNINGS = 5

# ─── Progress Bar Config ──────────────────────────────────────
BAR_LENGTH = 15

# ─── Conversation States ─────────────────────────────────────
(
    ST_ROLE_SELECT,
    ST_PISHVA_PASSWORD,
    ST_ADMIN_USERNAME,
    ST_ADMIN_FULLNAME,
    ST_ADMIN_ROLE_SELECT,
    ST_ADMIN_MESSAGE,
    ST_CLASS_NAME,
    ST_PLAYER_CLASS_SELECT,
    ST_PLAYER_NAME,
    ST_TOURNAMENT_NAME,
    ST_TOURNAMENT_SELECT,
    ST_TOURNAMENT_EDIT,
    ST_TOURNAMENT_DEFAULT,
    ST_MATCH_WHITE,
    ST_MATCH_BLACK,
    ST_MATCH_DATE,
    ST_MATCH_RESULT,
    ST_MATCH_DRAW_REASON,
    ST_MATCH_CANCEL_REASON,
    ST_MATCH_ELIMINATE,
    ST_WARNING_REASON,
    ST_NOTE_TEXT,
    ST_EDIT_PLAYER_NAME,
    ST_EDIT_PLAYER_CLASS,
    ST_SEARCH_PLAYER,
    ST_SEARCH_MATCH,
    ST_SEND_MSG_SELECT_ADMIN,
    ST_SEND_MSG_TEXT,
    ST_ANNOUNCEMENT_TEXT,
    ST_ANNOUNCEMENT_FILE,
    ST_NEWS_TEXT,
    ST_TASK_SELECT_ADMIN,
    ST_TASK_TITLE,
    ST_TASK_DESC,
    ST_TASK_DONE_REASON,
    ST_FEEDBACK_TEXT,
    ST_SUGGESTION_TEXT,
    ST_FEATURE_TITLE,
    ST_FEATURE_DESC,
    ST_PRAISE_TEXT,
    ST_BACKUP_FORMAT,
    ST_BACKUP_PERIOD,
    ST_PISHVA_NAME_CHANGE,
    ST_ADMIN_NAME_CHANGE,
    ST_LOTTERY_SCOPE,
    ST_LOTTERY_CLASS,
    ST_TEAM_NAME,
    ST_TEAM_SLOGAN,
    ST_TEAM_MEMBERS,
    ST_TEAM_DATE,
    ST_TEAM_REQUESTER,
    ST_TEAM_CAPTAIN,
    ST_TEAM_ADD_PLAYER,
    ST_MATCH_TEAM_SELECT1,
    ST_MATCH_TEAM_SELECT2,
    ST_MATCH_TEAM_TYPE,
    ST_MATCH_TEAM_BOARDS,
    ST_NEW_YEAR_CONFIRM,
    ST_NEW_YEAR_PASSWORD,
    ST_UPDATE_VERSION,
    ST_UPDATE_DESC,
    ST_REPAIR_REASON,
    ST_GROUP_ID,
    ST_ADMIN_TASK_SS,
    ST_ACCESS_REQUEST_MSG,
    ST_OVERRIDE_STRIKE,
    ST_ADMIN_WARNING_REASON,
    ST_BULK_REG_TEXT,
    ST_BULK_REG_PREVIEW,
    ST_BULK_REG_EDIT_NUM,
    ST_BULK_REG_EDIT_VALUE,
    ST_CHANNEL_ID,
    ST_ADV_LOTTERY_SCOPE,
    ST_ADV_LOTTERY_CLASS_A,
    ST_ADV_LOTTERY_CLASS_B,
    ST_ADV_LOTTERY_COUNT,
) = range(76)
