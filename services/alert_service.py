import requests
import os
from database.queries import (
    get_budget,
    get_total_expense_for_category,
    get_category_average,
)

# ==============================
# 🔑 ENV VARIABLES
# ==============================
RESEND_API_KEY = os.getenv("RESEND_API_KEY")


# ==============================
# 📧 EMAIL FUNCTION (RESEND API)
# ==============================
def send_email(to_email, subject, message):
    """
    Send email using Resend API (production safe)

    Returns:
        (success: bool, error_message: str or None)
    """
    if not to_email:
        return False, "No email provided"

    try:
        response = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "from": "onboarding@resend.dev",  # default test sender
                "to": [to_email],
                "subject": subject,
                "html": message,
            },
            timeout=10
        )

        if response.status_code in [200, 201]:
            print(f"✅ EMAIL SENT → {to_email}")
            return True, None
        else:
            error_msg = f"Resend error: {response.text}"
            print(f"❌ {error_msg}")
            return False, error_msg

    except requests.exceptions.Timeout:
        return False, "Request timed out"

    except requests.exceptions.ConnectionError:
        return False, "Network error (check internet or hosting)"

    except Exception as e:
        return False, f"Unexpected error: {str(e)}"


# ==============================
# 🚨 BUDGET ALERT
# ==============================
def check_budget_alert(user_id, category, month):
    budget_amount = get_budget(user_id, category, month)

    if not budget_amount:
        return None

    total = get_total_expense_for_category(user_id, category, month)

    if total >= budget_amount:
        return f"⚠️ Budget exceeded for {category}! Spent ₹{total:,.2f}/₹{budget_amount:,.2f}"

    elif total >= 0.8 * budget_amount:
        return f"⚡ 80% budget reached for {category}! ₹{total:,.2f}/₹{budget_amount:,.2f}"

    return None


# ==============================
# 🚨 ANOMALY DETECTION
# ==============================
def detect_anomaly(user_id, category, amount, exclude_expense_id=None):
    avg = get_category_average(
        user_id,
        category,
        exclude_expense_id=exclude_expense_id
    )

    if avg and amount > 2 * avg:
        return f"🚨 Unusual spending detected! ₹{amount:,.2f} vs avg ₹{avg:,.2f}"

    return None