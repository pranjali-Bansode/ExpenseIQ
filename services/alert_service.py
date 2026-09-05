"""
Alert service: email delivery + budget/anomaly detection helpers.

WHY EMAIL WASN'T SENDING (most likely cause):
Your local `.env` has real GMAIL_EMAIL / GMAIL_APP_PASSWORD values, but
`.env` is correctly listed in `.gitignore` -> it is NOT committed to git ->
Render never sees that file. Unless you also add those two variables in
the Render dashboard (Service -> Environment) or in render.yaml, Render's
process starts with GMAIL_EMAIL / GMAIL_APP_PASSWORD unset, so
`send_email()` always short-circuits at the "not set in environment
variables" check below and nothing is ever sent. This is the single most
common cause of "emails work locally, not in production" for Flask+Render.

A SECOND likely cause, even after the env vars are set correctly on
Render: Google frequently blocks or challenges SMTP logins that originate
from datacenter/cloud IP ranges (which is exactly what Render's outbound
IPs are), even with a correct app password. You may see
SMTPAuthenticationError or a "sign-in attempt blocked" style failure that
never happens from your home network. This is why this rewrite adds
Resend's HTTP API as the primary path - HTTP calls over 443 are not
subject to Gmail's SMTP heuristics and are the standard fix for
"transactional email from a PaaS" problems.

WHAT TO SET IN RENDER (Dashboard -> your service -> Environment, or in
render.yaml with `sync: false` placeholders):
    RESEND_API_KEY       (recommended - from resend.com, free tier available)
    ALERT_FROM_EMAIL     (a verified sender, e.g. alerts@yourdomain.com,
                          or Resend's onboarding@resend.dev for testing)
    GMAIL_EMAIL           (fallback only)
    GMAIL_APP_PASSWORD    (fallback only - 16-char app password, no spaces
                          needed either way, but strip them if you paste
                          them back in)
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import requests

from database.queries import (
    get_budget,
    get_total_expense_for_category,
    get_category_average,
)

RESEND_API_KEY = os.getenv("RESEND_API_KEY")
ALERT_FROM_EMAIL = os.getenv("ALERT_FROM_EMAIL", "onboarding@resend.dev")

GMAIL_EMAIL = os.getenv("GMAIL_EMAIL")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")


# ==============================
# 📧 EMAIL: RESEND HTTP API (preferred on Render)
# ==============================
def _send_via_resend(to_email, subject, message):
    if not RESEND_API_KEY:
        return False, "RESEND_API_KEY not set in environment variables"

    try:
        resp = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "from": ALERT_FROM_EMAIL,
                "to": [to_email],
                "subject": subject,
                "html": message,
            },
            timeout=10,
        )
    except requests.RequestException as e:
        return False, f"Resend request failed: {str(e)}"

    if resp.status_code in (200, 201):
        return True, None

    return False, f"Resend API error {resp.status_code}: {resp.text[:300]}"


# ==============================
# 📧 EMAIL: GMAIL SMTP (fallback / local dev)
# ==============================
def _send_via_gmail_smtp(to_email, subject, message):
    if not GMAIL_EMAIL:
        return False, "GMAIL_EMAIL not set in environment variables"
    if not GMAIL_APP_PASSWORD:
        return False, "GMAIL_APP_PASSWORD not set in environment variables"

    try:
        msg = MIMEMultipart()
        msg["From"] = GMAIL_EMAIL
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(message, "html"))

        # App passwords work with or without the display spaces, but
        # stripping them avoids edge cases with some SMTP client versions.
        app_password = GMAIL_APP_PASSWORD.replace(" ", "")

        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as server:
            server.login(GMAIL_EMAIL, app_password)
            server.send_message(msg)

        return True, None

    except smtplib.SMTPAuthenticationError as e:
        return False, (
            "Gmail authentication failed. Check GMAIL_EMAIL/GMAIL_APP_PASSWORD, "
            f"and note Gmail sometimes blocks sign-ins from cloud IPs like Render's. Error: {str(e)}"
        )
    except smtplib.SMTPException as e:
        return False, f"SMTP error: {str(e)}"
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"


# ==============================
# 📧 PUBLIC ENTRY POINT
# ==============================
def send_email(to_email, subject, message):
    """
    Send an alert email. Tries Resend's HTTP API first (recommended for
    Render/production); falls back to Gmail SMTP if Resend isn't
    configured. This mirrors the "SMTP/Resend API" plan from your project
    description.

    Returns:
        (success: bool, error_message: str or None)
    """
    if not to_email:
        return False, "No email provided"

    if RESEND_API_KEY:
        success, error = _send_via_resend(to_email, subject, message)
        if success:
            return True, None
        # fall through to SMTP fallback, but surface the Resend error if
        # SMTP also fails
        smtp_success, smtp_error = _send_via_gmail_smtp(to_email, subject, message)
        if smtp_success:
            return True, None
        return False, f"Resend failed ({error}); SMTP fallback failed ({smtp_error})"

    return _send_via_gmail_smtp(to_email, subject, message)


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
