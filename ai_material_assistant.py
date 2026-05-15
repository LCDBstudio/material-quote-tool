import re


def normalize_text(text):
    return str(text).lower().strip()


def classify_material(query):
    text = normalize_text(query)

    if "tape" in text:
        return "tape"

    if any(w in text for w in ["drywall", "gypsum", "sheetrock", "plywood", "osb", "panel", "sheathing", "cement board", "mdf"]):
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
    return {
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
        },
        "paint": {
            "takeoff_unit": "sf",
            "clarifier_label": "What container size?",
            "options": [
                "1 gallon / 3.78L can",
                "5 gallon / 18.9L pail",
                "quart / 946ml",
            ],
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
        },
        "fasteners": {
            "takeoff_unit": "qty",
            "clarifier_label": "What package size?",
            "options": [
                "100 pack",
                "500 pack",
                "1000 pack",
                "Box count unknown",
            ],
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
        },
    }.get(material_type)


def sheet_coverage(sheet_size):
    text = normalize_text(sheet_size)

    if "4 ft x 12" in text:
        return 48, "4 ft x 12 ft"

    if "4 ft x 10" in text:
        return 40, "4 ft x 10 ft"

    if "2 ft x 4" in text:
        return 8, "2 ft x 4 ft"

    return 32, "4 ft x 8 ft"


def coverage_from_clarification(material_type, clarification):
    text = normalize_text(clarification)

    if material_type == "sheet_goods":
        sf, size = sheet_coverage(clarification)
        return sf, "sf", "sheet", size, "sf"

    if material_type == "paint":
        if "5 gallon" in text or "18.9" in text:
            return 1900, "sf", "pail", "5 gallon / 18.9L pail", "sf"
        if "quart" in text or "946" in text:
            return 100, "sf", "quart", "quart / 946ml", "sf"
        return 400, "sf", "can", "1 gallon / 3.78L can", "sf"

    if material_type == "tape":
        if "hvac" in text or "foil" in text:
            return 30, "ln ft", "roll", "30 ft foil tape roll", "ln ft"
        if "drywall" in text:
            return 500, "ln ft", "roll", "500 ft drywall tape roll", "ln ft"
        if "tuck" in text or "sheathing" in text:
            return 180, "ln ft", "roll", "180 ft sheathing tape roll", "ln ft"
        if "painter" in text or "masking" in text:
            return 180, "ln ft", "roll", "180 ft painter's tape roll", "ln ft"
        return 250, "ln ft", "roll", "250 ft tape roll", "ln ft"

    if material_type == "linear_trim":
        if "12 ft" in text:
            return 12, "ln ft", "piece", "12 ft piece", "ln ft"
        if "10 ft" in text:
            return 10, "ln ft", "piece", "10 ft piece", "ln ft"
        if "priced per linear foot" in text:
            return 1, "ln ft", "ln ft", "priced per linear foot", "ln ft"
        return 8, "ln ft", "piece", "8 ft piece", "ln ft"

    if material_type == "insulation":
        if "rigid" in text or "foam" in text:
            return 32, "sf", "sheet", "assumed 4 ft x 8 ft rigid board", "sf"
        return 78, "sf", "bag", "assumed 78 sf / bag", "sf"

    if material_type == "flooring":
        return 20, "sf", "box", "assumed 20 sf / box", "sf"

    if material_type == "fasteners":
        count_match = re.search(r"(\d+)", text)
        qty = int(count_match.group(1)) if count_match else 100
        return qty, "qty", "box", f"{qty} count box", "qty"

    return 1, "qty", "each", "single unit", "qty"


def make_sheet_profile(sheet_material, thickness, sheet_size):
    coverage_qty, product_size = sheet_coverage(sheet_size)

    return {
        "material_type": "sheet_goods",
        "sheet_material": sheet_material,
        "thickness": thickness,
        "sheet_size": sheet_size,
        "takeoff_unit": "sf",
        "coverage_qty": coverage_qty,
        "coverage_unit": "sf",
        "store_unit": "sheet",
        "product_size": f"{thickness} {sheet_material} {product_size}",
        "clarifier_label": "Sheet material filters",
    }


