import easyocr
import os
from PIL import Image
import io

# ==============================
# 🎯 ALLOWED FILE TYPES
# ==============================
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "bmp"}


def allowed_file(filename):
    """Check if file extension is allowed"""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ==============================
# 📸 OCR TEXT EXTRACTION
# ==============================
def extract_text_from_image(image_file):
    """
    Extract text from image using EasyOCR
    
    Args:
        image_file: File object from request.files
    
    Returns:
        str: Extracted text
    """
    try:
        # Read image
        img = Image.open(io.BytesIO(image_file.read()))
        
        # Initialize reader (en = English)
        reader = easyocr.Reader(['en'])
        
        # Extract text
        results = reader.readtext(img)
        
        # Combine text
        extracted_text = "\n".join([text[1] for text in results])
        
        return extracted_text
    
    except Exception as e:
        raise Exception(f"OCR extraction failed: {str(e)}")


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
    try:
        # Extract text from receipt
        text = extract_text_from_image(image_file)
        
        # Look for amount (₹ or Rs or just numbers)
        amount = extract_amount(text)
        
        # Guess category from keywords
        category = guess_category(text)
        
        return {
            "amount": amount,
            "category": category,
            "description": text[:100],  # First 100 chars
            "confidence": 0.75
        }
    
    except Exception as e:
        raise Exception(f"Receipt parsing failed: {str(e)}")


# ==============================
# 💲 EXTRACT AMOUNT
# ==============================
def extract_amount(text):
    """
    Extract numerical amount from text
    Looks for: ₹, Rs, Total, Amount, etc.
    """
    import re
    
    # Remove newlines and extra spaces
    text = text.replace("\n", " ").lower()
    
    # Look for patterns like "₹500", "Rs 500", "amount: 500"
    patterns = [
        r"₹\s*(\d+(?:\.\d{2})?)",      # ₹500 or ₹500.00
        r"rs\.?\s*(\d+(?:\.\d{2})?)",  # Rs 500 or Rs. 500
        r"total\s*[:=]?\s*₹?\s*(\d+(?:\.\d{2})?)",  # total: 500
        r"amount\s*[:=]?\s*₹?\s*(\d+(?:\.\d{2})?)", # amount: 500
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return float(match.group(1))
    
    # If no pattern found, return 0
    return 0.0


# ==============================
# 🏷️ GUESS CATEGORY
# ==============================
def guess_category(text):
    """
    Guess expense category from receipt text
    """
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
