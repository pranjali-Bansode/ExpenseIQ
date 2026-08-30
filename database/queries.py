from datetime import datetime
from database.db import get_db


def get_expense_by_id(expense_id, user_id):
    conn = get_db()
    row = conn.execute(
        "SELECT id, amount, category, date, description "
        "FROM expenses WHERE id = ? AND user_id = ?",
        (expense_id, user_id),
    ).fetchone()
    conn.close()

    if row is None:
        return None

    return {
        "id": row["id"],
        "amount": row["amount"],
        "category": row["category"],
        "date": row["date"],
        "description": row["description"] or "",
    }


def update_expense(expense_id, user_id, amount, category, expense_date, description):
    conn = get_db()
    conn.execute(
        "UPDATE expenses SET amount = ?, category = ?, date = ?, description = ? "
        "WHERE id = ? AND user_id = ?",
        (amount, category, expense_date, description or None, expense_id, user_id),
    )
    conn.commit()
    conn.close()


def delete_expense_by_id(expense_id, user_id):
    conn = get_db()
    conn.execute(
        "DELETE FROM expenses WHERE id = ? AND user_id = ?",
        (expense_id, user_id),
    )
    conn.commit()
    conn.close()


def insert_expense(user_id, amount, category, expense_date, description):
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO expenses (user_id, amount, category, date, description)"
        " VALUES (?, ?, ?, ?, ?)",
        (user_id, amount, category, expense_date, description or None),
    )
    conn.commit()
    expense_id = cursor.lastrowid
    conn.close()
    return expense_id

def get_category_average(user_id, category, exclude_expense_id=None):
    conn = get_db()
    row = conn.execute(
        "SELECT AVG(amount) as avg_amount FROM expenses "
        "WHERE user_id = ? AND category = ?",
        (user_id, category),
    ).fetchone()
    conn.close()
    return row["avg_amount"] or 0


def _build_date_filter(date_from, date_to):
    if date_from and date_to:
        return "AND date BETWEEN ? AND ?", [date_from, date_to]
    return "", []


def get_user_by_id(user_id):
    conn = get_db()
    row = conn.execute(
        "SELECT id, name, email, created_at FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    conn.close()

    if row is None:
        return None

    name = row["name"]
    initials = "".join(w[0].upper() for w in name.split() if w)
    member_since = datetime.strptime(
        row["created_at"], "%Y-%m-%d %H:%M:%S"
    ).strftime("%B %Y")

    return {
        "name": name,
        "email": row["email"],
        "initials": initials,
        "member_since": member_since,
    }


# =======================
# 🔥 ANOMALY DETECTION
# =======================

def get_recent_transactions(user_id, limit=10, date_from=None, date_to=None):
    date_clause, date_params = _build_date_filter(date_from, date_to)
    params = [user_id] + date_params + [limit]

    conn = get_db()

    avg_rows = conn.execute(
        "SELECT category, AVG(amount) as avg_amount "
        "FROM expenses WHERE user_id = ? GROUP BY category",
        (user_id,)
    ).fetchall()

    category_avg = {
        row["category"]: row["avg_amount"] for row in avg_rows
    }

    rows = conn.execute(
        "SELECT id, date, description, category, amount "
        "FROM expenses "
        "WHERE user_id = ? " + date_clause +
        " ORDER BY date DESC, id DESC LIMIT ?",
        params,
    ).fetchall()

    conn.close()

    result = []

    for row in rows:
        amount = row["amount"]
        category = row["category"]
        avg = category_avg.get(category, 0)

        is_anomaly = avg > 0 and amount > (2 * avg)

        result.append({
            "id": row["id"],
            "date": datetime.strptime(row["date"], "%Y-%m-%d").strftime("%d %b %Y"),
            "description": row["description"],
            "category": category,
            "amount": "{:,.2f}".format(amount),
            "is_anomaly": is_anomaly
        })

    return result


def get_summary_stats(user_id, date_from=None, date_to=None):
    date_clause, date_params = _build_date_filter(date_from, date_to)
    params = [user_id] + date_params

    conn = get_db()
    row = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS count "
        "FROM expenses WHERE user_id = ? " + date_clause,
        params,
    ).fetchone()

    cat_row = conn.execute(
        "SELECT category FROM expenses WHERE user_id = ? "
        + date_clause +
        " GROUP BY category ORDER BY SUM(amount) DESC LIMIT 1",
        params,
    ).fetchone()

    conn.close()

    return {
        "total": "{:,.2f}".format(row["total"]),
        "count": row["count"],
        "top_category": cat_row["category"] if cat_row else "—",
    }


