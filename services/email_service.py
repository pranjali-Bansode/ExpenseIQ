"""
ExpenseIQ Email Implementation Snippets
Ready-to-copy code for your Flask backend
"""

# ============================================================================
# FILE 1: services/email_service.py
# ============================================================================

from flask_mail import Mail, Message
from flask import current_app
import logging

mail = Mail()
logger = logging.getLogger(__name__)


def send_budget_alert(user_email, budget_name, amount_limit, spent_amount):
    """
    Send email alert when user exceeds budget
    
    Args:
        user_email (str): Recipient email address
        budget_name (str): Name of the budget
        amount_limit (float): Budget limit
        spent_amount (float): Amount spent
    """
    if not user_email:
        logger.error("send_budget_alert: user_email is None or empty")
        return False
    
    try:
        with current_app.app_context():
            msg = Message(
                subject=f"⚠️ Budget Alert: {budget_name}",
                recipients=[user_email],  # Dynamic recipient
                html=f"""
                <h2>Budget Alert</h2>
                <p>You have exceeded your budget!</p>
                <ul>
                    <li><strong>Budget:</strong> {budget_name}</li>
                    <li><strong>Limit:</strong> ₹{amount_limit}</li>
                    <li><strong>Spent:</strong> ₹{spent_amount}</li>
                    <li><strong>Exceeded by:</strong> ₹{spent_amount - amount_limit}</li>
                </ul>
                <p>Please review your expenses in ExpenseIQ.</p>
                """,
                body=f"Budget Alert: You have exceeded {budget_name} budget. Limit: {amount_limit}, Spent: {spent_amount}"
            )
            mail.send(msg)
            logger.info(f"Budget alert email sent to {user_email}")
            return True
    except Exception as e:
        logger.error(f"Error sending budget alert to {user_email}: {str(e)}")
        return False


def send_registration_confirmation(user_email, username):
    """
    Send registration confirmation email
    
    Args:
        user_email (str): Recipient email address
        username (str): User's username
    """
    if not user_email:
        logger.error("send_registration_confirmation: user_email is None or empty")
        return False
    
    try:
        with current_app.app_context():
            msg = Message(
                subject="Welcome to ExpenseIQ! 🎉",
                recipients=[user_email],  # Dynamic recipient
                html=f"""
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
                """,
                body=f"Welcome {username}! Your ExpenseIQ account is ready to use."
            )
            mail.send(msg)
            logger.info(f"Registration confirmation sent to {user_email}")
            return True
    except Exception as e:
        logger.error(f"Error sending registration email to {user_email}: {str(e)}")
        return False


def send_expense_notification(user_email, expense_name, amount, category, date):
    """
    Send notification when expense is added
    
    Args:
        user_email (str): Recipient email address
        expense_name (str): Name of the expense
        amount (float): Amount of expense
        category (str): Category of expense
        date (str): Date of expense
    """
    if not user_email:
        logger.error("send_expense_notification: user_email is None or empty")
        return False
    
    try:
        with current_app.app_context():
            msg = Message(
                subject=f"💰 New Expense Added: {expense_name}",
                recipients=[user_email],  # Dynamic recipient
                html=f"""
                <h2>New Expense Recorded</h2>
                <p>A new expense has been added to your account:</p>
                <ul>
                    <li><strong>Name:</strong> {expense_name}</li>
                    <li><strong>Amount:</strong> ₹{amount}</li>
                    <li><strong>Category:</strong> {category}</li>
                    <li><strong>Date:</strong> {date}</li>
                </ul>
                <p>Check your ExpenseIQ dashboard to view all expenses.</p>
                """,
                body=f"Expense Added: {expense_name} - ₹{amount} in {category}"
            )
            mail.send(msg)
            logger.info(f"Expense notification sent to {user_email}")
            return True
    except Exception as e:
        logger.error(f"Error sending expense notification to {user_email}: {str(e)}")
        return False


def send_password_reset_email(user_email, reset_token, username):
    """
    Send password reset link email
    
    Args:
        user_email (str): Recipient email address
        reset_token (str): Password reset token
        username (str): User's username
    """
    if not user_email:
        logger.error("send_password_reset_email: user_email is None or empty")
        return False
    
    try:
        with current_app.app_context():
            reset_url = f"https://expenseiq-y2m4.onrender.com/reset-password?token={reset_token}"
            msg = Message(
                subject="Reset Your ExpenseIQ Password 🔐",
                recipients=[user_email],  # Dynamic recipient
                html=f"""
                <h2>Password Reset Request</h2>
                <p>Hi {username},</p>
                <p>You requested to reset your password. Click the link below to proceed:</p>
                <p><a href="{reset_url}" style="background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Reset Password</a></p>
                <p>This link expires in 24 hours.</p>
                <p>If you didn't request this, please ignore this email.</p>
                """,
                body=f"Click this link to reset your password: {reset_url}"
            )
            mail.send(msg)
            logger.info(f"Password reset email sent to {user_email}")
            return True
    except Exception as e:
        logger.error(f"Error sending password reset email to {user_email}: {str(e)}")
        return False


