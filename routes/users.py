"""User-management routes."""

from flask import Blueprint, render_template, request, redirect, url_for, flash

from models import db, User

bp = Blueprint("users", __name__)


@bp.route("/users")
def index():
    """List all Telegram users."""
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template("users.html", users=users)


@bp.route("/users/add", methods=["POST"])
def add():
    """Manually add a Telegram user."""
    chat_id  = request.form.get("chat_id", "").strip()
    username = request.form.get("username", "").strip()

    if not chat_id:
        flash("Chat ID is required.", "error")
        return redirect(url_for("users.index"))

    if User.query.filter_by(chat_id=chat_id).first():
        flash("That Chat ID is already registered.", "warning")
        return redirect(url_for("users.index"))

    db.session.add(User(chat_id=chat_id, username=username))
    db.session.commit()

    flash("User added!", "success")
    return redirect(url_for("users.index"))


@bp.route("/users/<int:uid>/toggle", methods=["POST"])
def toggle(uid):
    """Toggle user active / inactive."""
    user = db.session.get(User, uid)
    if user:
        user.is_active = not user.is_active
        db.session.commit()
        state = "activated" if user.is_active else "paused"
        flash(f"User {state}.", "success")
    return redirect(url_for("users.index"))


@bp.route("/users/<int:uid>/delete", methods=["POST"])
def delete(uid):
    """Delete a user."""
    user = db.session.get(User, uid)
    if user:
        db.session.delete(user)
        db.session.commit()
        flash("User removed.", "success")
    return redirect(url_for("users.index"))

