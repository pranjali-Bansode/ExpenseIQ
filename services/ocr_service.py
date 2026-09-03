"""
OCR Service - ExpenseIQ

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

The engine location is auto-detected (PATH, then TESSERACT_CMD env var,
then the common Windows install path) instead of being hardcoded, so this
works the same on a dev laptop, CI, and a Linux/Mac server.
"""

import os
import re
import shutil
import platform
from datetime import datetime
from io import BytesIO

from PIL import Image, ImageOps
import pytesseract


# ---------------------------------------------------------------- #
# Tesseract binary discovery (cross-platform, no hardcoded path)
# ---------------------------------------------------------------- #
def _configure_tesseract():
    # 1. Explicit override via environment variable always wins.
    env_path = os.environ.get("TESSERACT_CMD")
    if env_path and os.path.exists(env_path):
        pytesseract.pytesseract.tesseract_cmd = env_path
        return

    # 2. Whatever is on PATH (works out of the box on Linux/Mac/CI).
    found = shutil.which("tesseract")
    if found:
        pytesseract.pytesseract.tesseract_cmd = found
        return

    # 3. Common Windows install location, only if it actually exists there.
    if platform.system() == "Windows":
        default_win = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        if os.path.exists(default_win):
            pytesseract.pytesseract.tesseract_cmd = default_win
    # Otherwise leave pytesseract's default alone; if tesseract truly isn't
    # installed anywhere, it will raise a clear TesseractNotFoundError
    # instead of us silently pointing at a path that doesn't exist.


_configure_tesseract()

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "bmp"}

# Phrases that usually sit right next to the final payable amount.
# Order matters: more specific phrases are checked first.
TOTAL_KEYWORDS = [
    "grand total", "net amount", "total amount", "amount payable",
    "net payable", "bill amount", "total payable", "total",
]

# Many Indian POS receipts (D-Mart, supermarkets, etc.) print a summary
# line like "Items: 13   Qty: 15   477.70" right after the item list —
# the final amount on that line *is* the bill total, even though the
# word "total" never appears on it. This is checked before TOTAL_KEYWORDS.
ITEM_SUMMARY_KEYWORDS = ["items:", "items :", "no of items", "no. of items"]

# Once a line like this is seen, everything after it is a per-tax-slab
# breakdown table (taxable amount / CGST / SGST / cess per GST rate) — not
# the bill total. Kept as a best-effort signal, but NOT relied on alone —
# "GST Breakup Details" OCRs unreliably (e.g. as "OST Broaktp"), so the
# structural check in _looks_like_tax_slab_row() below is the primary
# defence against this table polluting the amount fallback.
GST_SECTION_MARKERS = [
    "gst breakup", "tax breakup", "hsn summary", "gst summary",
    "rate wise", "taxable amount",
]

# Lines mentioning these near the bottom of a receipt restate the final
# paid amount and are a strong, independent signal — checked after the
# item-summary line but before the generic TOTAL_KEYWORDS scan.
PAYMENT_LINE_KEYWORDS = [
    "amount received", "upi payment", "cash payment", "card payment",
    "amount paid", "you paid",
]

# The GST breakup table's closing row is conventionally printed as
# "T: <taxable> <cgst> <sgst> <total>" — often OCR'd as "Tt:" or similar.
# The LAST number on that row is the grand total (it repeats it), so this
# is another independent way to reach the right answer even when the
# "Items:" summary line and the table header both OCR badly.
_CLOSING_TOTAL_ROW = re.compile(r"^tt?\s*[:;]", re.IGNORECASE)

# A tax-slab breakdown row (e.g. "1  123.20  ....  ....  ....  123.20" or
# "2  337.62  8.44  8.44  ....  354.50") always starts with a bare
# single-digit GST-slab index. No legitimate item row or total line does
# this (item rows start with a 6-digit HSN code; totals are labelled).
# Detecting this shape — rather than the easily-garbled table header text
# — is what reliably keeps these rows out of the amount fallback.
_SLAB_ROW_FIRST_TOKEN = re.compile(r"^[1-9]$")


