"""
OCR Service - Receipt scanning for ExpenseIQ (Backup Clean Version)
"""

import re
from datetime import datetime
from io import BytesIO
from PIL import Image
import pytesseract

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "bmp"}

TOTAL_KEYWORDS = [
    "grand total", "net amount", "total amount", "amount payable",
    "net payable", "bill amount", "total payable", "total",
]

CATEGORY_KEYWORDS = {
    "Health": ["pharmacy", "medical", "chemist", "hospital", "clinic", "medicine"],
    "Food": ["dmart", "grocery", "supermarket", "restaurant", "food", "cafe"],
    "Shopping": ["mall", "store", "retail", "amazon", "flipkart", "electronics"],
    "Transport": ["uber", "ola", "taxi", "metro", "fuel"],
    "Bills": ["electricity", "recharge", "broadband", "water bill"],
}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def extract_text_from_image(file_storage):
    image = Image.open(BytesIO(file_storage.read())).convert("L")
    return pytesseract.image_to_string(image)


def parse_amount(text):
    pattern = r"(?:rs\.?|inr|₹)?\s*([0-9]+(?:,[0-9]{3})*(?:\.[0-9]{1,2})?)"

    # prioritize total line
    for line in text.splitlines():
        low = line.lower()
        if any(k in low for k in TOTAL_KEYWORDS):
            match = re.findall(pattern, low)
            if match:
                return float(match[-1].replace(",", ""))

    # fallback max value
    values = []
    for m in re.findall(pattern, text):
        try:
            values.append(float(m.replace(",", "")))
        except:
            pass

    return max(values) if values else None


def parse_date(text):
    patterns = [
        r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        r"(\d{4}[/-]\d{1,2}[/-]\d{1,2})",
    ]

    for p in patterns:
        match = re.search(p, text)
        if match:
            try:
                return datetime.strptime(match.group(1), "%d/%m/%Y").strftime("%Y-%m-%d")
            except:
                pass
    return None


def guess_category(text):
    text = text.lower()
    for cat, keys in CATEGORY_KEYWORDS.items():
        if any(k in text for k in keys):
            return cat
    return "Other"


def guess_merchant(text):
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    return lines[0] if lines else ""


def parse_receipt(file_storage):
    raw_text = extract_text_from_image(file_storage)

    merchant = guess_merchant(raw_text)

    return {
        "amount": parse_amount(raw_text),
        "date": parse_date(raw_text),
        "category": guess_category(raw_text),
        "merchant": merchant,
        "description": merchant,
        "raw_text": raw_text
    }