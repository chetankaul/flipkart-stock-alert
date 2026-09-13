"""Background stock-monitoring engine.

Spawns one daemon thread per active product.  Each thread checks stock for
every active pincode, sends alerts to all active Telegram users, and updates
the product's status in the database.
"""

import threading
import time
import urllib3
from datetime import datetime

import requests
import telebot

from config import FLIPKART_HEADERS, TELEGRAM_BOT_TOKEN, IST

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Shared bot instance for sending alerts
_bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN, parse_mode="HTML",
                        disable_web_page_preview=True)


# ── Stock-check logic (ported from notifier_v3) ──────────────────────────────

def _check_stock(url: str, pincode: str) -> dict | None:
    """Hit the Flipkart internal API and return a result dict, or None on error.

    Returns:
        {"title": str, "available": bool,
         "final_price": str, "offer_price": str, "pincode": str}
    """
    try:
        page_uri = url.split("flipkart.com", 1)[1]
    except IndexError:
        return None

    api_url = "https://rome.api.flipkart.com/api/4/page/fetch?cacheFirst=false"
    payload = {
        "pageUri": page_uri,
        "pageContext": {"pageNumber": 1, "fetchSeoData": True},
        "locationContext": {"pincode": pincode},
    }

    try:
        resp = requests.post(api_url, headers=FLIPKART_HEADERS,
                             json=payload, verify=False, timeout=15)
        data = resp.json()
    except Exception:
        return None

    page_data = data.get("RESPONSE", {}).get("pageData", {})
    schema    = page_data.get("seoData", {}).get("schema", [])
    title     = schema[0].get("name") if schema else "Unknown Product"

    tracking  = (page_data.get("pageContext", {})
                 .get("fdpEventTracking", {})
                 .get("events", {})
                 .get("psi", {}))

    available   = bool(tracking.get("pls", {}).get("isAvailable"))
    pricing     = tracking.get("ppd", {})
    final_price = str(pricing.get("finalPrice", "N/A"))
    offer_price = str(pricing.get("nepPrice", "N/A"))

    return {
        "title":       title,
        "available":   available,
        "final_price": final_price,
        "offer_price": offer_price,
        "pincode":     pincode,
    }


# ── Alert dispatcher ─────────────────────────────────────────────────────────

def _send_alerts(message: str, app):
    """Send *message* to every active Telegram user."""
    with app.app_context():
        from models import User
        recipients = [
            (u.chat_id, u.username)
            for u in User.query.filter_by(is_active=True).all()
        ]

    for chat_id, username in recipients:
        try:
            _bot.send_message(chat_id, message)
            time.sleep(0.05)                       # respect Telegram rate limits
        except Exception as exc:
            print(f"  ✗ Alert to {username}: {exc}")


# ── Per-product monitoring loop ──────────────────────────────────────────────

# Shared health state updated by every monitor thread
_health_lock     = threading.Lock()
_last_check_at   = None          # datetime of most recent check across all threads
_started_at      = None          # engine start time


