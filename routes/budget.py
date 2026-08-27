from flask import Blueprint, request, redirect, url_for, flash, session
from datetime import datetime
from database.queries import set_budget
from database.queries import set_budget, delete_budget

budget_bp = Blueprint("budget", __name__)

VALID_CATEGORIES = [
    "Food",
    "Transport",
    "Bills",
    "Health",
    "Entertainment",
    "Shopping",
    "Other",
]


@budget_bp.route("/set-budget", methods=["POST"])
def set_budget_route():
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))

    category = request.form.get("category")
    amount = request.form.get("amount")

    # ✅ CATEGORY VALIDATION
    if category not in VALID_CATEGORIES:
        flash("Invalid category", "error")
        return redirect(url_for("profile"))

    # ✅ AMOUNT VALIDATION
    try:
        amount = float(amount)
        if amount <= 0:
            raise ValueError("Amount must be positive")
    except ValueError:
        flash("Invalid budget amount", "error")
        return redirect(url_for("profile"))

    # ✅ CURRENT MONTH
    month = datetime.now().strftime("%Y-%m")

    set_budget(session["user_id"], category, amount, month)

    flash(f"Budget set for {category}!", "success")
    return redirect(url_for("profile"))

@budget_bp.route("/budget/<category>/delete", methods=["POST"])
def delete_budget_route(category):
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))

    if category not in VALID_CATEGORIES:
        flash("Invalid category", "error")
        return redirect(url_for("profile"))

    month = datetime.now().strftime("%Y-%m")
    delete_budget(session["user_id"], category, month)

    flash(f"Budget removed for {category}.", "success")
    return redirect(url_for("profile"))