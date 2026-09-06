import os
from datetime import datetime as _datetime, timedelta

from dotenv import load_dotenv
from flask import (
    Flask, render_template, session, redirect, url_for, flash,
    request, jsonify, send_file,
)

from database.db import init_db, get_db, seed_db, update_user_phone
from database.queries import (
    get_recent_transactions,
    get_summary_stats,
    get_category_breakdown,
    get_monthly_trend_data,
    get_month_over_month_comparison,
    get_category_trend_over_time,
    get_spending_velocity,
    get_category_average,
    get_spending_alerts,
    get_all_expenses,
    get_all_budgets,
    get_user_by_id,
    process_recurring_expenses,
)
from routes.auth import auth_bp
from routes.expenses import expense_bp
from routes.budget import budget_bp
from services.report_service import generate_expense_report_pdf

load_dotenv()

app = Flask(__name__)
# Read from env (set in Render dashboard); falls back to a dev-only value
# so local `flask run` still works without a .env file.
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-do-not-use-in-prod")

# Register Blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(expense_bp)
app.register_blueprint(budget_bp)

# Categories
CATEGORIES = [
    "Food", "Transport", "Shopping",
    "Bills", "Health", "Entertainment", "Other"
]

# Initialize DB
init_db()
# Seed demo data if database is empty
seed_db()
process_recurring_expenses()  # Process recurring expenses on startup


# =======================
# LANDING
# =======================
@app.route("/")
def landing():
    if "user_id" in session:
        return redirect(url_for("profile"))
    return render_template("landing.html")


# =======================
# ANALYTICS
# =======================
@app.route("/analytics")
def analytics():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")

    transactions = get_recent_transactions(
        session["user_id"], limit=50, date_from=date_from, date_to=date_to
    )
    stats = get_summary_stats(session["user_id"], date_from=date_from, date_to=date_to)
    category_breakdown = get_category_breakdown(
        session["user_id"], date_from=date_from, date_to=date_to
    )
    anomalies = [t for t in transactions if t["is_anomaly"]]

    return render_template(
        "analytics.html",
        transactions=transactions,
        anomalies=anomalies,
        stats=stats,
        category_breakdown=category_breakdown,
        date_from=date_from,
        date_to=date_to
    )


# =======================
# EXPORT REPORT (PDF)
# =======================
@app.route("/export/report")
def export_report():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")

    user = get_user_by_id(session["user_id"])
    expenses = get_all_expenses(session["user_id"], date_from=date_from, date_to=date_to)
    stats = get_summary_stats(session["user_id"], date_from=date_from, date_to=date_to)
    category_breakdown = get_category_breakdown(
        session["user_id"], date_from=date_from, date_to=date_to
    )

    current_month = _datetime.now().strftime("%Y-%m")
    budgets = get_all_budgets(session["user_id"], current_month)

    pdf_buffer = generate_expense_report_pdf(
        user_name=user["name"] if user else "User",
        expenses=expenses,
        stats=stats,
        category_breakdown=category_breakdown,
        budgets=budgets,
        date_from=date_from,
        date_to=date_to,
    )

    filename = f"expenseiq_report_{_datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    return send_file(
        pdf_buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
    )


