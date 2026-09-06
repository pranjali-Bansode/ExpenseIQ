"""
OCR Service - Receipt scanning for ExpenseIQ (hosted-API based, Render free-tier safe).

WHY THIS VERSION EXISTS:
The previous easyocr+torch approach needs far more RAM/CPU to load and run
its model than Render's free instance provides (0.1 CPU / 512MB RAM - Render's
own docs describe this tier as "not suitable for AI inference"). No code fix
changes that; the model itself doesn't fit. This version removes local ML
inference entirely and instead calls OCR.space's hosted OCR API over HTTPS -
the same pattern used for email via Resend: push the heavy lifting to an
external service reached over plain HTTPS (443), which Render's free tier
handles fine (only raw SMTP ports are blocked, not HTTPS).

SETUP REQUIRED:
1. Register a free API key at https://ocr.space/ocrapi (no credit card).
   Free tier: 25,000 requests/month, 1MB file size limit per image.
2. Set OCR_SPACE_API_KEY in Render's dashboard (Environment tab) - same
   place as RESEND_API_KEY / GMAIL_EMAIL etc.
   Do NOT rely on the shared demo key "helloworld" in production - it's
   rate-limited to ~10 requests every 10 minutes across ALL of OCR.space's
   users worldwide, not just you, and will fail under any real usage.
3. requirements.txt no longer needs easyocr / torch / opencv-python-headless
   / numpy for OCR - only `requests`, which was already there. This also
   removes several hundred MB from the build and eliminates the memory/
   timeout problems entirely.
"""

import os
import re

import requests

OCR_SPACE_API_KEY = os.getenv("OCR_SPACE_API_KEY", "helloworld")  # demo key fallback
OCR_SPACE_URL = "https://api.ocr.space/parse/image"

# ==============================
# 🎯 ALLOWED FILE TYPES
# ==============================
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "bmp"}


def allowed_file(filename):
    """Check if file extension is allowed"""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ==============================
# 📸 OCR TEXT EXTRACTION (OCR.space hosted API)
# ==============================
def extract_text_from_image(image_file):
    """
    Extract text from an uploaded image via OCR.space's hosted API.

    Args:
        image_file: File object from request.files (Flask FileStorage)

    Returns:
        str: Extracted text
    """
    image_file.seek(0)
    filename = getattr(image_file, "filename", "receipt.jpg") or "receipt.jpg"

    try:
        response = requests.post(
            OCR_SPACE_URL,
            files={"file": (filename, image_file.read(), "application/octet-stream")},
            data={
                "apikey": OCR_SPACE_API_KEY,
                "language": "eng",
                "OCREngine": "2",  # OCR.space's more accurate engine
                "isOverlayRequired": "false",
                "scale": "true",
            },
            timeout=25,
        )
    except requests.RequestException as e:
        raise Exception(f"Could not reach OCR service: {str(e)}")

    if response.status_code != 200:
        raise Exception(f"OCR service returned HTTP {response.status_code}: {response.text[:300]}")

    try:
        result = response.json()
    except ValueError:
        raise Exception("OCR service returned an unexpected (non-JSON) response")

    if result.get("IsErroredOnProcessing"):
        error_msg = result.get("ErrorMessage") or result.get("ErrorDetails") or "Unknown OCR error"
        if isinstance(error_msg, list):  # OCR.space sometimes returns a list
            error_msg = "; ".join(error_msg)
        raise Exception(f"OCR processing failed: {error_msg}")

    parsed_results = result.get("ParsedResults") or []
    if not parsed_results:
        return ""

    return "\n".join(pr.get("ParsedText", "") for pr in parsed_results)


# ==============================
# 💰 PARSE RECEIPT (Extract Amount & Category)
# ==============================
def parse_receipt(image_file):
    """
    Parse receipt and extract:
    - Amount (₹ value)
    - Category (guessed from keywords)

    Returns:
        {
            "amount": float,
            "category": str,
            "description": str,
            "confidence": float (0-1)
        }
    """
    text = extract_text_from_image(image_file)

    amount = extract_amount(text)
    category = guess_category(text)

    # First non-empty line is typically the store/merchant name (e.g. "D Mart")
    # - a much more useful description than a raw dump of the first 100
    # characters, which tends to include GSTIN/CIN numbers and other header
    # noise before anything readable shows up.
    description = next((line.strip() for line in text.split("\n") if line.strip()), "")[:100]

    return {
        "amount": amount,
        "category": category,
        "description": description,
        "confidence": 0.75 if amount else 0.3,
    }