def _monitor_product(product_id: int, app):
    """Continuously check a single product against all active pincodes."""
    global _last_check_at

    print(f"[Monitor] Worker thread started for product ID {product_id}")

    while True:
        try:
            # ── Load everything we need inside a context, then detach ─────
            with app.app_context():
                from models import db, Product, Pincode, Setting

                product = db.session.get(Product, product_id)
                if not product or not product.is_active:
                    print(f"[Monitor] Product ID {product_id} inactive or deleted — stopping worker thread.")
                    return                              # thread exits cleanly

                product_url = product.url               # plain string — safe outside ctx
                pincodes    = [p.pincode for p in Pincode.query.filter_by(is_active=True).all()]
                interval    = int(Setting.get("check_interval", "10"))
                cooldown    = int(Setting.get("alert_cooldown", "300"))

            if not pincodes:
                time.sleep(interval)
                continue

            # ── Check stock (no DB/session needed here) ──────────────────
            any_in_stock  = False
            stock_results = []

            for pin in pincodes:
                result = _check_stock(product_url, pin)
                if result and result["available"]:
                    any_in_stock = True
                    stock_results.append(result)

            now = datetime.now(IST)

            # ── Update DB status ─────────────────────────────────────────
            with app.app_context():
                product = db.session.get(Product, product_id)
                if product:
                    product.last_checked = now
                    product.last_status  = "in_stock" if any_in_stock else "out_of_stock"
                    db.session.commit()

            # Update shared health timestamp
            with _health_lock:
                _last_check_at = now

            # ── Alert if in stock ────────────────────────────────────────
            if any_in_stock:
                title = stock_results[0]["title"]
                lines = [f"<b>🟢 [In Stock] {title}</b>\n"]
                for r in stock_results:
                    lines.append(
                        f"📍 {r['pincode']}  —  LP: ₹{r['final_price']} | "
                        f"Offers: ₹{r['offer_price']}"
                    )
                lines.append(f"\n{product_url}")
                _send_alerts("\n".join(lines), app)
                time.sleep(cooldown)
            else:
                time.sleep(interval)

        except Exception as exc:
            print(f"[Monitor] Error in worker thread for product ID {product_id}: {exc}")
            time.sleep(10)


# ── Engine public API ────────────────────────────────────────────────────────

class MonitorEngine:
    """Manages one daemon thread per active product."""

    def __init__(self, app):
        global _started_at
        self._app     = app
        self._threads: dict[int, threading.Thread] = {}
        _started_at   = datetime.now(IST)

    # ── Health info (read by the dashboard) ───────────────────────────

    @property
    def active_threads(self) -> int:
        """Number of currently alive monitor threads."""
        return sum(1 for t in self._threads.values() if t.is_alive())

    @property
    def last_check_at(self) -> datetime | None:
        with _health_lock:
            return _last_check_at

    @property
    def started_at(self) -> datetime | None:
        return _started_at

    # ------------------------------------------------------------------

    def start(self):
        """Launch monitoring threads for every active product."""
        with self._app.app_context():
            from models import Product
            products = Product.query.filter_by(is_active=True).all()

        for p in products:
            self._launch(p.id)

        print(f"[Monitor] Started {len(self._threads)} monitoring thread(s)")

    def reload(self):
        """Reconcile running threads with the current DB state.

        - Starts threads for newly-active products.
        - Dead threads (product deactivated / deleted) are cleaned up.
        """
        with self._app.app_context():
            from models import Product
            active_ids = {p.id for p in Product.query.filter_by(is_active=True).all()}

        # Prune finished / stale threads
        for pid in list(self._threads):
            if not self._threads[pid].is_alive() or pid not in active_ids:
                print(f"[Monitor] Removing stopped thread for product ID {pid}")
                del self._threads[pid]

        # Start missing threads
        for pid in active_ids:
            if pid not in self._threads or not self._threads[pid].is_alive():
                print(f"[Monitor] Reload detected active product ID {pid} — launching thread")
                self._launch(pid)

    # ------------------------------------------------------------------

    def _launch(self, product_id: int):
        t = threading.Thread(target=_monitor_product,
                             args=(product_id, self._app), daemon=True)
        t.start()
        self._threads[product_id] = t


# ── Global Engine Instance Accessors ──────────────────────────────────────────

_engine: MonitorEngine | None = None


def init_engine(app) -> MonitorEngine:
    """Initialize and return the global MonitorEngine singleton."""
    global _engine
    _engine = MonitorEngine(app)
    return _engine


def get_engine() -> MonitorEngine | None:
    """Return the active MonitorEngine instance, if initialized."""
    return _engine


def reload_engine():
    """Trigger a hot reload of the monitor threads against current database state."""
    if _engine:
        _engine.reload()
    else:
        print("[Monitor] Warning: reload_engine called but monitor engine is not initialized.")


