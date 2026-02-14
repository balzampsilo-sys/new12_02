"""Конфигурация"""

import logging
import os
import sys
from pathlib import Path
from typing import List

import pytz
from dotenv import load_dotenv

load_dotenv()

# Setup basic logging early
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# === VALIDATION HELPERS ===

def validate_bot_token(token: str) -> bool:
    """Validate Telegram bot token format
    
    Expected format: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz
    
    Args:
        token: Bot token string
        
    Returns:
        True if valid format, False otherwise
    """
    if not token:
        return False
    
    parts = token.split(":")
    if len(parts) != 2:
        logger.error("BOT_TOKEN must have format: 123456789:ABCdef...")
        return False
    
    bot_id, token_part = parts
    
    if not bot_id.isdigit():
        logger.error("BOT_TOKEN bot ID must be numeric")
        return False
    
    if len(token_part) < 30:
        logger.error("BOT_TOKEN secret part too short (min 30 chars)")
        return False
    
    return True


def parse_admin_ids(ids_str: str) -> List[int]:
    """Parse ADMIN_IDS with validation and error handling
    
    Args:
        ids_str: Comma-separated string of user IDs
        
    Returns:
        List of valid admin IDs (positive integers)
        
    Raises:
        SystemExit if no valid IDs found
    """
    admin_ids = []
    
    for item in ids_str.split(","):
        item = item.strip()
        if not item:
            continue
            
        try:
            user_id = int(item)
            if user_id <= 0:
                logger.warning(f"⚠️ Invalid admin ID (must be > 0): {item}")
                continue
            admin_ids.append(user_id)
        except ValueError:
            logger.warning(f"⚠️ Invalid admin ID format (not a number): {item}")
            continue
    
    if not admin_ids:
        logger.error("❌ No valid admin IDs found in ADMIN_IDS")
        sys.exit("❌ ADMIN_IDS must contain at least one valid positive integer")
    
    logger.info(f"✅ Loaded {len(admin_ids)} admin ID(s): {admin_ids}")
    return admin_ids


# === BOT ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    sys.exit("❌ BOT_TOKEN not found in .env")

if not validate_bot_token(BOT_TOKEN):
    sys.exit("❌ BOT_TOKEN has invalid format. Expected: 123456789:ABCdef...")

# === ADMIN ===
ADMIN_IDS_STR = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = parse_admin_ids(ADMIN_IDS_STR)  # ✅ Safe parsing with validation

MAX_ADMIN_ADDITIONS_PER_HOUR = int(os.getenv("MAX_ADMIN_ADDITIONS_PER_HOUR", "3"))

# === BOOKINGS ===
MAX_BOOKINGS_PER_USER = int(os.getenv("MAX_BOOKINGS_PER_USER", "3"))
CANCELLATION_HOURS = int(os.getenv("CANCELLATION_HOURS", "24"))

# === REMINDERS ===
REMINDER_HOURS_BEFORE_1H = int(os.getenv("REMINDER_HOURS_BEFORE_1H", "1"))
REMINDER_HOURS_BEFORE_2H = int(os.getenv("REMINDER_HOURS_BEFORE_2H", "2"))
REMINDER_HOURS_BEFORE_24H = int(os.getenv("REMINDER_HOURS_BEFORE_24H", "24"))

# === FEEDBACK ===
FEEDBACK_HOURS_AFTER = int(os.getenv("FEEDBACK_HOURS_AFTER", "2"))

# === SERVICE INFO ===
SERVICE_LOCATION = os.getenv("SERVICE_LOCATION", "Москва, ул. Примерная, 1")

# === ONBOARDING ===
ONBOARDING_DELAY_SHORT = float(os.getenv("ONBOARDING_DELAY_SHORT", "1.5"))
ONBOARDING_DELAY_LONG = float(os.getenv("ONBOARDING_DELAY_LONG", "3.0"))

# === WORK SCHEDULE ===
WORK_HOURS_START = int(os.getenv("WORK_HOURS_START", "9"))
WORK_HOURS_END = int(os.getenv("WORK_HOURS_END", "18"))

# === DATABASE ===
# ✅ CHANGED: PostgreSQL by default (recommended for production)
DB_TYPE = os.getenv("DB_TYPE", "postgresql").lower()  # "postgresql" (default) or "sqlite" (legacy)

# SQLite configuration (legacy fallback)
DATABASE_PATH = os.getenv("DATABASE_PATH", "data/bookings.db")

# ✅ PostgreSQL configuration (RECOMMENDED)
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://booking_user:SecurePass2026!@postgres:5432/booking_saas"
)

# ✅ NEW: PostgreSQL Schema for multi-tenant isolation
# Each client gets their own schema (e.g., client_001, client_002)
PG_SCHEMA = os.getenv("PG_SCHEMA", "public")

# ✅ Connection pool settings (optimized for multiple clients)
DB_POOL_MIN_SIZE = int(os.getenv("DB_POOL_MIN_SIZE", "2"))
DB_POOL_MAX_SIZE = int(os.getenv("DB_POOL_MAX_SIZE", "10"))
DB_POOL_TIMEOUT = float(os.getenv("DB_POOL_TIMEOUT", "30.0"))
DB_COMMAND_TIMEOUT = float(os.getenv("DB_COMMAND_TIMEOUT", "60.0"))

