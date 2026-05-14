import re


def normalize_text(text):
    return str(text).lower().strip()


def classify_material(query):
    text = normalize_text(query)

    if any(w in text for w in ["tape", "foil tape", "tuck tape", "drywall tape", "painters tape"]):
        return "tape"

    if any(w in text for w in ["drywall", "gypsum", "sheetrock"]):
        return "sheet_goods"

    if any(w in text for w in ["plywood", "osb", "sheathing", "panel"]):
        return "sheet_goods"

    if any(w in text for w in ["paint", "primer", "stain", "sealer"]):
        return "paint"

    if any(w in text for w in ["baseboard", "trim", "moulding", "molding", "casing"]):
        return "linear_trim"

    if any(w in text for w in ["insulation", "batt", "rockwool", "fiberglass", "fibreglass"]):
        return "insulation"

    if any(w in text for w in ["flooring", "vinyl plank", "laminate", "lvp", "hardwood"]):
        return "flooring"

    if any(w in text for w in ["screw", "screws", "nail", "nails", "anchor", "bolt", "fastener"]):
        return "fasteners"

    return "general_qty"


def get_material_questions(material_type):
    questions = {
        "tape": {
            "takeoff_unit": "ln ft",
            "clarifier_label": "What kind of tape?",
            "options": [
                "Drywall joint tape",
                "HVAC foil tape",
                "Sheathing / Tuck tape",
                "Painter's tape",
                "Flooring seam tape",
                "Masking tape",
                "Other tape",
            ],
            "default_coverage": 250,
            "coverage_unit": "ln ft",
            "store_unit": "roll",
        },
        "sheet_goods": {
            "takeoff_unit": "sf",
            "clarifier_label": "What sheet size?",
            "options": [
                "4 ft x 8 ft",
                "4 ft x 10 ft",
                "4 ft x 12 ft",
                "2 ft x 4 ft",
            ],
            "default_coverage": 32,
            "coverage_unit": "sf",
            "store_unit": "sheet",
        },
        "paint": {
            "takeoff_unit": "sf",
            "clarifier_label": "What container size?",
            "options": [
                "1 gallon / 3.78L can",
                "5 gallon / 18.9L pail",
                "quart / 946ml",
            ],
            "default_coverage": 400,
            "coverage_unit": "sf",
            "store_unit": "can",
        },
        "linear_trim": {
            "takeoff_unit": "ln ft",
            "clarifier_label": "What trim length?",
            "options": [
                "8 ft piece",
                "10 ft piece",
                "12 ft piece",
                "Priced per linear foot",
            ],
            "default_coverage": 8,
            "coverage_unit": "ln ft",
            "store_unit": "piece",
        },
        "insulation": {
            "takeoff_unit": "sf",
            "clarifier_label": "What insulation type?",
            "options": [
                "Batt insulation",
                "Rockwool insulation",
                "Fiberglass insulation",
                "Rigid foam board",
            ],
            "default_coverage": 78,
            "coverage_unit": "sf",
            "store_unit": "bag",
        },
        "flooring": {
            "takeoff_unit": "sf",
            "clarifier_label": "What flooring type?",
            "options": [
                "Vinyl plank flooring",
                "Laminate flooring",
                "Engineered hardwood",
                "Tile flooring",
            ],
            "default_coverage": 20,
            "coverage_unit": "sf",
            "store_unit": "box",
        },
        "fasteners": {
            "takeoff_unit": "qty",
            "clarifier_label": "What fastener package?",
            "options": [
                "100 pack",
                "500 pack",
                "1000 pack",
                "Box count unknown",
            ],
            "default_coverage": 100,
            "coverage_unit": "qty",
            "store_unit": "box",
        },
        "general_qty": {
            "takeoff_unit": "qty",
            "clarifier_label": "How is this product purchased?",
            "options": [
                "Each",
                "Box",
                "Pack",
                "Set",
            ],
            "default_coverage": 1,
            "coverage_unit": "qty",
            "store_unit": "each",
        },
    }

    return questions.get(material_type, questions["general_qty"])


