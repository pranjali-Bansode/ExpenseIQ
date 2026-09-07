"""
Alert service: email delivery + budget/anomaly detection helpers.

EMAIL DELIVERY: SendGrid Web API only.
Resend and Gmail SMTP fallback have been removed - Render's network is
IPv4-only and Gmail's SMTP frequently blocks/challenges logins from
datacenter IPs, so an HTTP-based provider (SendGrid) is the reliable path
for a PaaS like Render. This mirrors services/email_service.py, which
uses the same provider and env vars.

WHAT TO SET IN RENDER (Dashboard -> your service -> Environment, or in
render.yaml with `sync: false` placeholders):
    SENDGRID_API_KEY   (from app.sendgrid.com/settings/api_keys)
    FROM_EMAIL         (must be a verified sender - see
                        Settings > Sender Authentication in SendGrid)
"""

import os

import requests

from database.queries import (
    get_budget,
    get_total_expense_for_category,
    get_category_average,
)

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
FROM_EMAIL = os.getenv("FROM_EMAIL")

SENDGRID_API_URL = "https://api.sendgrid.com/v3/mail/send"


# ==============================
# 📧 EMAIL: SENDGRID HTTP API
# ==============================
def _send_via_sendgrid(to_email, subject, message):
    if not SENDGRID_API_KEY:
        return False, "SENDGRID_API_KEY not set in environment variables"
    if not FROM_EMAIL:
        return False, "FROM_EMAIL not set in environment variables"

    payload = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": FROM_EMAIL},
        "subject": subject,
        "content": [
            # SendGrid requires a text/plain part alongside text/html.
            {"type": "text/plain", "value": message},
            {"type": "text/html", "value": message},
        ],
    }
    headers = {
        "Authorization": f"Bearer {SENDGRID_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        resp = requests.post(
            SENDGRID_API_URL, json=payload, headers=headers, timeout=10
        )
    except requests.RequestException as e:
        return False, f"SendGrid request failed: {str(e)}"

    if resp.status_code == 202:
        return True, None

    return False, f"SendGrid API error {resp.status_code}: {resp.text[:300]}"


# ==============================
# 📧 PUBLIC ENTRY POINT
# ==============================
def send_email(to_email, subject, message):
    """
    Send an alert email via SendGrid.

    Returns:
        (success: bool, error_message: str or None)
    """
    if not to_email:
        return False, "No email provided"

    return _send_via_sendgrid(to_email, subject, message)


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
def detect_anomaly(user_id, category, amount, exclude_expense_id=None, min_history=3):
    """
    Flag an expense as anomalous if it's more than 2x the user's own
    historical average for that category.

    `min_history` guards against false positives/negatives on categories
    with very little data: with only 1-2 past expenses, "2x average" is
    not statistically meaningful (e.g. a single ₹200 expense makes any
    ₹401+ expense "anomalous"). Below this many prior expenses, the
    function simply doesn't raise an anomaly yet.
    """
    avg, count = get_category_average(
        user_id,
        category,
        exclude_expense_id=exclude_expense_id,
        return_count=True,
    )

    if not avg or count < min_history:
        return None

    if amount > 2 * avg:
        return f"🚨 Unusual spending detected! ₹{amount:,.2f} vs avg ₹{avg:,.2f}"

    return None