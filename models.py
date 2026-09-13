"""SQLAlchemy models — Product, User, Pincode, and key-value Settings."""

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from config import IST

db = SQLAlchemy()


class Product(db.Model):
    """A Flipkart product URL to monitor."""

    __tablename__ = "products"

    id           = db.Column(db.Integer, primary_key=True)
    url          = db.Column(db.String(1024), nullable=False, unique=True)
    label        = db.Column(db.String(256), default="")
    target_price = db.Column(db.Float, nullable=True)            # Alert only if price <= target_price
    last_price   = db.Column(db.String(32), nullable=True)       # Last observed price string e.g. "₹44,999"
    is_active    = db.Column(db.Boolean, default=True)
    last_status  = db.Column(db.String(32), default="unknown")   # "in_stock" / "out_of_stock" / "error" / "unknown"
    last_checked = db.Column(db.DateTime, nullable=True)
    created_at   = db.Column(db.DateTime, default=lambda: datetime.now(IST))

    def __repr__(self):
        return f"<Product {self.id}: {self.label or self.url[:40]}>"


class User(db.Model):
    """A Telegram user who receives stock alerts."""

    __tablename__ = "users"

    id         = db.Column(db.Integer, primary_key=True)
    chat_id    = db.Column(db.String(64), nullable=False, unique=True)
    username   = db.Column(db.String(128), default="")
    is_active  = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(IST))

    def __repr__(self):
        return f"<User {self.chat_id} @{self.username}>"


class Pincode(db.Model):
    """A pincode to check stock availability against."""

    __tablename__ = "pincodes"

    id        = db.Column(db.Integer, primary_key=True)
    pincode   = db.Column(db.String(10), nullable=False, unique=True)
    label     = db.Column(db.String(64), default="")    # e.g. "Delhi", "Mumbai"
    is_active = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f"<Pincode {self.pincode} ({self.label})>"


class Setting(db.Model):
    """Runtime-editable key → value configuration store."""

    __tablename__ = "settings"

    key   = db.Column(db.String(64), primary_key=True)
    value = db.Column(db.String(256), nullable=False)

    # ── Convenience helpers ───────────────────────────────────────────────

    @classmethod
    def get(cls, key: str, default: str = "") -> str:
        """Return the value for *key*, or *default* if not set."""
        row = db.session.get(cls, key)
        return row.value if row else default

    @classmethod
    def set(cls, key: str, value: str) -> None:
        """Insert or update a setting."""
        row = db.session.get(cls, key)
        if row:
            row.value = value
        else:
            db.session.add(cls(key=key, value=value))
        db.session.commit()

