import re
import requests

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except Exception:
    BS4_AVAILABLE = False


def extract_text_from_url(url):
    if not url or not BS4_AVAILABLE:
        return ""

    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        return " ".join(soup.get_text(" ").split())

    except Exception:
        return ""


def parse_product_specs(title="", description="", url=""):
    text = " ".join([
        str(title),
        str(description),
        extract_text_from_url(url),
    ]).lower()

    result = {
        "coverage_qty": None,
        "coverage_unit": None,
        "store_unit": None,
        "product_size": None,
        "takeoff_unit": None,
        "confidence": "Low",
        "reason": "Could not verify product specs from product page.",
    }

    if "tape" in text:
        match = re.search(r"(\d+(?:\.\d+)?)\s*(ft|feet|foot)", text)
        length = float(match.group(1)) if match else 250

        result.update({
            "coverage_qty": length,
            "coverage_unit": "ln ft",
            "store_unit": "roll",
            "product_size": f"{length:g} ft roll",
            "takeoff_unit": "ln ft",
            "confidence": "High" if match else "Medium",
            "reason": "Detected tape roll length." if match else "Detected tape, roll length assumed.",
        })
        return result

    if any(w in text for w in ["drywall", "gypsum", "sheetrock", "plywood", "osb", "panel", "sheathing"]):
        if re.search(r"4\s*[x×]\s*12", text):
            size, sf = "4 ft x 12 ft", 48
        elif re.search(r"4\s*[x×]\s*10", text):
            size, sf = "4 ft x 10 ft", 40
        elif re.search(r"4\s*[x×]\s*8", text):
            size, sf = "4 ft x 8 ft", 32
        else:
            size, sf = "assumed 4 ft x 8 ft", 32

        result.update({
            "coverage_qty": sf,
            "coverage_unit": "sf",
            "store_unit": "sheet",
            "product_size": size,
            "takeoff_unit": "sf",
            "confidence": "High" if "assumed" not in size else "Medium",
            "reason": "Detected sheet material size.",
        })
        return result

    if any(w in text for w in ["paint", "primer", "stain", "sealer"]):
        if "18.9" in text or "18.96" in text or "5 gal" in text:
            coverage, size, unit = 1900, "5 gallon / 18.9L pail", "pail"
        elif "946 ml" in text or "quart" in text:
            coverage, size, unit = 100, "quart / 946ml", "quart"
        else:
            coverage, size, unit = 400, "1 gallon / 3.78L can", "can"

        result.update({
            "coverage_qty": coverage,
            "coverage_unit": "sf",
            "store_unit": unit,
            "product_size": size,
            "takeoff_unit": "sf",
            "confidence": "Medium",
            "reason": "Detected coating product; coverage is estimated.",
        })
        return result

    if any(w in text for w in ["screw", "screws", "nail", "nails", "anchor", "bolt"]):
        match = re.search(r"(\d+)\s*[- ]?\s*(pack|pc|pcs|piece|pieces|count|ct)", text)
        qty = int(match.group(1)) if match else 1

        result.update({
            "coverage_qty": qty,
            "coverage_unit": "qty",
            "store_unit": "box" if qty > 1 else "each",
            "product_size": f"{qty} count",
            "takeoff_unit": "qty",
            "confidence": "High" if qty > 1 else "Medium",
            "reason": "Detected package count.",
        })
        return result

    return result