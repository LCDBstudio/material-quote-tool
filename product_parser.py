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


def find_coverage_sf(text):
    patterns = [
        r"covers?\s*(?:up\s*to\s*)?(\d+(?:\.\d+)?)\s*(?:to|-)\s*(\d+(?:\.\d+)?)\s*(?:sq\.?\s*ft|square feet|sf)",
        r"(\d+(?:\.\d+)?)\s*(?:to|-)\s*(\d+(?:\.\d+)?)\s*(?:sq\.?\s*ft|square feet|sf)",
        r"covers?\s*(?:up\s*to\s*)?(\d+(?:\.\d+)?)\s*(?:sq\.?\s*ft|square feet|sf)",
        r"(\d+(?:\.\d+)?)\s*(?:sq\.?\s*ft|square feet|sf)\s*(?:per|/)\s*(?:gallon|gal|can|pail|box|bag)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            nums = [float(x) for x in match.groups() if x]
            if nums:
                return min(nums)

    return None


def find_linear_feet(text):
    patterns = [
        r"(\d+(?:\.\d+)?)\s*(?:linear\s*)?(?:ft|feet|foot)\s*(?:roll|per roll)?",
        r"(\d+(?:\.\d+)?)\s*(?:ft|feet|foot)\s*x",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return float(match.group(1))

    return None


def find_pack_count(text):
    match = re.search(r"(\d+)\s*[- ]?\s*(pack|pc|pcs|piece|pieces|count|ct)", text)
    if match:
        return int(match.group(1))
    return None


def parse_product_specs(title="", description="", url=""):
    page_text = extract_text_from_url(url)

    text = " ".join([
        str(title),
        str(description),
        page_text,
    ]).lower()

    result = {
        "coverage_qty": None,
        "coverage_unit": None,
        "store_unit": None,
        "product_size": None,
        "takeoff_unit": None,
        "confidence": "Low",
        "reason": "Could not verify product specs from product page.",
        "source": "Unknown",
    }

    # Tape / roll goods
    if "tape" in text:
        length = find_linear_feet(text)

        if length:
            result.update({
                "coverage_qty": length,
                "coverage_unit": "ln ft",
                "store_unit": "roll",
                "product_size": f"{length:g} ft roll",
                "takeoff_unit": "ln ft",
                "confidence": "High",
                "reason": "Verified tape roll length from product text.",
                "source": "Product text",
            })
            return result

        result.update({
            "coverage_qty": 250,
            "coverage_unit": "ln ft",
            "store_unit": "roll",
            "product_size": "estimated 250 ft roll",
            "takeoff_unit": "ln ft",
            "confidence": "Medium",
            "reason": "Tape detected, but roll length was not verified. Please confirm.",
            "source": "Estimate",
        })
        return result

    # Paint / primer / coating
    if any(w in text for w in ["paint", "primer", "stain", "sealer"]):
        coverage = find_coverage_sf(text)

        if "18.9" in text or "18.96" in text or "5 gal" in text or "5-gal" in text:
            size = "5 gallon / 18.9L pail"
            unit = "pail"
            fallback = 1500
        elif "946 ml" in text or "quart" in text:
            size = "quart / 946ml"
            unit = "quart"
            fallback = 75
        else:
            size = "1 gallon / 3.78L can"
            unit = "can"
            fallback = 300

        if coverage:
            result.update({
                "coverage_qty": coverage,
                "coverage_unit": "sf",
                "store_unit": unit,
                "product_size": size,
                "takeoff_unit": "sf",
                "confidence": "High",
                "reason": "Verified coverage from product text.",
                "source": "Product text",
            })
            return result

        result.update({
            "coverage_qty": fallback,
            "coverage_unit": "sf",
            "store_unit": unit,
            "product_size": f"{size} / estimated coverage",
            "takeoff_unit": "sf",
            "confidence": "Medium",
            "reason": "Coverage was not verified. Conservative estimate used.",
            "source": "Conservative estimate",
        })
        return result

    # Sheet goods
    if any(w in text for w in ["drywall", "gypsum", "sheetrock", "plywood", "osb", "panel", "sheathing", "cement board", "mdf"]):
        if re.search(r"4\s*[x×]\s*12", text):
            size, sf = "4 ft x 12 ft", 48
        elif re.search(r"4\s*[x×]\s*10", text):
            size, sf = "4 ft x 10 ft", 40
        elif re.search(r"4\s*[x×]\s*8", text):
            size, sf = "4 ft x 8 ft", 32
        elif re.search(r"2\s*[x×]\s*4", text):
            size, sf = "2 ft x 4 ft", 8
        else:
            size, sf = "assumed 4 ft x 8 ft", 32

        result.update({
            "coverage_qty": sf,
            "coverage_unit": "sf",
            "store_unit": "sheet",
            "product_size": size,
            "takeoff_unit": "sf",
            "confidence": "High" if "assumed" not in size else "Medium",
            "reason": "Detected sheet material size." if "assumed" not in size else "Sheet size was not verified. Assumed 4 ft x 8 ft.",
            "source": "Product text" if "assumed" not in size else "Estimate",
        })
        return result

    # Flooring / insulation coverage
    if any(w in text for w in ["flooring", "vinyl plank", "laminate", "lvp", "insulation", "batt", "rockwool", "fiberglass"]):
        coverage = find_coverage_sf(text)

        if coverage:
            store_unit = "bag" if "insulation" in text or "batt" in text else "box"

            result.update({
                "coverage_qty": coverage,
                "coverage_unit": "sf",
                "store_unit": store_unit,
                "product_size": f"{coverage:g} sf / {store_unit}",
                "takeoff_unit": "sf",
                "confidence": "High",
                "reason": "Verified square footage coverage from product text.",
                "source": "Product text",
            })
            return result

        fallback = 78 if "insulation" in text or "batt" in text else 20
        store_unit = "bag" if "insulation" in text or "batt" in text else "box"

        result.update({
            "coverage_qty": fallback,
            "coverage_unit": "sf",
            "store_unit": store_unit,
            "product_size": f"estimated {fallback:g} sf / {store_unit}",
            "takeoff_unit": "sf",
            "confidence": "Medium",
            "reason": "Coverage was not verified. Estimate used.",
            "source": "Estimate",
        })
        return result

    # Fasteners / packs
    if any(w in text for w in ["screw", "screws", "nail", "nails", "anchor", "bolt"]):
        qty = find_pack_count(text)

        if qty:
            result.update({
                "coverage_qty": qty,
                "coverage_unit": "qty",
                "store_unit": "box",
                "product_size": f"{qty} count",
                "takeoff_unit": "qty",
                "confidence": "High",
                "reason": "Verified package count from product text.",
                "source": "Product text",
            })
            return result

        result.update({
            "coverage_qty": 1,
            "coverage_unit": "qty",
            "store_unit": "each",
            "product_size": "count unknown",
            "takeoff_unit": "qty",
            "confidence": "Low",
            "reason": "Package count was not verified. Please confirm manually.",
            "source": "Unknown",
        })
        return result

    return result