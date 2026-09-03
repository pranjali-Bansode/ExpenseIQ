"""
OCR Service - Receipt scanning for ExpenseIQ.

Extracts amount, date, merchant and a suggested category from a photo/scan
of a receipt (D-Mart bill, medical/pharmacy bill, restaurant bill, etc.)
using Tesseract OCR.

SETUP REQUIRED (see requirements.txt):
    pip install pytesseract Pillow

You also need the Tesseract OCR ENGINE installed on your machine
(pytesseract is just a Python wrapper around it):
    Windows: https://github.com/UB-Mannheim/tesseract/wiki
    Mac:     brew install tesseract
    Linux:   sudo apt-get install tesseract-ocr
"""

import re
from datetime import datetime
from io import BytesIO

from PIL import Image
import pytesseract

# On Windows, if tesseract isn't on PATH, uncomment and set the install path:
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "bmp"}

# Phrases that usually sit right next to the final payable amount
TOTAL_KEYWORDS = [
    "grand total", "net amount", "total amount", "amount payable",
    "net payable", "bill amount", "total payable", "total",
]

# Keyword -> category guess (covers DMart / grocery + medical/pharmacy bills,
# plus a few other common receipt types)
CATEGORY_KEYWORDS = {
    "Health": [
        "pharmacy", "medical", "chemist", "hospital", "clinic", "medicine",
        "tablet", "capsule", "diagnostic", "lab test", "apollo", "medplus",
        "wellness", "healthcare",
    ],
    "Food": [
        "dmart", "d-mart", "d mart", "supermarket", "grocery", "kirana",
        "big bazaar", "reliance fresh", "more supermarket", "restaurant",
        "cafe", "food", "swiggy", "zomato", "hypermarket",
    ],
    "Shopping": [
        "mall", "fashion", "store", "retail", "electronics", "myntra",
        "amazon", "flipkart", "lifestyle", "pantaloons",
    ],
    "Transport": [
        "petrol", "diesel", "fuel", "uber", "ola", "cab", "taxi", "metro",
    ],
    "Bills": [
        "electricity", "recharge", "broadband", "dth", "water bill",
    ],
}


def allowed_file(filename):
    """Check the uploaded file has an image extension we can OCR."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def extract_text_from_image(file_storage):
    """Run OCR on an uploaded image (werkzeug FileStorage) and return raw text."""
    image_bytes = file_storage.read()
    image = Image.open(BytesIO(image_bytes))

    # Simple preprocessing - grayscale improves accuracy on phone-camera receipts
    image = image.convert("L")

    return pytesseract.image_to_string(image)


def _parse_amount(text):
    """Find the most likely total/payable amount on the receipt."""
    money_pattern = r"(?:rs\.?|inr|₹)?\s*([0-9]{1,3}(?:[,.][0-9]{2,3})*(?:\.[0-9]{1,2})?)"

    # 1. Prefer a line that mentions "total" / "amount payable" etc.
    for line in (l.strip() for l in text.splitlines() if l.strip()):
        lower = line.lower()
        if any(keyword in lower for keyword in TOTAL_KEYWORDS):
            matches = re.findall(money_pattern, lower)
            if matches:
                try:
                    value = float(matches[-1].replace(",", ""))
                    if value > 0:
                        return round(value, 2)
                except ValueError:
                    continue

    # 2. Fallback - largest currency-looking number anywhere on the receipt
    amounts = []
    for m in re.findall(money_pattern, text.lower()):
        try:
            amounts.append(float(m.replace(",", "")))
        except ValueError:
            continue

    return round(max(amounts), 2) if amounts else None


def _parse_date(text):
    """Find a date on the receipt and normalize it to YYYY-MM-DD."""
    date_patterns = [
        r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",  # 12/04/2026, 12-04-26
        r"(\d{4}[/-]\d{1,2}[/-]\d{1,2})",    # 2026-04-12
    ]
    date_formats = [
        "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y",
        "%Y-%m-%d", "%Y/%m/%d",
    ]

    for pattern in date_patterns:
        match = re.search(pattern, text)
        if match:
            raw = match.group(1)
            for fmt in date_formats:
                try:
                    return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
                except ValueError:
                    continue

    return None


def _guess_category(text):
    lower = text.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in lower for keyword in keywords):
            return category
    return "Other"


def _guess_merchant(text):
    """The first non-empty OCR line is almost always the store/hospital name."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    return lines[0][:100] if lines else ""


def parse_receipt(file_storage):
    """
    Main entry point. Takes an uploaded receipt image (Flask FileStorage)
    and returns a dict ready to auto-fill the Add Expense form:

        {
            "amount": 450.0 | None,
            "date": "2026-04-01" | None,
            "category": "Food",
            "merchant": "D MART",
            "description": "D MART",
            "raw_text": "...",
        }
    """
    raw_text = extract_text_from_image(file_storage)
    merchant = _guess_merchant(raw_text)

    return {
        "amount": _parse_amount(raw_text),
        "date": _parse_date(raw_text),
        "category": _guess_category(raw_text),
        "merchant": merchant,
        "description": merchant if merchant else "Scanned receipt",
        "raw_text": raw_text.strip(),
    }
