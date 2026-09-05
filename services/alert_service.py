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
# 🔑 ENV VARIABLES WITH DEBUGGING
# ==============================
GMAIL_EMAIL = os.getenv("GMAIL_EMAIL")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

# Debug: Print what we got
print(f"DEBUG: GMAIL_EMAIL = {GMAIL_EMAIL}")
print(f"DEBUG: GMAIL_APP_PASSWORD = {'*' * len(GMAIL_APP_PASSWORD) if GMAIL_APP_PASSWORD else 'NOT SET'}")


# ==============================
# 📧 EMAIL FUNCTION (GMAIL SMTP) - WITH DETAILED LOGGING
# ==============================
def send_email(to_email, subject, message):
    """
    Send email using Gmail SMTP (production safe)

    Returns:
        (success: bool, error_message: str or None)
    """
    print(f"\n📧 [EMAIL DEBUG] Attempting to send email to: {to_email}")
    print(f"📧 [EMAIL DEBUG] Subject: {subject}")
    
    if not to_email:
        print("❌ [EMAIL DEBUG] No email provided")
        return False, "No email provided"

    if not GMAIL_EMAIL:
        error_msg = "GMAIL_EMAIL not set in environment variables"
        print(f"❌ [EMAIL DEBUG] {error_msg}")
        return False, error_msg

    if not GMAIL_APP_PASSWORD:
        error_msg = "GMAIL_APP_PASSWORD not set in environment variables"
        print(f"❌ [EMAIL DEBUG] {error_msg}")
        return False, error_msg

    try:
        print(f"📧 [EMAIL DEBUG] Creating email message...")
        # Create email
        msg = MIMEMultipart()
        msg["From"] = GMAIL_EMAIL
        msg["To"] = to_email
        msg["Subject"] = subject

        # Add HTML body
        msg.attach(MIMEText(message, "html"))

        print(f"📧 [EMAIL DEBUG] Connecting to Gmail SMTP server...")
        # Send via Gmail SMTP
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            print(f"📧 [EMAIL DEBUG] Connected to SMTP server")
            
            print(f"📧 [EMAIL DEBUG] Attempting login with email: {GMAIL_EMAIL}")
            server.login(GMAIL_EMAIL, GMAIL_APP_PASSWORD)
            print(f"✅ [EMAIL DEBUG] Login successful!")
            
            print(f"📧 [EMAIL DEBUG] Sending message...")
            server.send_message(msg)
            print(f"✅ [EMAIL DEBUG] Message sent successfully!")

        print(f"✅ EMAIL SENT → {to_email}")
        return True, None

    except smtplib.SMTPAuthenticationError as e:
        error_msg = f"Gmail authentication failed. Check GMAIL_EMAIL and GMAIL_APP_PASSWORD. Error: {str(e)}"
        print(f"❌ [EMAIL DEBUG] {error_msg}")
        return False, error_msg

    except smtplib.SMTPException as e:
        error_msg = f"SMTP error: {str(e)}"
        print(f"❌ [EMAIL DEBUG] {error_msg}")
        return False, error_msg

    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        print(f"❌ [EMAIL DEBUG] {error_msg}")
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
