"""Flask application factory & entry point.

Launches the web UI, stock monitor engine, and Telegram bot polling
in a single process.
"""

from datetime import datetime
from flask import Flask, render_template

import config
from models import db, Product, User, Pincode, Setting

# Filled after app creation so other modules can import it
def create_app() -> Flask:
    """Build and configure the Flask app."""
    app = Flask(__name__)

    app.config["SECRET_KEY"]              = config.SECRET_KEY
    app.config["SQLALCHEMY_DATABASE_URI"] = config.SQLALCHEMY_DATABASE_URI
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "connect_args": {"timeout": 30}
    }

    db.init_app(app)

    # ── Register blueprints ───────────────────────────────────────────────
    from routes.products import bp as products_bp
    from routes.users    import bp as users_bp
    from routes.settings import bp as settings_bp

    app.register_blueprint(products_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(settings_bp)

    # ── Dashboard route ───────────────────────────────────────────────────
    @app.route("/")
    def dashboard():
        products       = Product.query.order_by(Product.created_at.desc()).all()
        total_products = len(products)
        in_stock       = sum(1 for p in products if p.last_status == "in_stock")
        out_of_stock   = sum(1 for p in products if p.last_status == "out_of_stock")
        active_users   = User.query.filter_by(is_active=True).count()

        # Engine health
        from monitor import get_engine
        engine         = get_engine()
        engine_ok      = False
        active_threads = 0
        last_check     = None
        engine_uptime  = None

        if engine:
            active_threads = engine.active_threads
            last_check     = engine.last_check_at
            started        = engine.started_at
            engine_ok      = active_threads > 0 or total_products == 0

            if started:
                from config import IST
                delta = datetime.now(IST) - started
                hours, rem = divmod(int(delta.total_seconds()), 3600)
                mins, secs = divmod(rem, 60)
                engine_uptime = f"{hours}h {mins}m {secs}s"

        return render_template("dashboard.html",
                               products=products,
                               total_products=total_products,
                               in_stock=in_stock,
                               out_of_stock=out_of_stock,
                               active_users=active_users,
                               engine_ok=engine_ok,
                               active_threads=active_threads,
                               last_check=last_check,
                               engine_uptime=engine_uptime)

    # ── Create tables & seed defaults ─────────────────────────────────────
    with app.app_context():
        db.create_all()
        _seed_defaults()

    return app


def _seed_defaults():
    """Populate initial settings and the default pincode on first run."""
    if not db.session.get(Setting, "check_interval"):
        db.session.add(Setting(key="check_interval",
                               value=str(config.DEFAULT_CHECK_INTERVAL)))
    if not db.session.get(Setting, "alert_cooldown"):
        db.session.add(Setting(key="alert_cooldown",
                               value=str(config.DEFAULT_ALERT_COOLDOWN)))

    # Seed the default pincode if the table is empty
    if Pincode.query.count() == 0:
        db.session.add(Pincode(pincode=config.DEFAULT_PINCODE, label="Default"))

    db.session.commit()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = create_app()

    # Start the stock monitor engine
    from monitor import init_engine
    engine = init_engine(app)
    engine.start()

    # Start the Telegram bot polling
    import telegram_bot
    telegram_bot.start(app)

    print("\n  🚀  Stock Notifier running at http://127.0.0.1:5000\n")
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)