def _looks_like_tax_slab_row(line):
    tokens = line.split()
    if not tokens or not _SLAB_ROW_FIRST_TOKEN.match(tokens[0]):
        return False
    # Must also contain at least one decimal money value to count —
    # otherwise a genuine one-word/one-digit line could be misclassified.
    return bool(_extract_money_values(line, require_decimal=True))

# Lines containing these should never be treated as the amount, even in the
# fallback pass — they're a common source of wrong "amount" guesses (HSN /
# product codes, CIN, GST, bill/invoice numbers, phone numbers, etc.).
IGNORE_LINE_KEYWORDS = [
    "gstin", "gst no", "cin no", "phone", "mobile", "contact", "invoice no",
    "bill no", "receipt no", "order no", "table no", "cashier",
    "fssai", "voucher", "vou. no", "hsn",
]

# Lines that describe the store's *location* rather than the store itself
# (street/landmark references). "Opposite Fortune Hospital" on a grocery
# receipt should never make the category guesser think this is a medical
# expense — so these lines are excluded from category keyword scanning.
ADDRESS_LINE_KEYWORDS = [
    "opposite", "near ", "beside", "behind", "next to", "landmark",
    " road", "nagar", "marg", "colony", "sector", "chowk", "society",
    "survey no", "cts no", "ward no", "pin code", "pincode", "pcmc",
]

CATEGORY_KEYWORDS = {
    "Food": [
        "dmart", "d-mart", "d mart", "supermarket", "supermarts", "mart",
        "grocery", "kirana", "big bazaar", "reliance fresh",
        "more supermarket", "restaurant", "cafe", "food", "swiggy",
        "zomato", "hypermarket",
    ],
    "Health": [
        "pharmacy", "medical store", "chemist", "hospital", "clinic",
        "medicine", "tablet", "capsule", "diagnostic", "lab test",
        "apollo pharmacy", "medplus", "wellness", "healthcare",
    ],
    "Shopping": [
        "mall", "fashion", "electronics", "myntra", "amazon", "flipkart",
        "lifestyle", "pantaloons",
    ],
    "Transport": [
        "petrol", "diesel", "fuel", "uber", "ola", "cab", "taxi", "metro",
    ],
    "Bills": [
        "electricity", "recharge", "broadband", "dth", "water bill",
    ],
    "Entertainment": [
        "cinema", "movie", "pvr", "inox", "netflix", "bookmyshow",
    ],
}

# Month name -> number, for receipts printed like "01 Sep 2026" / "Sept 1, 2026"
_MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10,
    "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}

_CURRENT_YEAR = datetime.now().year
_MIN_YEAR = 2015
_MAX_YEAR = _CURRENT_YEAR + 1

# Money pattern: a full run of digits (with optional thousands separators
# and an optional 2-decimal part), matched as ONE contiguous number.
# Using `\d[\d,]*` (instead of capping the integer part at 3 digits) is the
# key fix — it stops the previous behaviour of chopping "1499" into "149"
# and "9" or matching nothing at all in "2350.00".
_MONEY_PATTERN = re.compile(
    r"(?:rs\.?|inr|₹)?\s*(\d[\d,]*(?:\.\d{1,2})?)", re.IGNORECASE
)

# A reasonable ceiling for a single expense line item / total on a receipt.
# Filters out phone numbers, invoice numbers, GSTINs etc. that would
# otherwise win the "largest number on the page" fallback.
_MAX_REASONABLE_AMOUNT = 999999.0