def build_sheet_search_query(sheet_material, thickness, sheet_size):
    return f"{thickness} {sheet_material} {sheet_size}".strip()


def build_refined_search_query(base_query, material_type, clarification):
    parts = [base_query.strip(), clarification.strip()]

    if material_type == "tape":
        parts.append("roll")
    elif material_type == "sheet_goods":
        parts.append("building material")
    elif material_type == "paint":
        parts.append("paint coverage")
    elif material_type == "linear_trim":
        parts.append("moulding trim")
    elif material_type == "insulation":
        parts.append("coverage")
    elif material_type == "fasteners":
        parts.append("pack")

    return " ".join([p for p in parts if p]).strip()


def make_profile(query, clarification):
    material_type = classify_material(query)
    questions = get_material_questions(material_type)

    coverage_qty, coverage_unit, store_unit, product_size, takeoff_unit = coverage_from_clarification(
        material_type,
        clarification,
    )

    return {
        "material_type": material_type,
        "takeoff_unit": takeoff_unit,
        "coverage_qty": coverage_qty,
        "coverage_unit": coverage_unit,
        "store_unit": store_unit,
        "product_size": product_size,
        "clarifier_label": questions["clarifier_label"],
    }


def infer_sheet_data_from_title(title, fallback_profile):
    text = normalize_text(title)

    detected_size = None
    detected_coverage = None

    if re.search(r"4\s*[x×]\s*12", text):
        detected_size = "4 ft x 12 ft"
        detected_coverage = 48
    elif re.search(r"4\s*[x×]\s*10", text):
        detected_size = "4 ft x 10 ft"
        detected_coverage = 40
    elif re.search(r"4\s*[x×]\s*8", text):
        detected_size = "4 ft x 8 ft"
        detected_coverage = 32
    else:
        detected_size = fallback_profile.get("sheet_size", "4 ft x 8 ft")
        detected_coverage = fallback_profile.get("coverage_qty", 32)

    thickness = fallback_profile.get("thickness", "")
    sheet_material = fallback_profile.get("sheet_material", "")

    thickness_ok = normalize_text(thickness).replace(" ", "") in text.replace(" ", "")
    material_ok = normalize_text(sheet_material).split()[0] in text

    confidence = "High" if thickness_ok and material_ok else "Medium"

    return (
        detected_coverage,
        "sf",
        "sheet",
        f"{thickness} {sheet_material} {detected_size}".strip(),
        "sf",
        confidence,
    )


def infer_product_data_from_title(title, fallback_profile):
    text = normalize_text(title)
    material_type = fallback_profile["material_type"]

    confidence = "Medium"

    if material_type == "sheet_goods":
        return infer_sheet_data_from_title(title, fallback_profile)

    if material_type == "tape":
        match = re.search(r"(\d+(?:\.\d+)?)\s*(ft|feet|foot)", text)
        if match:
            length = float(match.group(1))
            return length, "ln ft", "roll", f"{length:g} ft roll", "ln ft", "High"

    if material_type == "paint":
        if "18.9" in text or "18.96" in text or "5 gal" in text:
            return 1900, "sf", "pail", "5 gallon / 18.9L pail", "sf", "High"
        if "946 ml" in text or "quart" in text:
            return 100, "sf", "quart", "quart / 946ml", "sf", "High"
        if "3.78" in text or "1 gal" in text or "gallon" in text:
            return 400, "sf", "can", "1 gallon / 3.78L can", "sf", "High"

    if material_type == "fasteners":
        match = re.search(r"(\d+)\s*[- ]?\s*(pack|pc|pcs|piece|pieces|count|ct)", text)
        if match:
            qty = int(match.group(1))
            return qty, "qty", "box", f"{qty} count box", "qty", "High"

    return (
        fallback_profile["coverage_qty"],
        fallback_profile["coverage_unit"],
        fallback_profile["store_unit"],
        fallback_profile["product_size"],
        fallback_profile["takeoff_unit"],
        confidence,
    )