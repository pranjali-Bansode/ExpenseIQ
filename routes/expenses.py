from flask import Blueprint, render_template, request, redirect, url_for, flash, session, abort, jsonify
from datetime import date, datetime
from database.db import get_db
from database.queries import (
    insert_expense,
    get_expense_by_id,
    update_expense,
    delete_expense_by_id,
    get_budget,
    get_total_expense_for_category,
    get_category_average
)

from services.ocr_service import parse_receipt, allowed_file

# ✅ Alert service for budget and anomaly detection
from services.alert_service import (
    check_budget_alert,
    detect_anomaly,
    send_email,
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


# =======================
# ADD EXPENSE
# =======================
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

        # ================= VALIDATION ================= #
        try:
            amount = float(amount_raw)
            if amount <= 0:
                raise ValueError
        except ValueError:
            flash("Amount must be a positive number.", "error")
            return render_template("add_expense.html", categories=CATEGORIES, today=today, form=request.form)

        if category not in CATEGORIES:
            flash("Invalid category.", "error")
            return render_template("add_expense.html", categories=CATEGORIES, today=today, form=request.form)

        if not _parse_date(expense_date):
            flash("Invalid date.", "error")
            return render_template("add_expense.html", categories=CATEGORIES, today=today, form=request.form)

        user_id = session["user_id"]
        user_email = session.get("user_email")
        user_phone = session.get("user_phone")

        # ================= INSERT EXPENSE ================= #
        expense_id = insert_expense(user_id, amount, category, expense_date, description)

        # ================= ALERT SYSTEM ================= #
        month = expense_date[:7]  # "YYYY-MM" from the expense's own date
        alert1 = check_budget_alert(user_id, category, month)
        alert2 = detect_anomaly(user_id, category, amount, exclude_expense_id=expense_id)

        alert_message = alert1 or alert2

        if alert_message:
            flash(alert_message, "warning")

            # ✅ Send email if available and handle errors properly
            if user_email:
                try:
                    success, error_msg = send_email(
                        user_email, 
                        "ExpenseIQ Alert 🚨", 
                        alert_message
                    )
                    
                    # Inform user if email failed (but don't prevent expense creation)
                    if not success:
                        error_detail = error_msg if error_msg else "Could not send email notification"
                        flash(
                            f"⚠️ Alert created but email not sent: {error_detail}",
                            "info"
                        )
                except Exception as e:
                    # Catch any unexpected errors from send_email
                    print(f"❌ Unexpected error in email sending: {str(e)}")
                    flash(
                        "⚠️ Alert created but email notification failed",
                        "info"
                    )

        flash("Expense added successfully.", "success")
        return redirect(url_for("profile"))

    return render_template("add_expense.html", categories=CATEGORIES, today=today, form={})


# =======================
# OCR RECEIPT SCAN
# =======================
@expense_bp.route("/expenses/scan-receipt", methods=["POST"])
def scan_receipt():
    if not session.get("user_id"):
        return jsonify({"error": "unauthorized"}), 401

    file = request.files.get("receipt")

    if not file or file.filename == "":
        return jsonify({"error": "No file uploaded."}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "Unsupported file type."}), 400

    try:
        result = parse_receipt(file)
    except Exception as e:
        return jsonify({"error": f"OCR failed: {str(e)}"}), 500

    if result["category"] not in CATEGORIES:
        result["category"] = "Other"

    return jsonify(result), 200


# =======================
# EDIT EXPENSE
# =======================
@expense_bp.route("/expenses/<int:id>/edit", methods=["GET", "POST"])
def edit_expense(id):
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))

    expense = get_expense_by_id(id, session["user_id"])
    if expense is None:
        abort(404)

    if request.method == "GET":
        return render_template("edit_expense.html", expense=expense, categories=CATEGORIES, form={})

    amount = float(request.form.get("amount"))
    category = request.form.get("category")
    expense_date = request.form.get("date")
    description = request.form.get("description")

    update_expense(id, session["user_id"], amount, category, expense_date, description)

    flash("Updated successfully.", "success")
    return redirect(url_for("profile"))


# =======================
# DELETE EXPENSE
# =======================
@expense_bp.route("/expenses/<int:id>/delete", methods=["POST"])
def delete_expense(id):
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))

    delete_expense_by_id(id, session["user_id"])

    flash("Deleted successfully.", "success")
    return redirect(url_for("profile"))


# =======================
# RECURRING EXPENSES
# =======================
@expense_bp.route("/expenses/recurring")
def list_recurring_expenses():
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))

    # For now simple page (you can enhance later)
    return render_template("recurring_expenses.html")
