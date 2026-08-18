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


# =========================================================
# 🔥 ANOMALY DETECTION FEATURE (UPDATED FUNCTION)
# =========================================================

def get_recent_transactions(user_id, limit=10, date_from=None, date_to=None):
    date_clause, date_params = _build_date_filter(date_from, date_to)
    params = [user_id] + date_params + [limit]

    conn = get_db()

    # 1️⃣ Get category averages
    avg_rows = conn.execute(
        "SELECT category, AVG(amount) as avg_amount "
        "FROM expenses WHERE user_id = ? GROUP BY category",
        (user_id,)
    ).fetchall()

    category_avg = {
        row["category"]: row["avg_amount"] for row in avg_rows
    }

    # 2️⃣ Get transactions
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

        # 🔥 anomaly logic
        is_anomaly = avg > 0 and amount > (2 * avg)

        result.append({
            "id": row["id"],
            "date": datetime.strptime(row["date"], "%Y-%m-%d").strftime("%d %b %Y"),
            "description": row["description"],
            "category": category,
            "amount": "{:,.2f}".format(amount),
            "is_anomaly": is_anomaly
        })

    # ✅ DEBUG (safe and correct)
    print("ANOMALY DATA:")
    for r in result:
        print(r["description"], r["amount"], r["is_anomaly"])

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