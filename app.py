from flask import Flask, render_template, session, redirect, url_for, flash
from database.db import init_db, get_db, seed_db

from routes.auth import auth_bp
from routes.expenses import expense_bp
from routes.budget import budget_bp

from database.queries import (
    get_recent_transactions,
    get_summary_stats,
    get_category_breakdown
)

app = Flask(__name__)
app.secret_key = "dev-secret-key"

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
    
    # ✨ NEW: Get date filter if provided
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")
    
    # ✨ NEW: Get anomalies data
    transactions = get_recent_transactions(session["user_id"], limit=50, 
                                           date_from=date_from, date_to=date_to)
    
    # ✨ NEW: Get summary stats
    stats = get_summary_stats(session["user_id"], date_from=date_from, 
                              date_to=date_to)
    
    # ✨ NEW: Get category breakdown
    category_breakdown = get_category_breakdown(session["user_id"], 
                                                date_from=date_from, date_to=date_to)
    
    # ✨ NEW: Filter anomalies
    anomalies = [t for t in transactions if t["is_anomaly"]]
    
    # ✨ NEW: Pass data to template
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
        LIMIT 5
    """, (session["user_id"],)).fetchall()

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

    # Convert budgets → dict (SAFE)
    budgets = {row[0]: row[1] for row in rows}

    # Chart data
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
        chart_values=chart_values
    )


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
    app.run(debug=True, port=5001)
