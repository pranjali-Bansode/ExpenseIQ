from flask import Blueprint, render_template, request, redirect, url_for, flash, session, abort
from datetime import date, datetime

from database.queries import (
    insert_expense,
    get_expense_by_id,
    update_expense,
    delete_expense_by_id,
    get_budget,
    get_total_expense_for_category
)

expense_bp = Blueprint('expenses', __name__)

CATEGORIES = [
    "Food",
    "Transport",
    "Bills",
    "Health",
    "Entertainment",
    "Shopping",
    "Other",
]


def _parse_date(val):
    try:
        datetime.strptime(val, "%Y-%m-%d")
        return val
    except ValueError:
        return None


@expense_bp.route("/expenses/add", methods=["GET", "POST"])
def add_expense():
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))

    today = date.today().isoformat()

    if request.method == "POST":
        amount_raw = request.form.get("amount", "").strip()
        category = request.form.get("category", "").strip()
        expense_date = request.form.get("date", "").strip()
        description = request.form.get("description", "").strip()

        # ---------------- VALIDATION ---------------- #

        try:
            amount = float(amount_raw)
            if amount <= 0:
                raise ValueError("Amount must be positive")
        except ValueError:
            flash("Amount must be a positive number.", "error")
            return render_template(
                "add_expense.html",
                categories=CATEGORIES,
                today=today,
                form=request.form
            )

        if category not in CATEGORIES:
            flash("Invalid category.", "error")
            return render_template(
                "add_expense.html",
                categories=CATEGORIES,
                today=today,
                form=request.form
            )

        if not _parse_date(expense_date):
            flash("Invalid date.", "error")
            return render_template(
                "add_expense.html",
                categories=CATEGORIES,
                today=today,
                form=request.form
            )

        # ---------------- INSERT ---------------- #
        insert_expense(session["user_id"], amount, category, expense_date, description)

        # ---------------- BUDGET LOGIC ---------------- #
        month = datetime.now().strftime("%Y-%m")

        budget = get_budget(session["user_id"], category, month)
        total_spent = get_total_expense_for_category(session["user_id"], category, month)

        if budget:
            if total_spent >= budget:
                flash(f"ЁЯЪи Budget exceeded for {category}!", "error")
            elif total_spent >= 0.8 * budget:
                flash(f"тЪая╕П You have used 80% of your {category} budget", "warning")

        flash("Expense added successfully.", "success")
        return redirect(url_for("profile"))

    # ---------------- GET REQUEST ---------------- #
    return render_template(
        "add_expense.html",
        categories=CATEGORIES,
        today=today,
        form={}
    )


@expense_bp.route("/expenses/<int:id>/edit", methods=["GET", "POST"])
def edit_expense(id):
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))

    expense = get_expense_by_id(id, session["user_id"])
    if expense is None:
        abort(404)

    if request.method == "GET":
        return render_template(
            "edit_expense.html",
            expense=expense,
            categories=CATEGORIES,
            form={}
        )

    amount_raw = request.form.get("amount", "").strip()
    category = request.form.get("category", "").strip()
    expense_date = request.form.get("date", "").strip()
    description = request.form.get("description", "").strip()

    try:
        amount = float(amount_raw)
        if amount <= 0:
            raise ValueError("Amount must be positive")
    except ValueError:
        flash("Invalid amount.", "error")
        return redirect(url_for("expenses.edit_expense", id=id))

    if category not in CATEGORIES:
        flash("Invalid category.", "error")
        return redirect(url_for("expenses.edit_expense", id=id))

    if not _parse_date(expense_date):
        flash("Invalid date.", "error")
        return redirect(url_for("expenses.edit_expense", id=id))

    update_expense(id, session["user_id"], amount, category, expense_date, description)

    flash("Updated successfully.", "success")
    return redirect(url_for("profile"))


@expense_bp.route("/expenses/<int:id>/delete", methods=["POST"])
def delete_expense(id):
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))

    expense = get_expense_by_id(id, session["user_id"])
    if expense is None:
        abort(404)

    delete_expense_by_id(id, session["user_id"])

    flash("Deleted successfully.", "success")
    return redirect(url_for("profile"))