def allowed_file(filename):
    """Check the uploaded file has an image extension we can OCR."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def extract_text_from_image(file_storage):
    """Run OCR on an uploaded image (werkzeug FileStorage) and return raw text."""
    image_bytes = file_storage.read()
    image = Image.open(BytesIO(image_bytes))

    # Respect the camera's EXIF orientation tag (phone photos are very
    # commonly stored sideways/upside-down relative to how they display).
    image = ImageOps.exif_transpose(image)

    # Grayscale improves accuracy on phone-camera receipts.
    image = image.convert("L")

    # Upscale small/low-res photos — Tesseract does noticeably better
    # above ~1000px on the long edge.
    max_side = max(image.size)
    if max_side < 1500:
        scale = 1500 / max_side
        new_size = (int(image.width * scale), int(image.height * scale))
        image = image.resize(new_size, Image.LANCZOS)

    # Boost contrast so faint thermal-printer receipts OCR more reliably.
    image = ImageOps.autocontrast(image)

    return pytesseract.image_to_string(image, config="--oem 3 --psm 6")


def _normalize_decimal_commas(text):
    """
    Thermal/dot-matrix receipts often get OCR'd with the decimal point
    misread as a comma followed by a space (e.g. printed "477.70" comes
    back as "477, 70"). Genuine Indian thousands-separator commas are
    never followed by a space (e.g. "12,499"), so it's safe to fix only
    the "<digits>, <2 digits>" pattern into a real decimal point.
    """
    return re.sub(r"(\d+),\s+(\d{2})\b", r"\1.\2", text)


def _extract_money_values(line, require_decimal=False):
    """Return all plausible money values found on a single line.

    require_decimal=True restricts matches to numbers that include a
    decimal part (e.g. "477.70"). Receipts almost always print money with
    2 decimal places, while product/HSN codes, bill numbers, and phone
    numbers are always plain integers — so requiring a decimal point is a
    reliable way to keep a stray 6-digit product code from ever winning
    the "largest number on the page" fallback below.
    """
    values = []
    for raw in _MONEY_PATTERN.findall(line):
        if require_decimal and "." not in raw:
            continue
        cleaned = raw.replace(",", "")
        try:
            value = float(cleaned)
        except ValueError:
            continue
        if 0 < value <= _MAX_REASONABLE_AMOUNT:
            values.append(value)
    return values


def parse_amount(text):
    """Find the most likely total/payable amount on the receipt."""
    text = _normalize_decimal_commas(text)
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    # 1. POS "Items: N  Qty: M  <amount>" summary line — the strongest
    #    signal when present, since it's specific to the bill total and
    #    printed once, right after the itemized list.
    for line in lines:
        low = line.lower()
        if any(kw in low for kw in ITEM_SUMMARY_KEYWORDS):
            values = _extract_money_values(low, require_decimal=True)
            if values:
                return round(values[-1], 2)

    # 2. GST breakup table's closing "T:"/"Tt:" row repeats the grand
    #    total as its last column.
    for line in lines:
        if _CLOSING_TOTAL_ROW.match(line):
            values = _extract_money_values(line, require_decimal=True)
            if values:
                return round(values[-1], 2)

    # 3. "Amount Received" / "UPI Payment" / "Amount Paid" lines restate
    #    the final total independently of how the itemized section OCR'd.
    for line in lines:
        low = line.lower()
        if any(kw in low for kw in PAYMENT_LINE_KEYWORDS):
            values = _extract_money_values(low, require_decimal=True)
            if values:
                return round(values[-1], 2)

    # 4. Prefer a line that mentions "total" / "amount payable" etc.,
    #    skipping over lines that are clearly something else (GSTIN, phone).
    for keyword in TOTAL_KEYWORDS:
        for line in lines:
            low = line.lower()
            if keyword not in low:
                continue
            if any(bad in low for bad in IGNORE_LINE_KEYWORDS):
                continue
            values = _extract_money_values(low)
            if values:
                # The amount is almost always the last number on a total line
                # (e.g. "Total Qty 5   Total Amount: Rs. 1499.00").
                return round(values[-1], 2)

    # 5. Fallback — largest number that's actually formatted like money
    #    (has a decimal part) anywhere on the receipt, ignoring lines that
    #    look like phone/invoice/GST/HSN numbers OR tax-slab breakdown rows
    #    (structurally detected, not by header text — see
    #    _looks_like_tax_slab_row — since table headers OCR unreliably).
    all_values = []
    for line in lines:
        low = line.lower()
        if any(bad in low for bad in IGNORE_LINE_KEYWORDS):
            continue
        if _looks_like_tax_slab_row(line):
            continue
        all_values.extend(_extract_money_values(low, require_decimal=True))

    if all_values:
        return round(max(all_values), 2)

    # 6. Last resort — no decimal-formatted numbers found at all (rare).
    #    Fall back to the previous, looser rule rather than returning
    #    nothing. Still skips tax-slab rows and ignored lines.
    all_values = []
    for line in lines:
        low = line.lower()
        if any(bad in low for bad in IGNORE_LINE_KEYWORDS):
            continue
        if _looks_like_tax_slab_row(line):
            continue
        all_values.extend(_extract_money_values(low))

    return round(max(all_values), 2) if all_values else None


def _try_parse_numeric_date(raw):
    formats = [
        "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y",
        "%Y-%m-%d", "%Y/%m/%d",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(raw, fmt)
            if _MIN_YEAR <= dt.year <= _MAX_YEAR:
                return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def parse_date(text):
    """Find a date on the receipt and normalize it to YYYY-MM-DD."""
    # Numeric formats: 12/04/2026, 12-04-26, 2026-04-12, etc.
    numeric_patterns = [
        r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b",
        r"\b(\d{4}[/-]\d{1,2}[/-]\d{1,2})\b",
    ]
    for pattern in numeric_patterns:
        for match in re.finditer(pattern, text):
            result = _try_parse_numeric_date(match.group(1))
            if result:
                return result

    # Month-name formats: "01 Sep 2026", "Sep 01, 2026", "September 1 2026"
    month_names = "|".join(sorted(_MONTHS.keys(), key=len, reverse=True))
    day_month_year = re.compile(
        rf"\b(\d{{1,2}})\s+({month_names})\.?,?\s+(\d{{4}})\b", re.IGNORECASE
    )
    month_day_year = re.compile(
        rf"\b({month_names})\.?\s+(\d{{1,2}}),?\s+(\d{{4}})\b", re.IGNORECASE
    )

    m = day_month_year.search(text)
    if m:
        day, month_name, year = m.groups()
        month = _MONTHS[month_name.lower()]
        try:
            dt = datetime(int(year), month, int(day))
            if _MIN_YEAR <= dt.year <= _MAX_YEAR:
                return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass

    m = month_day_year.search(text)
    if m:
        month_name, day, year = m.groups()
        month = _MONTHS[month_name.lower()]
        try:
            dt = datetime(int(year), month, int(day))
            if _MIN_YEAR <= dt.year <= _MAX_YEAR:
                return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass

    return None


def guess_category(text):
    """
    Score each category by keyword hits, ignoring address/location lines
    (e.g. "Opposite Fortune Hospital" on a grocery receipt) so an
    incidental nearby-landmark mention can't outrank the actual store name.
    The store name usually appears near the top, so header lines count
    double.
    """
    lines = [l for l in text.lower().splitlines() if l.strip()]
    scores = {cat: 0 for cat in CATEGORY_KEYWORDS}

    for i, line in enumerate(lines):
        if any(addr_kw in line for addr_kw in ADDRESS_LINE_KEYWORDS):
            continue
        weight = 2 if i < 6 else 1  # header/merchant lines count more
        for cat, keywords in CATEGORY_KEYWORDS.items():
            for kw in keywords:
                if kw in line:
                    scores[cat] += weight

    best_cat = max(scores, key=lambda c: scores[c])
    return best_cat if scores[best_cat] > 0 else "Other"


def guess_merchant(text):
    """The first solid-looking OCR line is almost always the store/hospital name."""
    for line in (l.strip() for l in text.splitlines()):
        if len(line) < 3:
            continue
        # Skip lines that are mostly punctuation/digits (separators, barcodes).
        alpha_chars = sum(1 for c in line if c.isalpha())
        if alpha_chars < 3:
            continue
        return line[:100]
    return ""


def parse_receipt(file_storage):
    """
    Main entry point. Takes an uploaded receipt image (Flask FileStorage)
    and returns a dict ready to auto-fill the Add Expense form:

        {
            "amount": 1499.0 | None,
            "date": "2026-04-01" | None,
            "category": "Food",
            "merchant": "D MART",
            "description": "D MART",
            "raw_text": "...",
        }
    """
    raw_text = extract_text_from_image(file_storage)
    merchant = guess_merchant(raw_text)

    return {
        "amount": parse_amount(raw_text),
        "date": parse_date(raw_text),
        "category": guess_category(raw_text),
        "merchant": merchant,
        "description": merchant if merchant else "Scanned receipt",
        "raw_text": raw_text.strip(),
    }