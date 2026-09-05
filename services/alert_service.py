import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from database.queries import (
    get_budget,
    get_total_expense_for_category,
    get_category_average,
)

# ==============================
# 🔑 ENV VARIABLES
# ==============================
GMAIL_EMAIL = os.getenv("GMAIL_EMAIL")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")


# ==============================
# 📧 EMAIL FUNCTION (GMAIL SMTP)
# ==============================
def send_email(to_email, subject, message):
    """
    Send email using Gmail SMTP (production safe)

    Returns:
        (success: bool, error_message: str or None)
    """
    if not to_email:
        return False, "No email provided"

    if not GMAIL_EMAIL or not GMAIL_APP_PASSWORD:
        print("⚠️ Gmail credentials not configured in .env")
        return False, "Email service not configured"

    try:
        # Create email
        msg = MIMEMultipart()
        msg["From"] = GMAIL_EMAIL
        msg["To"] = to_email
        msg["Subject"] = subject

        # Add HTML body
        msg.attach(MIMEText(message, "html"))

        # Send via Gmail SMTP
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_EMAIL, GMAIL_APP_PASSWORD)
            server.send_message(msg)

        print(f"✅ EMAIL SENT → {to_email}")
        return True, None

    except smtplib.SMTPAuthenticationError:
        error_msg = "Gmail authentication failed. Check GMAIL_EMAIL and GMAIL_APP_PASSWORD in .env"
        print(f"❌ {error_msg}")
        return False, error_msg

    except smtplib.SMTPException as e:
        error_msg = f"SMTP error: {str(e)}"
        print(f"❌ {error_msg}")
        return False, error_msg

    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        print(f"❌ {error_msg}")
        return False, error_msg


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