# === DATABASE RETRY LOGIC ===
DB_MAX_RETRIES = int(os.getenv("DB_MAX_RETRIES", "3"))
DB_RETRY_DELAY = float(os.getenv("DB_RETRY_DELAY", "0.5"))
DB_RETRY_BACKOFF = float(os.getenv("DB_RETRY_BACKOFF", "2.0"))

# === REDIS (FSM Storage) ===
REDIS_ENABLED = os.getenv("REDIS_ENABLED", "True").lower() in ("true", "1", "yes")
REDIS_HOST = os.getenv("REDIS_HOST", "redis-shared")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

# ✅ CHANGED: All clients use DB 0 (unlimited clients via key prefix)
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)

# ✅ NEW: Client isolation via key prefix
# Instead of using different DB numbers (0-15 limit),
# we use unique prefixes for unlimited scalability
CLIENT_ID = os.getenv("CLIENT_ID", "default")
REDIS_KEY_PREFIX = os.getenv("REDIS_KEY_PREFIX", f"{CLIENT_ID}:")

# === SENTRY (Error Monitoring) ===
SENTRY_ENABLED = os.getenv("SENTRY_ENABLED", "False").lower() in ("true", "1", "yes")
SENTRY_DSN = os.getenv("SENTRY_DSN", "")
SENTRY_ENVIRONMENT = os.getenv("SENTRY_ENVIRONMENT", "production")
SENTRY_TRACES_SAMPLE_RATE = float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1"))

# === BACKUP ===
BACKUP_ENABLED = os.getenv("BACKUP_ENABLED", "True").lower() in ("true", "1", "yes")
BACKUP_DIR = os.getenv("BACKUP_DIR", "backups")
BACKUP_INTERVAL_HOURS = int(os.getenv("BACKUP_INTERVAL_HOURS", "24"))
BACKUP_RETENTION_DAYS = int(os.getenv("BACKUP_RETENTION_DAYS", "30"))

# === BROADCAST ===
BROADCAST_DELAY = float(os.getenv("BROADCAST_DELAY", "0.05"))

# === RATE LIMITING ===
RATE_LIMIT_MESSAGE = float(os.getenv("RATE_LIMIT_MESSAGE", "0.5"))
RATE_LIMIT_CALLBACK = float(os.getenv("RATE_LIMIT_CALLBACK", "0.3"))

# === CALENDAR ===
CALENDAR_MAX_MONTHS_AHEAD = int(os.getenv("CALENDAR_MAX_MONTHS_AHEAD", "3"))

# === TIMEZONE ===
TIMEZONE = pytz.timezone("Europe/Moscow")

# === DAY NAMES ===
DAY_NAMES = [
    "Пн",
    "Вт",
    "Ср",
    "Чт",
    "Пт",
    "Сб",
    "Вс",
]

DAY_NAMES_SHORT = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

MONTH_NAMES = [
    "Январь",
    "Февраль",
    "Март",
    "Апрель",
    "Май",
    "Июнь",
    "Июль",
    "Август",
    "Сентябрь",
    "Октябрь",
    "Ноябрь",
    "Декабрь",
]

# === CALLBACK VALIDATION ===
CALLBACK_VERSION = "v3"
CALLBACK_MESSAGE_TTL_HOURS = 48

# === ERROR CODES ===
ERROR_NO_SERVICES = "NO_SERVICES"
ERROR_SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
ERROR_LIMIT_EXCEEDED = "LIMIT_EXCEEDED"
ERROR_SLOT_TAKEN = "SLOT_TAKEN"

# === ADMIN ROLES ===
ROLE_SUPER_ADMIN = "super_admin"
ROLE_MODERATOR = "moderator"

ADMIN_ROLES = [ROLE_SUPER_ADMIN, ROLE_MODERATOR]

ROLE_PERMISSIONS = {
    ROLE_SUPER_ADMIN: {
        "manage_admins": True,
        "view_audit_log": True,
        "manage_bookings": True,
        "manage_slots": True,
        "edit_services": True,
        "export_data": True,
        "manage_settings": True,
    },
    ROLE_MODERATOR: {
        "manage_admins": False,
        "view_audit_log": False,
        "manage_bookings": True,
        "manage_slots": True,
        "edit_services": True,
        "export_data": False,
        "manage_settings": False,
    },
}

# === LOGGING ===
if DB_TYPE == "postgresql":
    logger.info(
        f"✅ Database: PostgreSQL\n"
        f"   • Pool: {DB_POOL_MIN_SIZE}-{DB_POOL_MAX_SIZE}\n"
        f"   • Schema: {PG_SCHEMA} (multi-tenant isolation)"
    )
else:
    logger.warning(f"⚠️ Database: SQLite (legacy) - {DATABASE_PATH}")
    logger.warning("⚠️ Consider using PostgreSQL for production (better scalability)")

if REDIS_ENABLED:
    logger.info(
        f"✅ Redis: {REDIS_HOST}:{REDIS_PORT}\n"
        f"   • DB: {REDIS_DB}\n"
        f"   • Client: {CLIENT_ID}\n"
        f"   • Key Prefix: {REDIS_KEY_PREFIX} (unlimited clients)"
    )
else:
    logger.warning("⚠️ Redis disabled - using MemoryStorage (not recommended for production)")