# ==============================
# 💲 EXTRACT AMOUNT
# ==============================
# Lines containing these words are savings/discounts, not what was paid -
# e.g. "Saved Rs. 90.00 on MRP" on a DMart-style receipt. Without this
# exclusion, a discount amount can get picked up as if it were the total.
_EXCLUDE_LINE_WORDS = ("saved", "discount", "you save", "off on mrp", "cashback")

# Checked in this order: specific "this IS the total" phrases first, generic
# currency symbols last - so a real total/payment line always wins over an
# incidental Rs./₹ mention elsewhere on the receipt (like a savings line).
_AMOUNT_KEYWORD_PATTERNS = [
    r"grand\s*total\s*[:=]?\s*₹?\s*(?:rs\.?)?\s*(\d+(?:\.\d{2})?)",
    r"net\s*(?:amount|payable)\s*[:=]?\s*₹?\s*(?:rs\.?)?\s*(\d+(?:\.\d{2})?)",
    r"amount\s*received\s*[:=]?\s*₹?\s*(?:rs\.?)?\s*(\d+(?:\.\d{2})?)",
    r"upi\s*payment\s*[:=]?\s*₹?\s*(?:rs\.?)?\s*(\d+(?:\.\d{2})?)",
    r"total\s*amount\s*[:=]?\s*₹?\s*(?:rs\.?)?\s*(\d+(?:\.\d{2})?)",
    r"bill\s*amt\.?\s*[:=]?\s*₹?\s*(?:rs\.?)?\s*(\d+(?:\.\d{2})?)",
    r"total\s*[:=]?\s*₹?\s*(?:rs\.?)?\s*(\d+(?:\.\d{2})?)",   # generic "total"
    r"amount\s*[:=]?\s*₹?\s*(?:rs\.?)?\s*(\d+(?:\.\d{2})?)",  # generic "amount"
]


def extract_amount(text):
    """
    Extract the amount actually paid from receipt text.

    Strategy:
    1. Try specific "this is the total" phrases first (grand total, net
       amount, amount received, UPI payment, etc.) - these are unambiguous.
    2. If none match, fall back to the largest ₹/Rs number found on any
       line that isn't a savings/discount line - on real receipts the
       grand total is virtually always the largest currency figure printed,
       while savings/discount lines are smaller call-outs.
    """
    flat = text.replace("\n", " ").lower()

    for pattern in _AMOUNT_KEYWORD_PATTERNS:
        match = re.search(pattern, flat)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                continue

    # Fallback: largest ₹/Rs amount on a line that isn't a discount call-out.
    candidates = []
    for line in text.split("\n"):
        low = line.lower()
        if any(word in low for word in _EXCLUDE_LINE_WORDS):
            continue
        for m in re.finditer(r"(?:₹|rs\.?)\s*(\d+(?:\.\d{2})?)", low):
            try:
                candidates.append(float(m.group(1)))
            except ValueError:
                pass

    return max(candidates) if candidates else 0.0


# ==============================
# 🏷️ GUESS CATEGORY
# ==============================
def guess_category(text):
    """Guess expense category from receipt text"""
    text = text.lower()

    category_keywords = {
        "Food": [
            "restaurant", "cafe", "pizza", "burger", "coffee", "food", "delivery",
            "swiggy", "zomato", "dine",
            # supermarket/grocery vocabulary - a grocery run (DMart, Big Bazaar,
            # More, Reliance Fresh, etc.) is a food expense, not a utility bill.
            "mart", "supermarket", "supermarts", "hypermarket", "grocery", "kirana",
        ],
        "Transport": ["uber", "ola", "taxi", "petrol", "gas", "parking", "metro", "train", "bus", "vehicle"],
        "Shopping": ["mall", "store", "shop", "amazon", "flipkart", "retail", "market", "dress", "clothes"],
        # NOTE: bare "bill" was removed from here - almost every retail receipt
        # prints "Bill No." / "Bill Dt.", so it was matching supermarket and
        # restaurant receipts as "Bills" before either Food or Shopping got a
        # chance to match anything more specific. The remaining keywords below
        # are specific enough to actual utility bills that this false-positive
        # doesn't happen anymore.
        "Bills": ["electricity", "water bill", "internet bill", "broadband", "phone bill", "utility", "recharge"],
        "Health": ["pharmacy", "doctor", "hospital", "medical", "health", "medicine", "clinic"],
        "Entertainment": ["movie", "cinema", "theater", "game", "spotify", "netflix", "show", "ticket"],
    }

    for category, keywords in category_keywords.items():
        for keyword in keywords:
            if keyword in text:
                return category

    return "Other"
