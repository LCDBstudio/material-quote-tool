import re
import requests
from bs4 import BeautifulSoup


def extract_text_from_url(url):
    if not url:
        return ""

    try:
        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        response = requests.get(url, headers=headers, timeout=12)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        return " ".join(soup.get_text(" ").split())

    except Exception:
        return ""


def parse_product_specs(title="", description="", url=""):
    combined_text = " ".join([
        str(title),
        str(description),
        extract_text_from_url(url)
    ]).lower()

    result = {
        "coverage_qty": None,
        "coverage_unit": None,
        "store_unit": None,
        "product_size": None,
        "takeoff_unit": None,
        "confidence": "Low",
        "reason": "Could not verify product specs from page."
    }

    # Tape / roll goods
    if "tape" in combined_text:
        length_match = re.search(r"(\d+(?:\.\d+)?)\s*(ft|feet|foot)", combined_text)

        if length_match:
            length = float(length_match.group(1))
            result.update({
                "coverage_qty": length,
                "coverage_unit": "ln ft",
                "store_unit": "roll",
                "product_size": f"{length:g} ft roll",
                "takeoff_unit": "ln ft",
                "confidence": "High",
                "reason": "Detected roll length."
            })
            return result

        result.update({
            "coverage_qty": 250,
            "coverage_unit": "ln ft",
            "store_unit": "roll",
            "product_size": "assumed 250 ft roll",
            "takeoff_unit": "ln ft",
            "confidence": "Medium",
            "reason": "Detected tape, but roll length was not confirmed."
        })
        return result

    # Sheet goods
    if any(word in combined_text for word in ["drywall", "gypsum", "sheetrock", "plywood", "osb", "panel", "sheathing"]):
        if re.search(r"4\s*[x×]\s*12", combined_text):
            size, sf = "4 ft x 12 ft", 48
        elif re.search(r"4\s*[x×]\s*10", combined_text):
            size, sf = "4 ft x 10 ft", 40
        elif re.search(r"4\s*[x×]\s*8", combined_text):
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
            "reason": "Detected sheet material size."
        })
        return result

    # Paint
    if any(word in combined_text for word in ["paint", "primer", "stain", "sealer"]):
        if "18.9" in combined_text or "18.96" in combined_text or "5 gal" in combined_text:
            coverage, size, unit = 1900, "5 gallon / 18.9L pail", "pail"
        elif "946 ml" in combined_text or "quart" in combined_text:
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
            "reason": "Detected coating product; coverage is estimated."
        })
        return result

    # Fasteners / packs
    if any(word in combined_text for word in ["screw", "screws", "nail", "nails", "anchor", "bolt"]):
        match = re.search(r"(\d+)\s*[- ]?\s*(pack|pc|pcs|piece|pieces|count|ct)", combined_text)
        qty = int(match.group(1)) if match else 1

        result.update({
            "coverage_qty": qty,
            "coverage_unit": "qty",
            "store_unit": "box" if qty > 1 else "each",
            "product_size": f"{qty} count",
            "takeoff_unit": "qty",
            "confidence": "High" if qty > 1 else "Medium",
            "reason": "Detected package count."
        })
        return result

    return result