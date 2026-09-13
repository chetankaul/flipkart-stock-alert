"""Product-management routes."""

import re
from flask import Blueprint, render_template, request, redirect, url_for, flash

from models import db, Product

bp = Blueprint("products", __name__)

_FLIPKART_URL_RE = re.compile(
    r"https?://(?:www\.)?flipkart\.com/.+", re.IGNORECASE
)


@bp.route("/products")
def index():
    """List all products."""
    products = Product.query.order_by(Product.created_at.desc()).all()
    return render_template("products.html", products=products)


@bp.route("/products/add", methods=["POST"])
def add():
    """Add a new product after validating the URL."""
    url          = request.form.get("url", "").strip()
    label        = request.form.get("label", "").strip()
    target_price = request.form.get("target_price", "").strip()

    if not url:
        flash("URL is required.", "error")
        return redirect(url_for("products.index"))

    if not _FLIPKART_URL_RE.match(url):
        flash("Invalid URL — must be a flipkart.com product link.", "error")
        return redirect(url_for("products.index"))

    if Product.query.filter_by(url=url).first():
        flash("That product is already being monitored.", "warning")
        return redirect(url_for("products.index"))

    price_val = None
    if target_price:
        try:
            price_val = float(target_price)
            if price_val <= 0:
                flash("Target price must be greater than 0.", "error")
                return redirect(url_for("products.index"))
        except ValueError:
            flash("Invalid target price. Please enter a valid number.", "error")
            return redirect(url_for("products.index"))

    db.session.add(Product(url=url, label=label, target_price=price_val))
    db.session.commit()

    # Trigger monitor reload
    from monitor import reload_engine
    reload_engine()

    flash("Product added!", "success")
    return redirect(url_for("products.index"))


@bp.route("/products/<int:pid>/edit", methods=["POST"])
def edit(pid):
    """Update a product's label and target price."""
    product = db.session.get(Product, pid)
    if not product:
        flash("Product not found.", "error")
        return redirect(url_for("products.index"))

    label        = request.form.get("label", "").strip()
    target_price = request.form.get("target_price", "").strip()

    product.label = label

    if target_price:
        try:
            price_val = float(target_price)
            if price_val <= 0:
                flash("Target price must be greater than 0.", "error")
                return redirect(url_for("products.index"))
            product.target_price = price_val
        except ValueError:
            flash("Invalid target price. Please enter a valid number.", "error")
            return redirect(url_for("products.index"))
    else:
        product.target_price = None

    db.session.commit()

    from monitor import reload_engine
    reload_engine()

    flash("Product updated!", "success")
    return redirect(url_for("products.index"))


@bp.route("/products/<int:pid>/toggle", methods=["POST"])
def toggle(pid):
    """Toggle active / inactive."""
    product = db.session.get(Product, pid)
    if product:
        product.is_active = not product.is_active
        db.session.commit()

        from monitor import reload_engine
        reload_engine()

        state = "activated" if product.is_active else "paused"
        flash(f"Product {state}.", "success")
    return redirect(url_for("products.index"))


@bp.route("/products/<int:pid>/delete", methods=["POST"])
def delete(pid):
    """Delete a product."""
    product = db.session.get(Product, pid)
    if product:
        db.session.delete(product)
        db.session.commit()

        from monitor import reload_engine
        reload_engine()

        flash("Product removed.", "success")
    return redirect(url_for("products.index"))

