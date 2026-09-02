from flask import Blueprint, render_template, request, redirect, url_for, flash, session, abort
from datetime import date, datetime

from database.queries import (
    insert_expense,
    get_expense_by_id,
    update_expense,
    delete_expense_by_id,
    get_budget,
    get_total_expense_for_category,
    get_category_average
)


from database.queries import (
    insert_expense,
    get_expense_by_id,
    update_expense,
    delete_expense_by_id,
    get_budget,
    get_total_expense_for_category,
    get_category_average,
    create_recurring_expense,
    get_recurring_expenses,
    get_recurring_expense_by_id,
    update_recurring_expense,
    delete_recurring_expense,
    get_recurring_expense_summary
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

        # ---------------- ANOMALY CHECK (before insert) ---------------- #
        avg_amount = get_category_average(session["user_id"], category)
        is_anomaly = avg_amount > 0 and amount > (2 * avg_amount)

        # ---------------- INSERT ---------------- #
        insert_expense(session["user_id"], amount, category, expense_date, description)

        # ---------------- BUDGET LOGIC ---------------- #
        month = datetime.now().strftime("%Y-%m")

        budget = get_budget(session["user_id"], category, month)
        total_spent = get_total_expense_for_category(session["user_id"], category, month)

        if is_anomaly:
            flash(
                f"⚠️ This ₹{amount:.2f} {category} expense is more than double "
                f"your usual ₹{avg_amount:.2f} average for this category.",
                "warning"
            )

        if budget:
            if total_spent >= budget:
                flash(f"🚨 Budget exceeded for {category}!", "error")
            elif total_spent >= 0.8 * budget:
                flash(f"⚠️ You have used 80% of your {category} budget", "warning")

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

    

# =======================
# RECURRING EXPENSES
# =======================

@expense_bp.route("/recurring/add", methods=["GET", "POST"])
def add_recurring_expense():
    """Add a new recurring expense"""
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))

    today = date.today().isoformat()

    if request.method == "POST":
        amount_raw = request.form.get("amount", "").strip()
        category = request.form.get("category", "").strip()
        frequency = request.form.get("frequency", "").strip()
        start_date = request.form.get("start_date", "").strip()
        end_date = request.form.get("end_date", "").strip() or None
        description = request.form.get("description", "").strip()

        # Validation
        try:
            amount = float(amount_raw)
            if amount <= 0:
                raise ValueError("Amount must be positive")
        except ValueError:
            flash("Amount must be a positive number.", "error")
            return render_template(
                "add_recurring_expense.html",
                categories=CATEGORIES,
                frequencies=["daily", "weekly", "biweekly", "monthly", "quarterly", "yearly"],
                today=today,
                form=request.form
            )

        if category not in CATEGORIES:
            flash("Invalid category.", "error")
            return render_template(
                "add_recurring_expense.html",
                categories=CATEGORIES,
                frequencies=["daily", "weekly", "biweekly", "monthly", "quarterly", "yearly"],
                today=today,
                form=request.form
            )

        if frequency not in ["daily", "weekly", "biweekly", "monthly", "quarterly", "yearly"]:
            flash("Invalid frequency.", "error")
            return render_template(
                "add_recurring_expense.html",
                categories=CATEGORIES,
                frequencies=["daily", "weekly", "biweekly", "monthly", "quarterly", "yearly"],
                today=today,
                form=request.form
            )

        if not _parse_date(start_date):
            flash("Invalid start date.", "error")
            return render_template(
                "add_recurring_expense.html",
                categories=CATEGORIES,
                frequencies=["daily", "weekly", "biweekly", "monthly", "quarterly", "yearly"],
                today=today,
                form=request.form
            )

        if end_date and not _parse_date(end_date):
            flash("Invalid end date.", "error")
            return render_template(
                "add_recurring_expense.html",
                categories=CATEGORIES,
                frequencies=["daily", "weekly", "biweekly", "monthly", "quarterly", "yearly"],
                today=today,
                form=request.form
            )

        # Create recurring expense
        create_recurring_expense(
            session["user_id"],
            amount,
            category,
            description,
            frequency,
            start_date,
            end_date
        )

        flash("Recurring expense added successfully!", "success")
        return redirect(url_for("profile"))

    # GET request
    return render_template(
        "add_recurring_expense.html",
        categories=CATEGORIES,
        frequencies=["daily", "weekly", "biweekly", "monthly", "quarterly", "yearly"],
        today=today,
        form={}
    )


@expense_bp.route("/recurring/list")
def list_recurring_expenses():
    """View all recurring expenses"""
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))

    recurring_expenses = get_recurring_expenses(session["user_id"], only_active=True)
    summary = get_recurring_expense_summary(session["user_id"])

    return render_template(
        "recurring_expenses.html",
        recurring_expenses=recurring_expenses,
        summary=summary
    )


@expense_bp.route("/recurring/<int:id>/edit", methods=["GET", "POST"])
def edit_recurring_expense(id):
    """Edit a recurring expense"""
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))

    recurring = get_recurring_expense_by_id(id, session["user_id"])
    if recurring is None:
        abort(404)

    if request.method == "GET":
        return render_template(
            "edit_recurring_expense.html",
            recurring=recurring,
            categories=CATEGORIES,
            frequencies=["daily", "weekly", "biweekly", "monthly", "quarterly", "yearly"],
            form={}
        )

    # POST request
    amount_raw = request.form.get("amount", "").strip()
    category = request.form.get("category", "").strip()
    frequency = request.form.get("frequency", "").strip()
    end_date = request.form.get("end_date", "").strip() or None
    description = request.form.get("description", "").strip()

    try:
        amount = float(amount_raw)
        if amount <= 0:
            raise ValueError("Amount must be positive")
    except ValueError:
        flash("Invalid amount.", "error")
        return redirect(url_for("expenses.edit_recurring_expense", id=id))

    if category not in CATEGORIES:
        flash("Invalid category.", "error")
        return redirect(url_for("expenses.edit_recurring_expense", id=id))

    if frequency not in ["daily", "weekly", "biweekly", "monthly", "quarterly", "yearly"]:
        flash("Invalid frequency.", "error")
        return redirect(url_for("expenses.edit_recurring_expense", id=id))

    if end_date and not _parse_date(end_date):
        flash("Invalid end date.", "error")
        return redirect(url_for("expenses.edit_recurring_expense", id=id))

    update_recurring_expense(id, session["user_id"], amount, category, description, frequency, end_date)

    flash("Recurring expense updated successfully.", "success")
    return redirect(url_for("expenses.list_recurring_expenses"))


@expense_bp.route("/recurring/<int:id>/delete", methods=["POST"])
def delete_recurring_expense_route(id):
    """Delete (deactivate) a recurring expense"""
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))

    recurring = get_recurring_expense_by_id(id, session["user_id"])
    if recurring is None:
        abort(404)

    delete_recurring_expense(id, session["user_id"])

    flash("Recurring expense deleted.", "success")
    return redirect(url_for("expenses.list_recurring_expenses"))