def get_category_breakdown(user_id, date_from=None, date_to=None):
    date_clause, date_params = _build_date_filter(date_from, date_to)
    params = [user_id] + date_params

    conn = get_db()
    rows = conn.execute(
        "SELECT category AS name, SUM(amount) AS total "
        "FROM expenses "
        "WHERE user_id = ? " + date_clause +
        " GROUP BY category ORDER BY total DESC",
        params,
    ).fetchall()

    conn.close()

    grand_total = sum(r["total"] for r in rows)

    if grand_total == 0:
        return []

    pcts = [int(r["total"] / grand_total * 100) for r in rows]
    pcts[0] += 100 - sum(pcts)

    return [
        {
            "name": r["name"],
            "amount": "{:,.2f}".format(r["total"]),
            "percent": pct,
        }
        for r, pct in zip(rows, pcts)
    ]


# =======================
# 💰 BUDGET FUNCTIONS
# =======================

def set_budget(user_id, category, amount, month):
    conn = get_db()
    conn.execute(
        """
        INSERT INTO budgets (user_id, category, amount, month)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id, category, month)
        DO UPDATE SET amount = excluded.amount
        """,
        (user_id, category, amount, month),
    )
    conn.commit()
    conn.close()


def get_budget(user_id, category, month):
    conn = get_db()
    row = conn.execute(
        "SELECT amount FROM budgets WHERE user_id=? AND category=? AND month=?",
        (user_id, category, month),
    ).fetchone()
    conn.close()
    return row["amount"] if row else None

def get_all_budgets(user_id, month):
    conn = get_db()
    rows = conn.execute(
        "SELECT category, amount FROM budgets WHERE user_id=? AND month=?",
        (user_id, month),
    ).fetchall()
    conn.close()

    return {row["category"]: row["amount"] for row in rows}

def get_total_expense_for_category(user_id, category, month):
    conn = get_db()
    row = conn.execute(
        """
        SELECT COALESCE(SUM(amount), 0) as total
        FROM expenses
        WHERE user_id=? AND category=? AND strftime('%Y-%m', date)=?
        """,
        (user_id, category, month),
    ).fetchone()
    conn.close()
    return row["total"]

def get_user_budgets(user_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT category, amount, month FROM budgets WHERE user_id=? ORDER BY month DESC",
        (user_id,)
    ).fetchall()
    conn.close()

    return [
        {
            "category": r["category"],
            "amount": r["amount"],
            "month": r["month"]
        }
        for r in rows
    ]
def delete_budget(user_id, category, month):
    conn = get_db()
    conn.execute(
        "DELETE FROM budgets WHERE user_id=? AND category=? AND month=?",
        (user_id, category, month),
    )
    conn.commit()
    conn.close()

    # =======================
# 📊 EXPENSE TRENDS - ADD TO database/queries.py
# Location: Add at the END of database/queries.py (after line 286)
# =======================

def get_monthly_trend_data(user_id, months=6):
    """Get last N months of spending data grouped by month and category"""
    conn = get_db()
    
    rows = conn.execute("""
        SELECT 
            strftime('%Y-%m', date) AS month,
            category,
            SUM(amount) as monthly_total,
            COUNT(*) as transaction_count,
            AVG(amount) as avg_amount
        FROM expenses
        WHERE user_id = ?
        GROUP BY strftime('%Y-%m', date), category
        ORDER BY month DESC
        LIMIT ?
    """, (user_id, months * 10)).fetchall()
    
    conn.close()
    
    # Organize by month
    trend_data = {}
    for row in rows:
        month = row["month"]
        if month not in trend_data:
            trend_data[month] = []
        
        trend_data[month].append({
            "category": row["category"],
            "monthly_total": "{:,.2f}".format(row["monthly_total"]),
            "transaction_count": row["transaction_count"],
            "avg_amount": "{:,.2f}".format(row["avg_amount"])
        })
    
    return trend_data


