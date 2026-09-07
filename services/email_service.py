"""
services/email_service.py

Email sending via SendGrid Web API v3 (uses `requests`, no extra
dependency needed beyond what's already in requirements.txt).

Required environment variables (set these in Render's dashboard as
well as your local .env):
    SENDGRID_API_KEY   - your SendGrid API key
    FROM_EMAIL          - the verified "from" address in SendGrid
                           (Settings > Sender Authentication)

All functions return True on success, False on failure, and never
raise - callers can fire-and-forget these without wrapping in
try/except themselves.
"""

import os
import logging

import requests

logger = logging.getLogger(__name__)

SENDGRID_API_URL = "https://api.sendgrid.com/v3/mail/send"


def _send_via_sendgrid(to_email, subject, html_content, text_content, context=""):
    """
    Low-level helper that actually calls the SendGrid API.

    Args:
        to_email (str): Recipient email address
        subject (str): Email subject
        html_content (str): HTML body
        text_content (str): Plain-text fallback body
        context (str): Short label used in log messages, e.g. "budget_alert"

    Returns:
        bool: True if SendGrid accepted the message, False otherwise
    """
    if not to_email:
        logger.error(f"[{context}] Aborting send: to_email is None or empty")
        return False

    api_key = os.getenv("SENDGRID_API_KEY")
    from_email = os.getenv("FROM_EMAIL")

    if not api_key:
        logger.error(f"[{context}] SENDGRID_API_KEY is not set")
        return False
    if not from_email:
        logger.error(f"[{context}] FROM_EMAIL is not set")
        return False

    payload = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": from_email},
        "subject": subject,
        "content": [
            {"type": "text/plain", "value": text_content},
            {"type": "text/html", "value": html_content},
        ],
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            SENDGRID_API_URL, json=payload, headers=headers, timeout=10
        )
        # SendGrid returns 202 Accepted on success
        if response.status_code == 202:
            logger.info(f"[{context}] Email sent to {to_email}")
            return True

        logger.error(
            f"[{context}] SendGrid returned {response.status_code}: {response.text}"
        )
        return False

    except requests.exceptions.RequestException as e:
        logger.error(f"[{context}] Request to SendGrid failed: {str(e)}")
        return False


def send_budget_alert(user_email, budget_name, amount_limit, spent_amount):
    """
    Send email alert when user exceeds budget.

    Args:
        user_email (str): Recipient email address
        budget_name (str): Name of the budget
        amount_limit (float): Budget limit
        spent_amount (float): Amount spent
    """
    exceeded_by = spent_amount - amount_limit

    html_content = f"""
    <h2>Budget Alert</h2>
    <p>You have exceeded your budget!</p>
    <ul>
        <li><strong>Budget:</strong> {budget_name}</li>
        <li><strong>Limit:</strong> ₹{amount_limit}</li>
        <li><strong>Spent:</strong> ₹{spent_amount}</li>
        <li><strong>Exceeded by:</strong> ₹{exceeded_by}</li>
    </ul>
    <p>Please review your expenses in ExpenseIQ.</p>
    """
    text_content = (
        f"Budget Alert: You have exceeded {budget_name} budget. "
        f"Limit: {amount_limit}, Spent: {spent_amount}"
    )

    return _send_via_sendgrid(
        to_email=user_email,
        subject=f"⚠️ Budget Alert: {budget_name}",
        html_content=html_content,
        text_content=text_content,
        context="send_budget_alert",
    )


def send_registration_confirmation(user_email, username):
    """
    Send registration confirmation email.

    Args:
        user_email (str): Recipient email address
        username (str): User's username
    """
    html_content = f"""
    <h2>Welcome to ExpenseIQ, {username}!</h2>
    <p>Your account has been successfully created.</p>
    <p>You can now:</p>
    <ul>
        <li>Track your daily expenses</li>
        <li>Set and monitor budgets</li>
        <li>Scan receipts with OCR</li>
        <li>Get budget alerts</li>
    </ul>
    <p><a href="https://expenseiq-y2m4.onrender.com/login">Log in to ExpenseIQ</a></p>
    <p>Best regards,<br>ExpenseIQ Team</p>
    """
    text_content = f"Welcome {username}! Your ExpenseIQ account is ready to use."

    return _send_via_sendgrid(
        to_email=user_email,
        subject="Welcome to ExpenseIQ! 🎉",
        html_content=html_content,
        text_content=text_content,
        context="send_registration_confirmation",
    )


def send_expense_notification(user_email, expense_name, amount, category, date):
    """
    Send notification when expense is added.

    Args:
        user_email (str): Recipient email address
        expense_name (str): Name of the expense
        amount (float): Amount of expense
        category (str): Category of expense
        date (str): Date of expense
    """
    html_content = f"""
    <h2>New Expense Recorded</h2>
    <p>A new expense has been added to your account:</p>
    <ul>
        <li><strong>Name:</strong> {expense_name}</li>
        <li><strong>Amount:</strong> ₹{amount}</li>
        <li><strong>Category:</strong> {category}</li>
        <li><strong>Date:</strong> {date}</li>
    </ul>
    <p>Check your ExpenseIQ dashboard to view all expenses.</p>
    """
    text_content = f"Expense Added: {expense_name} - ₹{amount} in {category}"

    return _send_via_sendgrid(
        to_email=user_email,
        subject=f"💰 New Expense Added: {expense_name}",
        html_content=html_content,
        text_content=text_content,
        context="send_expense_notification",
    )


def send_password_reset_email(user_email, reset_token, username):
    """
    Send password reset link email.

    Args:
        user_email (str): Recipient email address
        reset_token (str): Password reset token
        username (str): User's username
    """
    reset_url = f"https://expenseiq-y2m4.onrender.com/reset-password?token={reset_token}"

    html_content = f"""
    <h2>Password Reset Request</h2>
    <p>Hi {username},</p>
    <p>You requested to reset your password. Click the link below to proceed:</p>
    <p><a href="{reset_url}" style="background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Reset Password</a></p>
    <p>This link expires in 24 hours.</p>
    <p>If you didn't request this, please ignore this email.</p>
    """
    text_content = f"Click this link to reset your password: {reset_url}"

    return _send_via_sendgrid(
        to_email=user_email,
        subject="Reset Your ExpenseIQ Password 🔐",
        html_content=html_content,
        text_content=text_content,
        context="send_password_reset_email",
    )


def send_ocr_receipt_alert(user_email, receipt_data):
    """
    Send email when receipt is scanned.

    Args:
        user_email (str): Recipient email address
        receipt_data (dict): Extracted receipt data
    """
    amount = receipt_data.get("amount", "N/A")
    merchant = receipt_data.get("merchant", "N/A")
    date = receipt_data.get("date", "N/A")

    html_content = f"""
    <h2>Receipt Scanned</h2>
    <p>Your receipt has been successfully scanned:</p>
    <ul>
        <li><strong>Amount:</strong> ₹{amount}</li>
        <li><strong>Merchant:</strong> {merchant}</li>
        <li><strong>Date:</strong> {date}</li>
    </ul>
    <p>Review and confirm the details in your ExpenseIQ app.</p>
    """
    text_content = f"Receipt scanned for ₹{amount} at {merchant}"

    return _send_via_sendgrid(
        to_email=user_email,
        subject="📸 Receipt Scanned Successfully",
        html_content=html_content,
        text_content=text_content,
        context="send_ocr_receipt_alert",
    )