"""Centralised configuration — loads values from .env at import time."""

import os
from datetime import timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

# ── Timezone ──────────────────────────────────────────────────────────────────
IST = timezone(timedelta(hours=5, minutes=30))

# ── Telegram ──────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")

# ── Flask ─────────────────────────────────────────────────────────────────────
SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key")
SQLALCHEMY_DATABASE_URI: str = os.getenv("DATABASE_URI", "sqlite:///stock.db")

# ── Monitor defaults (overridable at runtime via Settings table) ──────────────
DEFAULT_CHECK_INTERVAL: int = int(os.getenv("CHECK_INTERVAL", "10"))
DEFAULT_ALERT_COOLDOWN: int = int(os.getenv("ALERT_COOLDOWN", "300"))
DEFAULT_PINCODE: str = os.getenv("DEFAULT_PINCODE", "110086")

# ── HTTP headers for Flipkart API ─────────────────────────────────────────────
FLIPKART_HEADERS: dict = {
    "Content-Type":    "application/json",
    "User-Agent":      ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/109.0.5414.120 Safari/537.36"),
    "X-User-Agent":    ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/109.0.5414.120 Safari/537.36 "
                        "FKUA/website/42/website/Desktop"),
    "Accept":          "*/*",
    "Origin":          "https://www.flipkart.com",
    "Referer":         "https://www.flipkart.com/",
    "Accept-Encoding": "gzip, deflate",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection":      "close",
}

