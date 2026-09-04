import requests
import os
import smtplib
from email.mime.text import MIMEText

RESEND_API_KEY = os.getenv("RESEND_API_KEY")
from database.queries import (
    get_budget,
    get_total_expense_for_category,
    get_category_average,
)

# ==============================
# 📧 EMAIL FUNCTION (FIXED)
# ==============================
EMAIL = os.getenv("GMAIL_EMAIL", "pranjalib908@gmail.com")
APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "skhr ltsy vpwc upwx")


def send_email(to_email, subject, message):
    """
    Send email using Gmail SMTP
    
    Args:
        to_email: Recipient email address
        subject: Email subject
        message: Email body (supports HTML)
    
    Returns:
        tuple: (success: bool, error_message: str or None)
    """
    if not to_email:
        return False, "No email provided"

    try:
        msg = MIMEText(message, "html")
        msg["Subject"] = subject
        msg["From"] = EMAIL
        msg["To"] = to_email

        # Create SMTP connection with timeout
        server = smtplib.SMTP("smtp.gmail.com", 587, timeout=10)
        server.starttls()
        server.login(EMAIL, APP_PASSWORD)
        
        # Send the message
        server.send_message(msg)
        server.quit()

        print(f"✅ EMAIL SENT SUCCESSFULLY → {to_email}")
        return True, None

    except smtplib.SMTPAuthenticationError as e:
        error_msg = f"Email authentication failed. Please check your Gmail credentials."
        print(f"❌ {error_msg}: {str(e)}")
        return False, error_msg
    
    except smtplib.SMTPException as e:
        error_msg = f"SMTP server error: {str(e)}"
        print(f"❌ {error_msg}")
        return False, error_msg
    
    except ConnectionError as e:
        error_msg = f"Network connection error: {str(e)}"
        print(f"❌ {error_msg}")
        return False, error_msg
    
    except TimeoutError:
        error_msg = "Email server connection timed out"
        print(f"❌ {error_msg}")
        return False, error_msg
    
    except Exception as e:
        error_msg = f"Unexpected error sending email: {str(e)}"
        print(f"❌ {error_msg}")
        return False, error_msg


# ==============================
# 🚨 BUDGET ALERT
# ==============================
def check_budget_alert(user_id, category, month):
    """
    Check if spending has exceeded budget threshold
    
    Args:
        user_id: User ID
        category: Expense category
        month: Month in YYYY-MM format
    
    Returns:
        str: Alert message or None
    """
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
    """
    Detect unusual spending patterns
    
    Args:
        user_id: User ID
        category: Expense category
        amount: Current expense amount
        exclude_expense_id: Expense ID to exclude from average calculation
    
    Returns:
        str: Alert message or None
    """
    avg = get_category_average(
        user_id,
        category,
        exclude_expense_id=exclude_expense_id
    )

    if avg and amount > 2 * avg:
        return f"🚨 Unusual spending detected! ₹{amount:,.2f} vs avg ₹{avg:,.2f}"

    return None