def send_ocr_receipt_alert(user_email, receipt_data):
    """
    Send email when receipt is scanned
    
    Args:
        user_email (str): Recipient email address
        receipt_data (dict): Extracted receipt data
    """
    if not user_email:
        logger.error("send_ocr_receipt_alert: user_email is None or empty")
        return False
    
    try:
        with current_app.app_context():
            msg = Message(
                subject="📸 Receipt Scanned Successfully",
                recipients=[user_email],  # Dynamic recipient
                html=f"""
                <h2>Receipt Scanned</h2>
                <p>Your receipt has been successfully scanned:</p>
                <ul>
                    <li><strong>Amount:</strong> ₹{receipt_data.get('amount', 'N/A')}</li>
                    <li><strong>Merchant:</strong> {receipt_data.get('merchant', 'N/A')}</li>
                    <li><strong>Date:</strong> {receipt_data.get('date', 'N/A')}</li>
                </ul>
                <p>Review and confirm the details in your ExpenseIQ app.</p>
                """,
                body=f"Receipt scanned for ₹{receipt_data.get('amount', 'N/A')} at {receipt_data.get('merchant', 'N/A')}"
            )
            mail.send(msg)
            logger.info(f"Receipt alert sent to {user_email}")
            return True
    except Exception as e:
        logger.error(f"Error sending receipt alert to {user_email}: {str(e)}")
        return False


# ============================================================================
# FILE 2: app.py or config.py
# ============================================================================

import os
from dotenv import load_dotenv
from flask import Flask
from flask_mail import Mail
from flask_sqlalchemy import SQLAlchemy

load_dotenv()

app = Flask(__name__)

# Database Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///expenseiq.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Flask-Mail Configuration
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'True') == 'True'
app.config['MAIL_USE_SSL'] = os.getenv('MAIL_USE_SSL', 'False') == 'True'
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_SUPPRESS_SEND'] = False  # Set to True for testing without actually sending

# Session Configuration
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = 86400  # 24 hours

db = SQLAlchemy(app)
mail = Mail(app)

print(f"[CONFIG] Mail Server: {app.config['MAIL_SERVER']}")
print(f"[CONFIG] Mail Port: {app.config['MAIL_PORT']}")
print(f"[CONFIG] Mail Username: {app.config['MAIL_USERNAME']}")
print(f"[CONFIG] Mail Sender: {app.config['MAIL_DEFAULT_SENDER']}")


# ============================================================================
# FILE 3: routes/auth.py (User Registration Example)
# ============================================================================

from flask import Blueprint, request, jsonify, session
from werkzeug.security import generate_password_hash
from services.email_service import send_registration_confirmation
from database.models import User
from app import db

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')


