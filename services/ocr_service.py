"""
OCR Service - Receipt scanning for ExpenseIQ (EasyOCR-based, Render-safe).

FIXES vs. the previous version:
1. easyocr.Reader(...).readtext() does NOT accept a PIL.Image object.
   It only accepts: a file path (str), raw bytes, or a numpy array.
   Passing a PIL Image silently produces wrong/empty results (or raises,
   depending on version) - this was the #1 reason OCR "did nothing".
   Fix: convert to a numpy array with np.array(img) before calling readtext().
2. `easyocr.Reader(['en'])` was being created on EVERY request. This:
   - re-loads the ~65-100MB recognition model from disk every single call
   - is extremely slow (multiple seconds, sometimes >30s cold)
   - is why requests were timing out on Render (gunicorn's default worker
     timeout is 30s) and appearing to "not work" in production even though
     it might succeed locally on a first warm call.
   Fix: build the Reader ONCE at import time (module-level singleton) and
   reuse it across requests.
3. Added explicit, actionable exceptions instead of swallowing errors.

DEPLOYMENT NOTES (Render):
- requirements.txt must use `opencv-python-headless`, NOT `opencv-python`.
  easyocr depends on OpenCV internally. The regular `opencv-python` wheel
  needs system graphics libraries (libGL.so.1, libSM.so.6, libXext.so.6)
  that are NOT present on Render's slim Python runtime. This causes:
      ImportError: libGL.so.1: cannot open shared object file
  at import time -> the whole app can fail to boot, not just OCR.
  `opencv-python-headless` has no GUI dependency and works out of the box.
- easyocr pulls in torch (PyTorch), which is a large download (several
  hundred MB) and needs real memory to run inference (recommend at least
  a 1GB-RAM Render instance; the free 512MB tier will likely OOM on the
  first OCR request). If you're stuck on a small instance, see the
  "lighter alternative" note at the bottom of this file.
- The very first OCR call after a deploy will download EasyOCR's model
  weights to disk (~/.EasyOCR by default). Render's filesystem is writable
  at runtime but is EPHEMERAL (wiped on every deploy/restart), so this
  download will repeat on every deploy. That's normal, but budget for it
  by warming up the model at startup (see `_get_reader()` below) rather
  than on the user's first request.
"""

import io
import re
import threading

import numpy as np
from PIL import Image

# ==============================
# 🎯 ALLOWED FILE TYPES
# ==============================
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "bmp"}


def allowed_file(filename):
    """Check if file extension is allowed"""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ==============================
# 🧠 SINGLETON EASYOCR READER
# ==============================
# Built once (lazily, thread-safely) instead of once-per-request.
_reader = None
_reader_lock = threading.Lock()


def _get_reader():
    global _reader
    if _reader is None:
        with _reader_lock:
            if _reader is None:  # re-check inside the lock
                import easyocr  # imported lazily so app boot doesn't block on it
                # gpu=False is required on Render (no GPU available)
                _reader = easyocr.Reader(["en"], gpu=False)
    return _reader


# ==============================
# 📸 OCR TEXT EXTRACTION
# ==============================
def extract_text_from_image(image_file):
    """
    Extract text from an uploaded image using EasyOCR.

    Args:
        image_file: File object from request.files (Flask FileStorage)

    Returns:
        str: Extracted text
    """
    try:
        img = Image.open(io.BytesIO(image_file.read())).convert("RGB")
    except Exception as e:
        raise Exception(f"Could not read image file: {str(e)}")

    # easyocr needs a numpy array (or path/bytes) - NOT a PIL Image.
    img_array = np.array(img)

    try:
        reader = _get_reader()
        results = reader.readtext(img_array)
    except Exception as e:
        raise Exception(f"OCR extraction failed: {str(e)}")

    extracted_text = "\n".join(item[1] for item in results)
    return extracted_text


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

    return {
        "amount": amount,
        "category": category,
        "description": text[:100],  # First 100 chars
        "confidence": 0.75 if amount else 0.3,
    }


# ==============================
# 💲 EXTRACT AMOUNT
# ==============================
def extract_amount(text):
    """
    Extract numerical amount from text.
    Looks for: ₹, Rs, Total, Amount, etc.
    """
    text = text.replace("\n", " ").lower()

    patterns = [
        r"total\s*[:=]?\s*₹?\s*rs?\.?\s*(\d+(?:\.\d{2})?)",   # total: ₹500 / total rs 500
        r"amount\s*[:=]?\s*₹?\s*rs?\.?\s*(\d+(?:\.\d{2})?)",  # amount: 500
        r"₹\s*(\d+(?:\.\d{2})?)",                              # ₹500 or ₹500.00
        r"rs\.?\s*(\d+(?:\.\d{2})?)",                          # Rs 500 or Rs. 500
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                continue

    return 0.0


# ==============================
# 🏷️ GUESS CATEGORY
# ==============================
def guess_category(text):
    """Guess expense category from receipt text"""
    text = text.lower()

    category_keywords = {
        "Food": ["restaurant", "cafe", "pizza", "burger", "coffee", "food", "delivery", "swiggy", "zomato", "dine"],
        "Transport": ["uber", "ola", "taxi", "petrol", "gas", "parking", "metro", "train", "bus", "vehicle"],
        "Shopping": ["mall", "store", "shop", "amazon", "flipkart", "retail", "market", "dress", "clothes"],
        "Bills": ["electricity", "water", "internet", "phone", "utility", "bill", "recharge"],
        "Health": ["pharmacy", "doctor", "hospital", "medical", "health", "medicine", "clinic"],
        "Entertainment": ["movie", "cinema", "theater", "game", "spotify", "netflix", "show", "ticket"],
    }

    for category, keywords in category_keywords.items():
        for keyword in keywords:
            if keyword in text:
                return category

    return "Other"


# ==============================
# 🪶 LIGHTER ALTERNATIVE (optional)
# ==============================
# If Render's memory/build limits make easyocr+torch impractical on your
# plan, you can swap this whole module for a Tesseract-based version:
#   1. requirements.txt: pytesseract==0.3.13 (drop easyocr, opencv-*)
#   2. render.yaml buildCommand:
#        apt-get update && apt-get install -y tesseract-ocr && \
#        pip install --upgrade pip && pip install -r requirements.txt
#      (Render's native Python runtime does NOT run apt-get for you -
#       you need a Dockerfile-based service, or Render's "aptfile" style
#       buildpack, to get the tesseract-ocr system binary installed.)
#   3. Never hardcode a Windows path like
#        pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\..."
#      on Linux - just leave tesseract_cmd unset so it uses PATH.
