import os
import re
import requests
from dotenv import load_dotenv

load_dotenv()

SERPAPI_KEY = os.getenv("SERPAPI_KEY")


def infer_product_data(title):
    text = str(title).lower()

    # -----------------------------
    # 1. Fasteners / countable items
    # -----------------------------
    if any(word in text for word in [
        "screw", "screws", "nail", "nails", "anchor", "anchors",
        "bolt", "bolts", "washer", "washers", "fastener", "fasteners"
    ]):
        count_patterns = [
            r"(\d+)\s*[- ]?\s*pack",
            r"(\d+)\s*[- ]?\s*pc",
            r"(\d+)\s*[- ]?\s*pcs",
            r"(\d+)\s*[- ]?\s*piece",
            r"(\d+)\s*[- ]?\s*pieces",
            r"(\d+)\s*count",
            r"(\d+)\s*ct",
        ]

        for pattern in count_patterns:
            match = re.search(pattern, text)
            if match:
                qty = int(match.group(1))
                return {
                    "Takeoff Unit": "qty",
                    "Coverage Qty": qty,
                    "Coverage Unit": "qty",
                    "Store Unit": "box",
                    "Product Size": f"{qty} count box"
                }

        return {
            "Takeoff Unit": "qty",
            "Coverage Qty": 1,
            "Coverage Unit": "qty",
            "Store Unit": "box",
            "Product Size": "count unknown / verify"
        }

    # -----------------------------
    # 2. Paint / primer / stain
    # -----------------------------
    if any(word in text for word in ["paint", "primer", "stain", "sealer"]):
        if "18.9" in text or "18.96" in text or "5 gal" in text or "5-gal" in text:
            return {
                "Takeoff Unit": "sf",
                "Coverage Qty": 1900,
                "Coverage Unit": "sf",
                "Store Unit": "pail",
                "Product Size": "18.9 L / 5 gal pail"
            }

        if "3.78" in text or "3.66" in text or "1 gal" in text or "1-gal" in text or "gallon" in text:
            return {
                "Takeoff Unit": "sf",
                "Coverage Qty": 400,
                "Coverage Unit": "sf",
                "Store Unit": "can",
                "Product Size": "1 gal / 3.78 L can"
            }

        if "946 ml" in text or "quart" in text:
            return {
                "Takeoff Unit": "sf",
                "Coverage Qty": 100,
                "Coverage Unit": "sf",
                "Store Unit": "quart",
                "Product Size": "946 ml / quart"
            }

        return {
            "Takeoff Unit": "sf",
            "Coverage Qty": 400,
            "Coverage Unit": "sf",
            "Store Unit": "can",
            "Product Size": "assumed 1 gal paint can"
        }

    # -----------------------------
    # 3. Baseboard / trim / moulding
    # -----------------------------
    if any(word in text for word in ["baseboard", "trim", "moulding", "molding", "casing"]):
        length_match = re.search(r"(\d+(?:\.\d+)?)\s*(ft|feet|foot)", text)

        if length_match:
            length = float(length_match.group(1))
        elif "96" in text and "in" in text:
            length = 8.0
        else:
            length = 8.0

        return {
            "Takeoff Unit": "ln ft",
            "Coverage Qty": length,
            "Coverage Unit": "ln ft",
            "Store Unit": "piece",
            "Product Size": f"{length:g} linear ft piece"
        }

    # -----------------------------
    # 4. Flooring
    # -----------------------------
    if any(word in text for word in ["vinyl plank", "laminate", "engineered hardwood", "flooring", "lvp"]):
        coverage_match = re.search(
            r"(\d+(?:\.\d+)?)\s*(sq\.?\s*ft|square feet|sf)",
            text
        )

        if coverage_match:
            sf = float(coverage_match.group(1))
        else:
            sf = 20.0

        return {
            "Takeoff Unit": "sf",
            "Coverage Qty": sf,
            "Coverage Unit": "sf",
            "Store Unit": "box",
            "Product Size": f"{sf:g} sf / box"
        }

    # -----------------------------
    # 5. Insulation
    # -----------------------------
    if any(word in text for word in ["insulation", "batt", "rockwool", "fiberglass", "fibreglass"]):
        coverage_match = re.search(
            r"(\d+(?:\.\d+)?)\s*(sq\.?\s*ft|square feet|sf)",
            text
        )

        if coverage_match:
            sf = float(coverage_match.group(1))
        else:
            sf = 78.0

        return {
            "Takeoff Unit": "sf",
            "Coverage Qty": sf,
            "Coverage Unit": "sf",
            "Store Unit": "bag",
            "Product Size": f"{sf:g} sf / bag"
        }

    # -----------------------------
    # 6. Sheet goods: drywall / plywood / OSB
    # -----------------------------
    if any(word in text for word in ["drywall", "gypsum", "sheetrock", "plywood", "osb", "sheathing", "panel"]):
        if re.search(r"4\s*[x×]\s*12", text):
            sf = 48
            size = "4 ft x 12 ft"
        elif re.search(r"4\s*[x×]\s*10", text):
            sf = 40
            size = "4 ft x 10 ft"
        elif re.search(r"4\s*[x×]\s*8", text):
            sf = 32
            size = "4 ft x 8 ft"
        elif re.search(r"2\s*[x×]\s*4", text):
            sf = 8
            size = "2 ft x 4 ft"
        else:
            sf = 32
            size = "assumed 4 ft x 8 ft"

        return {
            "Takeoff Unit": "sf",
            "Coverage Qty": sf,
            "Coverage Unit": "sf",
            "Store Unit": "sheet",
            "Product Size": size
        }

    # -----------------------------
    # 7. Generic packs
    # -----------------------------
    pack_match = re.search(r"(\d+)\s*[- ]?\s*pack", text)

    if pack_match:
        qty = int(pack_match.group(1))
        return {
            "Takeoff Unit": "qty",
            "Coverage Qty": qty,
            "Coverage Unit": "qty",
            "Store Unit": "box",
            "Product Size": f"{qty} pack"
        }

    # -----------------------------
    # 8. Fallback
    # -----------------------------
    return {
        "Takeoff Unit": "qty",
        "Coverage Qty": 1,
        "Coverage Unit": "qty",
        "Store Unit": "each",
        "Product Size": "single unit / verify"
    }


def search_google_shopping(query):
    if not SERPAPI_KEY:
        raise ValueError("SERPAPI_KEY missing. Check your .env file.")

    params = {
        "engine": "google_shopping",
        "q": query,
        "google_domain": "google.ca",
        "gl": "ca",
        "hl": "en",
        "location": "Vancouver, British Columbia, Canada",
        "api_key": SERPAPI_KEY,
    }

    response = requests.get(
        "https://serpapi.com/search.json",
        params=params,
        timeout=30
    )

    response.raise_for_status()
    data = response.json()

    results = []

    for item in data.get("shopping_results", []):
        title = item.get("title", "")
        price = item.get("extracted_price", None)

        inferred = infer_product_data(title)

        results.append({
            "Vendor": item.get("source", ""),
            "Product": title,
            "Price": price,
            "Displayed Price": item.get("price", ""),
            "Product URL": item.get("product_link", ""),
            "Takeoff Unit": inferred["Takeoff Unit"],
            "Coverage Qty": inferred["Coverage Qty"],
            "Coverage Unit": inferred["Coverage Unit"],
            "Store Unit": inferred["Store Unit"],
            "Product Size": inferred["Product Size"],
        })

    return results