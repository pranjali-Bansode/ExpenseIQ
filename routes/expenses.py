from flask import Blueprint, render_template, request, redirect, url_for, flash, session, abort
from datetime import date

from database.queries import (
    insert_expense,
    get_expense_by_id,
    update_expense,
    delete_expense_by_id,
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
    from datetime import datetime
    try:
        datetime.strptime(val, "%Y-%m-%d")
        return val
    except:
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

        try:
            amount = float(amount_raw)
            if amount <= 0:
                raise ValueError
        except ValueError:
            flash("Amount must be a positive number.", "error")
            return render_template("add_expense.html", categories=CATEGORIES, form=request.form, today=today)

        if category not in CATEGORIES:
            flash("Invalid category.", "error")
            return render_template("add_expense.html", categories=CATEGORIES, form=request.form, today=today)

        if not _parse_date(expense_date):
            flash("Invalid date.", "error")
            return render_template("add_expense.html", categories=CATEGORIES, form=request.form, today=today)

        insert_expense(session["user_id"], amount, category, expense_date, description)
        flash("Expense added.", "success")
        return redirect(url_for("profile"))

    return render_template("add_expense.html", categories=CATEGORIES, form={}, today=today)


@expense_bp.route("/expenses/<int:id>/edit", methods=["GET", "POST"])
def edit_expense(id):
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))

    expense = get_expense_by_id(id, session["user_id"])
    if expense is None:
        abort(404)

    if request.method == "GET":
        return render_template("edit_expense.html", expense=expense, categories=CATEGORIES, form={})

    amount_raw = request.form.get("amount", "").strip()
    category = request.form.get("category", "").strip()
    expense_date = request.form.get("date", "").strip()
    description = request.form.get("description", "").strip()

    try:
        amount = float(amount_raw)
        if amount <= 0:
            raise ValueError
    except:
        flash("Invalid amount.", "error")
        return render_template("edit_expense.html", expense=expense, categories=CATEGORIES, form=request.form)

    if category not in CATEGORIES:
        flash("Invalid category.", "error")
        return render_template("edit_expense.html", expense=expense, categories=CATEGORIES, form=request.form)

    if not _parse_date(expense_date):
        flash("Invalid date.", "error")
        return render_template("edit_expense.html", expense=expense, categories=CATEGORIES, form=request.form)

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
    return redirect(url_for("profile"))