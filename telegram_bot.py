"""Telegram bot — handles user self-registration and basic commands.

Runs `bot.infinity_polling()` in a daemon thread so it coexists with Flask.
"""

import re
import threading

import telebot

from config import TELEGRAM_BOT_TOKEN

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN, parse_mode="HTML",
                       disable_web_page_preview=True)

# The Flask app reference is set in `start()` so we can push app context.
_app = None

_FLIPKART_URL_RE = re.compile(
    r"https?://(?:www\.)?flipkart\.com/.+", re.IGNORECASE
)


# ── /start — self-register ───────────────────────────────────────────────────

@bot.message_handler(commands=["start"])
def _handle_start(message):
    with _app.app_context():
        from models import db, User

        chat_id  = str(message.chat.id)
        username = message.from_user.username or message.from_user.first_name or ""

        existing = User.query.filter_by(chat_id=chat_id).first()
        if existing:
            bot.reply_to(message, "✅ You're already registered for alerts!")
            return

        db.session.add(User(chat_id=chat_id, username=username))
        db.session.commit()

    bot.reply_to(message, (
        "🎉 <b>Registered!</b>\n\n"
        "You'll now receive stock alerts.\n"
        "Use /status to see monitored products.\n"
        "Use /add <code>&lt;flipkart-url&gt;</code> to add a product."
    ))


# ── /status — current product snapshot ───────────────────────────────────────

@bot.message_handler(commands=["status"])
def _handle_status(message):
    with _app.app_context():
        from models import Product

        products = Product.query.filter_by(is_active=True).all()
        if not products:
            bot.reply_to(message, "📭 No products being monitored yet.")
            return

        lines = ["<b>📋 Monitored Products</b>\n"]
        for p in products:
            icon = {"in_stock": "🟢", "out_of_stock": "🔴",
                    "error": "⚠️"}.get(p.last_status, "⚪")
            label = p.label or p.url[:50]
            price_info = f" (Target: ≤ ₹{int(p.target_price):,})" if p.target_price else ""
            if p.last_price:
                price_info += f" [Latest: {p.last_price}]"
            lines.append(f"{icon} <a href='{p.url}'>{label}</a>{price_info}")

        bot.reply_to(message, "\n".join(lines))


# ── /add <url> [max_price] — add a product from Telegram ───────────────────

@bot.message_handler(commands=["add"])
def _handle_add(message):
    parts = message.text.split()
    if len(parts) < 2 or not _FLIPKART_URL_RE.match(parts[1].strip()):
        bot.reply_to(message,
                     "Usage: /add <code>&lt;flipkart-url&gt;</code> <code>[max_price]</code>\n"
                     "Example: /add https://www.flipkart.com/... 45000")
        return

    url = parts[1].strip()
    target_price = None
    if len(parts) >= 3:
        try:
            target_price = float(re.sub(r"[^\d.]", "", parts[2]))
            if target_price <= 0:
                target_price = None
        except ValueError:
            target_price = None

    with _app.app_context():
        from models import db, Product

        if Product.query.filter_by(url=url).first():
            bot.reply_to(message, "ℹ️ That product is already being monitored.")
            return

        db.session.add(Product(url=url, target_price=target_price))
        db.session.commit()

    # Trigger monitor reload so the new product starts being checked
    from monitor import reload_engine
    reload_engine()

    price_msg = f" (Alert when ≤ ₹{int(target_price):,})" if target_price else ""
    bot.reply_to(message, f"✅ Product added and monitoring started!{price_msg}")


# ── Public API ───────────────────────────────────────────────────────────────

def start(app):
    """Begin polling in a background daemon thread."""
    global _app
    _app = app

    def _poll():
        print("[Telegram] Bot polling started")
        bot.infinity_polling(timeout=30, long_polling_timeout=30)

    t = threading.Thread(target=_poll, daemon=True)
    t.start()