# =======================
# EXPENSE TRENDS & COMPARISON
# =======================
@app.route("/trends")
def trends():
    """Expense Trends & Comparison page"""
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    today = _datetime.now()
    current_month = today.strftime("%Y-%m")
    previous_month = (today.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")

    comparison = get_month_over_month_comparison(
        session["user_id"], current_month, previous_month
    )
    trend_data = get_monthly_trend_data(session["user_id"], months=6)
    velocity = get_spending_velocity(session["user_id"])

    selected_category = request.args.get("category", "Food")
    category_trend = get_category_trend_over_time(
        session["user_id"], selected_category, months=6
    )

    all_categories = list(set(
        cat for month_cats in trend_data.values()
        for cat in [c["category"] for c in month_cats]
    ))

    return render_template(
        "trends.html",
        comparison=comparison,
        trend_data=trend_data,
        velocity=velocity,
        category_trend=category_trend,
        selected_category=selected_category,
        all_categories=sorted(all_categories),
        current_month=current_month,
        previous_month=previous_month
    )


@app.route("/api/trends/category-data")
def trends_category_data():
    """Returns category trend data as JSON for trends.js to fetch."""
    if "user_id" not in session:
        return jsonify({"error": "unauthorized"}), 401

    category = request.args.get("category", "Food")
    category_trend = get_category_trend_over_time(session["user_id"], category, months=6)

    labels = [item["month"] for item in category_trend]
    data = [float(item["total"].replace(",", "")) for item in category_trend]

    return jsonify({"labels": labels, "data": data})


# =======================
# PROFILE DASHBOARD
# =======================
@app.route("/profile")
def profile():
    if "user_id" not in session:
        flash("Please login first!", "warning")
        return redirect(url_for("auth.login"))

    conn = get_db()

    # USER
    user = conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (session["user_id"],)
    ).fetchone()

    if user is None:
        conn.close()
        session.clear()
        flash("User profile not found. Please log in again.", "warning")
        return redirect(url_for("auth.login"))

    # SMART SPENDING ALERTS
    current_month = _datetime.now().strftime("%Y-%m")
    spending_alerts = get_spending_alerts(session["user_id"], current_month)

    # TOTAL EXPENSE
    total = conn.execute(
        "SELECT SUM(amount) FROM expenses WHERE user_id = ?",
        (session["user_id"],)
    ).fetchone()[0] or 0

    # RECENT EXPENSES
    expenses = conn.execute("""
        SELECT * FROM expenses
        WHERE user_id = ?
        ORDER BY date DESC
        LIMIT 20
    """, (session["user_id"],)).fetchall()

    # ANOMALY CHECK FOR RECENT TRANSACTIONS
    # NOTE: each expense's average EXCLUDES itself (same rule detect_anomaly()
    # uses when an expense is first added) and requires at least 3 prior
    # expenses in that category before flagging - otherwise a category's
    # very first expense trivially looks "anomalous" against itself, and a
    # second expense looks anomalous against an average of one data point.
    anomaly_ids = set()
    for e in expenses:
        avg, count = get_category_average(
            session["user_id"], e["category"],
            exclude_expense_id=e["id"], return_count=True,
        )
        if avg and count >= 3 and e["amount"] > 2 * avg:
            anomaly_ids.add(e["id"])

    # CATEGORY BREAKDOWN
    category_data = conn.execute("""
        SELECT category, SUM(amount) as total
        FROM expenses
        WHERE user_id = ?
        GROUP BY category
    """, (session["user_id"],)).fetchall()

    # BUDGETS
    rows = conn.execute("""
        SELECT category, amount
        FROM budgets
        WHERE user_id = ?
    """, (session["user_id"],)).fetchall()

    conn.close()

    budgets = {row[0]: row[1] for row in rows}
    chart_labels = [row[0] for row in category_data]
    chart_values = [row[1] for row in category_data]

    return render_template(
        "profile.html",
        user=user,
        total=total,
        expenses=expenses,
        budgets=budgets,
        categories=CATEGORIES,
        chart_labels=chart_labels,
        chart_values=chart_values,
        anomaly_ids=anomaly_ids,
        spending_alerts=spending_alerts
    )


# =======================
# NOTIFICATION SETTINGS (phone number for SMS alerts)
# =======================
@app.route("/profile/notifications", methods=["POST"])
def update_notifications():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    phone = request.form.get("phone", "").strip()

    update_user_phone(session["user_id"], phone or None)
    session["user_phone"] = phone or None

    flash("Notification settings updated.", "success")
    return redirect(url_for("profile"))


# =======================
# LOGOUT
# =======================
@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully!", "success")
    return redirect(url_for("auth.login"))


# =======================
# RUN APP
# =======================
if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000))
    )