@auth_bp.route('/register', methods=['POST'])
def register():
    """
    Register a new user
    Expected JSON: {
        "username": "john_doe",
        "email": "john@example.com",
        "password": "securepassword"
    }
    """
    try:
        data = request.get_json()
        
        # Validate input
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '')
        
        if not all([username, email, password]):
            return jsonify({"error": "Username, email, and password are required"}), 400
        
        # Check if user already exists
        if User.query.filter_by(email=email).first():
            return jsonify({"error": "Email already registered"}), 409
        
        if User.query.filter_by(username=username).first():
            return jsonify({"error": "Username already taken"}), 409
        
        # Create new user
        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password)
        )
        
        db.session.add(user)
        db.session.commit()
        
        # ✅ SEND REGISTRATION EMAIL WITH USER'S EMAIL
        send_registration_confirmation(
            user_email=email,  # Use the email they registered with
            username=username
        )
        
        return jsonify({
            "message": "User registered successfully. Check your email for confirmation.",
            "user_id": user.id
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@auth_bp.route('/login', methods=['POST'])
def login():
    """
    Login user
    Expected JSON: {
        "email": "john@example.com",
        "password": "securepassword"
    }
    """
    try:
        data = request.get_json()
        email = data.get('email', '').strip()
        password = data.get('password', '')
        
        if not email or not password:
            return jsonify({"error": "Email and password required"}), 400
        
        user = User.query.filter_by(email=email).first()
        
        if not user or not user.check_password(password):
            return jsonify({"error": "Invalid credentials"}), 401
        
        # Store user in session
        session['user_id'] = user.id
        session['email'] = user.email
        session['username'] = user.username
        
        return jsonify({
            "message": "Login successful",
            "user_id": user.id,
            "username": user.username,
            "email": user.email
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================================
# FILE 4: routes/expenses.py (Expense Example)
# ============================================================================

from flask import Blueprint, request, jsonify, session
from datetime import datetime
from services.email_service import send_expense_notification, send_budget_alert
from database.models import User, Expense, Budget
from app import db

expense_bp = Blueprint('expenses', __name__, url_prefix='/api/expenses')


@expense_bp.route('/add', methods=['POST'])
def add_expense():
    """
    Add a new expense
    Expected JSON: {
        "name": "Coffee",
        "amount": 5.00,
        "category": "Food",
        "date": "2026-09-06"
    }
    """
    try:
        # Get user from session
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({"error": "User not authenticated"}), 401
        
        # Fetch user from database
        user = User.query.get(user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        # Get request data
        data = request.get_json()
        name = data.get('name', '').strip()
        amount = float(data.get('amount', 0))
        category = data.get('category', '').strip()
        date_str = data.get('date', datetime.now().isoformat())
        
        # Validate
        if not name or amount <= 0 or not category:
            return jsonify({"error": "Invalid expense data"}), 400
        
        # Create expense
        expense = Expense(
            user_id=user_id,
            name=name,
            amount=amount,
            category=category,
            date=datetime.fromisoformat(date_str)
        )
        
        db.session.add(expense)
        db.session.commit()
        
        # ✅ SEND EMAIL NOTIFICATION WITH USER'S ACTUAL EMAIL
        if user.email:
            send_expense_notification(
                user_email=user.email,  # Use user's email from database
                expense_name=name,
                amount=amount,
                category=category,
                date=date_str
            )
        
        # Check if this expense exceeded any budget
        budget = Budget.query.filter_by(
            user_id=user_id,
            category=category
        ).first()
        
        if budget:
            total_spent = db.session.query(
                db.func.sum(Expense.amount)
            ).filter_by(
                user_id=user_id,
                category=category
            ).scalar() or 0
            
            if total_spent > budget.limit and user.email:
                # ✅ SEND BUDGET ALERT WITH USER'S EMAIL
                send_budget_alert(
                    user_email=user.email,  # User's actual email
                    budget_name=budget.name,
                    amount_limit=budget.limit,
                    spent_amount=total_spent
                )
        
        return jsonify({
            "message": "Expense added successfully",
            "expense_id": expense.id
        }), 201
        
    except ValueError as e:
        return jsonify({"error": f"Invalid input: {str(e)}"}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# ============================================================================
# FILE 5: .env (Environment Variables)
# ============================================================================

"""
Copy this to your .env file and fill in your actual values.
DO NOT COMMIT THIS FILE TO GIT!
"""

# Gmail Configuration (use App Password, not your regular password)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-16-char-app-password

# Database
DATABASE_URL=sqlite:///expenseiq.db

# Flask
FLASK_ENV=production
SECRET_KEY=your-secret-key-here-min-32-chars-long


# ============================================================================
# FILE 6: Dockerfile (for Render deployment)
# ============================================================================

"""
Copy this to your Dockerfile (root of project)
"""

FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY . .

# Expose port
EXPOSE 5000

# Run app
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "app:app"]


# ============================================================================
# FILE 7: Testing Script (test_email.py)
# ============================================================================

"""
Run this locally to test email functionality:
python test_email.py
"""

from app import app, mail
from flask_mail import Message
from services.email_service import send_budget_alert, send_registration_confirmation

def test_email_configuration():
    """Test if email configuration is correct"""
    print("[TEST] Email Configuration Check")
    print(f"  MAIL_SERVER: {app.config['MAIL_SERVER']}")
    print(f"  MAIL_PORT: {app.config['MAIL_PORT']}")
    print(f"  MAIL_USERNAME: {app.config['MAIL_USERNAME']}")
    print(f"  MAIL_USE_TLS: {app.config['MAIL_USE_TLS']}")
    print(f"  MAIL_DEFAULT_SENDER: {app.config['MAIL_DEFAULT_SENDER']}")
    print()

def test_send_simple_email():
    """Test sending a simple email"""
    print("[TEST] Sending Simple Test Email")
    try:
        with app.app_context():
            msg = Message(
                subject="Test Email from ExpenseIQ",
                recipients=["your-test-email@gmail.com"],  # Change this!
                body="This is a test email. If you receive this, email is working!"
            )
            mail.send(msg)
            print("✅ Test email sent successfully!")
    except Exception as e:
        print(f"❌ Error sending test email: {str(e)}")
    print()

def test_registration_email():
    """Test registration email"""
    print("[TEST] Testing Registration Email")
    try:
        with app.app_context():
            result = send_registration_confirmation(
                user_email="your-test-email@gmail.com",  # Change this!
                username="testuser"
            )
            if result:
                print("✅ Registration email sent successfully!")
            else:
                print("❌ Failed to send registration email")
    except Exception as e:
        print(f"❌ Error: {str(e)}")
    print()

def test_budget_alert_email():
    """Test budget alert email"""
    print("[TEST] Testing Budget Alert Email")
    try:
        with app.app_context():
            result = send_budget_alert(
                user_email="your-test-email@gmail.com",  # Change this!
                budget_name="Food",
                amount_limit=500.00,
                spent_amount=650.00
            )
            if result:
                print("✅ Budget alert email sent successfully!")
            else:
                print("❌ Failed to send budget alert email")
    except Exception as e:
        print(f"❌ Error: {str(e)}")
    print()

if __name__ == "__main__":
    print("\n" + "="*50)
    print("ExpenseIQ Email Testing Suite")
    print("="*50 + "\n")
    
    test_email_configuration()
    test_send_simple_email()
    test_registration_email()
    test_budget_alert_email()
    
    print("="*50)
    print("Testing Complete!")
    print("="*50 + "\n")
