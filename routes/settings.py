"""Settings & pincode management routes."""

from flask import Blueprint, render_template, request, redirect, url_for, flash

from models import db, Setting, Pincode

bp = Blueprint("settings", __name__)


@bp.route("/settings")
def index():
    """Show settings form + pincode list."""
    pincodes = Pincode.query.order_by(Pincode.id).all()
    return render_template("settings.html",
                           check_interval=Setting.get("check_interval", "10"),
                           alert_cooldown=Setting.get("alert_cooldown", "300"),
                           pincodes=pincodes)


@bp.route("/settings/save", methods=["POST"])
def save():
    """Persist timing settings."""
    interval = request.form.get("check_interval", "10").strip()
    cooldown = request.form.get("alert_cooldown", "300").strip()

    # Basic validation
    try:
        int(interval)
        int(cooldown)
    except ValueError:
        flash("Intervals must be whole numbers (seconds).", "error")
        return redirect(url_for("settings.index"))

    Setting.set("check_interval", interval)
    Setting.set("alert_cooldown", cooldown)

    flash("Settings saved!", "success")
    return redirect(url_for("settings.index"))


# ── Pincode CRUD ─────────────────────────────────────────────────────────────

@bp.route("/settings/pincodes/add", methods=["POST"])
def add_pincode():
    """Add a pincode to the global list."""
    pincode = request.form.get("pincode", "").strip()
    label   = request.form.get("label", "").strip()

    if not pincode or not pincode.isdigit() or len(pincode) != 6:
        flash("Enter a valid 6-digit pincode.", "error")
        return redirect(url_for("settings.index"))

    if Pincode.query.filter_by(pincode=pincode).first():
        flash("That pincode already exists.", "warning")
        return redirect(url_for("settings.index"))

    db.session.add(Pincode(pincode=pincode, label=label))
    db.session.commit()

    flash(f"Pincode {pincode} added!", "success")
    return redirect(url_for("settings.index"))


@bp.route("/settings/pincodes/<int:pid>/toggle", methods=["POST"])
def toggle_pincode(pid):
    """Toggle a pincode active / inactive."""
    pin = db.session.get(Pincode, pid)
    if pin:
        pin.is_active = not pin.is_active
        db.session.commit()
        flash(f"Pincode {pin.pincode} {'enabled' if pin.is_active else 'disabled'}.",
              "success")
    return redirect(url_for("settings.index"))


@bp.route("/settings/pincodes/<int:pid>/delete", methods=["POST"])
def delete_pincode(pid):
    """Remove a pincode."""
    pin = db.session.get(Pincode, pid)
    if pin:
        db.session.delete(pin)
        db.session.commit()
        flash("Pincode removed.", "success")
    return redirect(url_for("settings.index"))

