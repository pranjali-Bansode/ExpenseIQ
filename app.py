import calendar
from datetime import date, datetime

from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from database.db import init_db, seed_db
from database.queries import (
    get_category_breakdown,
    get_recent_transactions,
    get_summary_stats,
    get_user_by_id,
)

from routes.auth import auth_bp
from routes.expenses import expense_bp

app = Flask(__name__)
app.secret_key = "dev-secret-key"

# ✅ Register Blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(expense_bp)

# Categories (used in templates if needed)
CATEGORIES = [
    "Food",
    "Transport",
    "Bills",
    "Health",
    "Entertainment",
    "Shopping",
    "Other",
]

# Initialize DB
with app.app_context():
    init_db()
    seed_db()


# ---------------------- Helper Functions ---------------------- #

def _parse_date(val):
    try:
        datetime.strptime(val, "%Y-%m-%d")
        return val
    except (ValueError, TypeError):
        return None


def _months_ago(today, n):
    m, y = today.month - n, today.year
    while m <= 0:
        m += 12
        y -= 1
    return date(y, m, 1).isoformat()


# ---------------------- Routes ---------------------- #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))

    uid = session["user_id"]
    today = date.today()

    date_from = _parse_date(request.args.get("date_from"))
    date_to = _parse_date(request.args.get("date_to"))

    if date_from and date_to and date_from > date_to:
        flash("Start date must be before end date.", "error")
        date_from = date_to = None

    today_str = today.isoformat()
    this_month_from = today.replace(day=1).isoformat()
    this_month_to = today.replace(
        day=calendar.monthrange(today.year, today.month)[1]
    ).isoformat()

    presets = {
        "this_month": {"date_from": this_month_from, "date_to": this_month_to},
        "last_3": {"date_from": _months_ago(today, 3), "date_to": today_str},
        "last_6": {"date_from": _months_ago(today, 6), "date_to": today_str},
    }

    return render_template(
        "profile.html",
        user=get_user_by_id(uid),
        stats=get_summary_stats(uid, date_from, date_to),
        expenses=get_recent_transactions(uid, date_from=date_from, date_to=date_to),
        categories=get_category_breakdown(uid, date_from, date_to),
        date_from=date_from,
        date_to=date_to,
        presets=presets,
    )


@app.route("/analytics")
def analytics():
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))
    return render_template("analytics.html")


# ---------------------- Run Server ---------------------- #

if __name__ == "__main__":
    app.run(debug=True, port=5001)