def get_month_over_month_comparison(user_id, current_month, previous_month):
    """Compare spending between two months"""
    conn = get_db()
    
    # Current month data
    current_data = conn.execute("""
        SELECT 
            category,
            SUM(amount) as total
        FROM expenses
        WHERE user_id = ? AND strftime('%Y-%m', date) = ?
        GROUP BY category
    """, (user_id, current_month)).fetchall()
    
    # Previous month data
    previous_data = conn.execute("""
        SELECT 
            category,
            SUM(amount) as total
        FROM expenses
        WHERE user_id = ? AND strftime('%Y-%m', date) = ?
        GROUP BY category
    """, (user_id, previous_month)).fetchall()
    
    conn.close()
    
    # Create dictionaries for easy lookup
    current_dict = {row["category"]: row["total"] for row in current_data}
    previous_dict = {row["category"]: row["total"] for row in previous_data}
    
    # Get all categories
    all_categories = set(current_dict.keys()) | set(previous_dict.keys())
    
    # Calculate comparison
    comparison = []
    for category in sorted(all_categories):
        curr = current_dict.get(category, 0)
        prev = previous_dict.get(category, 0)
        
        # Calculate percentage change
        if prev > 0:
            percent_change = ((curr - prev) / prev) * 100
        else:
            percent_change = 100 if curr > 0 else 0
        
        comparison.append({
            "category": category,
            "current_month": "{:,.2f}".format(curr),
            "previous_month": "{:,.2f}".format(prev),
            "percent_change": round(percent_change, 2),
            "status": "increase" if percent_change > 0 else "decrease"
        })
    
    return comparison


def get_category_trend_over_time(user_id, category, months=6):
    """Get spending trend for a specific category over time"""
    conn = get_db()
    
    rows = conn.execute("""
        SELECT 
            strftime('%Y-%m', date) AS month,
            SUM(amount) as total,
            COUNT(*) as count,
            AVG(amount) as avg_amount,
            MAX(amount) as max_amount,
            MIN(amount) as min_amount
        FROM expenses
        WHERE user_id = ? AND category = ?
        GROUP BY strftime('%Y-%m', date)
        ORDER BY month DESC
        LIMIT ?
    """, (user_id, category, months)).fetchall()
    
    conn.close()
    
    trend = []
    for row in rows:
        trend.append({
            "month": row["month"],
            "total": "{:,.2f}".format(row["total"]),
            "count": row["count"],
            "avg_amount": "{:,.2f}".format(row["avg_amount"]),
            "max_amount": "{:,.2f}".format(row["max_amount"]),
            "min_amount": "{:,.2f}".format(row["min_amount"])
        })
    
    return trend


def get_spending_velocity(user_id):
    """Calculate how fast user is spending (daily average)"""
    conn = get_db()
    
    # Get data for last 30 days
    result = conn.execute("""
        SELECT 
            COUNT(DISTINCT DATE(date)) as days_with_spending,
            SUM(amount) as total_spent,
            COUNT(*) as transaction_count,
            AVG(amount) as avg_per_transaction
        FROM expenses
        WHERE user_id = ? AND date >= DATE('now', '-30 days')
    """, (user_id,)).fetchone()
    
    conn.close()
    
    days_with_spending = result["days_with_spending"] or 0
    total_spent = result["total_spent"] or 0
    transaction_count = result["transaction_count"] or 0
    avg_per_transaction = result["avg_per_transaction"] or 0
    
    # Calculate daily average
    daily_avg = total_spent / 30 if total_spent > 0 else 0
    
    return {
        "total_spent_30_days": "{:,.2f}".format(total_spent),
        "daily_average": "{:,.2f}".format(daily_avg),
        "days_with_spending": days_with_spending,
        "transaction_count": transaction_count,
        "avg_per_transaction": "{:,.2f}".format(avg_per_transaction)
    }