def coverage_from_clarification(material_type, clarification):
    text = normalize_text(clarification)

    if material_type == "sheet_goods":
        if "4 ft x 12" in text:
            return 48, "sf", "sheet", "4 ft x 12 ft"
        if "4 ft x 10" in text:
            return 40, "sf", "sheet", "4 ft x 10 ft"
        if "2 ft x 4" in text:
            return 8, "sf", "sheet", "2 ft x 4 ft"
        return 32, "sf", "sheet", "4 ft x 8 ft"

    if material_type == "paint":
        if "5 gallon" in text or "18.9" in text:
            return 1900, "sf", "pail", "5 gallon / 18.9L pail"
        if "quart" in text or "946" in text:
            return 100, "sf", "quart", "quart / 946ml"
        return 400, "sf", "can", "1 gallon / 3.78L can"

    if material_type == "tape":
        if "hvac" in text or "foil" in text:
            return 30, "ln ft", "roll", "30 ft foil tape roll"
        if "drywall" in text:
            return 500, "ln ft", "roll", "500 ft drywall tape roll"
        if "tuck" in text or "sheathing" in text:
            return 180, "ln ft", "roll", "180 ft sheathing tape roll"
        if "painter" in text or "masking" in text:
            return 180, "ln ft", "roll", "180 ft painter's tape roll"
        return 250, "ln ft", "roll", "250 ft tape roll"

    if material_type == "linear_trim":
        if "12 ft" in text:
            return 12, "ln ft", "piece", "12 ft piece"
        if "10 ft" in text:
            return 10, "ln ft", "piece", "10 ft piece"
        if "priced per linear foot" in text:
            return 1, "ln ft", "ln ft", "priced per linear foot"
        return 8, "ln ft", "piece", "8 ft piece"

    if material_type == "insulation":
        if "rigid" in text or "foam board" in text:
            return 32, "sf", "sheet", "assumed 4 ft x 8 ft rigid board"
        return 78, "sf", "bag", "assumed 78 sf / bag"

    if material_type == "flooring":
        return 20, "sf", "box", "assumed 20 sf / box"

    if material_type == "fasteners":
        count_match = re.search(r"(\d+)", text)
        qty = int(count_match.group(1)) if count_match else 100
        return qty, "qty", "box", f"{qty} count box"

    return 1, "qty", "each", "single unit"


def build_refined_search_query(base_query, material_type, clarification):
    query_parts = [base_query.strip(), clarification.strip()]

    if material_type == "tape":
        query_parts.append("roll")
    elif material_type == "sheet_goods":
        query_parts.append("building material")
    elif material_type == "paint":
        query_parts.append("interior construction")
    elif material_type == "linear_trim":
        query_parts.append("moulding")
    elif material_type == "insulation":
        query_parts.append("coverage")
    elif material_type == "fasteners":
        query_parts.append("pack")

    return " ".join([q for q in query_parts if q]).strip()


def infer_product_data_from_title(title, fallback_profile):
    text = normalize_text(title)

    material_type = fallback_profile["material_type"]

    if material_type == "tape":
        length_match = re.search(r"(\d+(?:\.\d+)?)\s*(ft|feet|foot)", text)
        if length_match:
            length = float(length_match.group(1))
            return length, "ln ft", "roll", f"{length:g} ft roll", "ln ft"

    if material_type == "sheet_goods":
        if re.search(r"4\s*[x×]\s*12", text):
            return 48, "sf", "sheet", "4 ft x 12 ft", "sf"
        if re.search(r"4\s*[x×]\s*10", text):
            return 40, "sf", "sheet", "4 ft x 10 ft", "sf"
        if re.search(r"4\s*[x×]\s*8", text):
            return 32, "sf", "sheet", "4 ft x 8 ft", "sf"

    if material_type == "paint":
        if "18.9" in text or "18.96" in text or "5 gal" in text:
            return 1900, "sf", "pail", "5 gallon / 18.9L pail", "sf"
        if "946 ml" in text or "quart" in text:
            return 100, "sf", "quart", "quart / 946ml", "sf"
        if "3.78" in text or "1 gal" in text or "gallon" in text:
            return 400, "sf", "can", "1 gallon / 3.78L can", "sf"

    if material_type == "fasteners":
        match = re.search(r"(\d+)\s*[- ]?\s*(pack|pc|pcs|piece|pieces|count|ct)", text)
        if match:
            qty = int(match.group(1))
            return qty, "qty", "box", f"{qty} count box", "qty"

    return (
        fallback_profile["coverage_qty"],
        fallback_profile["coverage_unit"],
        fallback_profile["store_unit"],
        fallback_profile["product_size"],
        fallback_profile["takeoff_unit"],
    )


def make_profile(query, clarification):
    material_type = classify_material(query)
    q = get_material_questions(material_type)
    coverage_qty, coverage_unit, store_unit, product_size = coverage_from_clarification(
        material_type,
        clarification,
    )

    return {
        "material_type": material_type,
        "takeoff_unit": q["takeoff_unit"],
        "coverage_qty": coverage_qty,
        "coverage_unit": coverage_unit,
        "store_unit": store_unit,
        "product_size": product_size,
    }