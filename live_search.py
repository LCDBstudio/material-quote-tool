import os
import re
import requests
import streamlit as st

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


def get_serpapi_key():
    key = os.getenv("SERPAPI_KEY")

    if not key:
        try:
            key = st.secrets["SERPAPI_KEY"]
        except Exception:
            key = None

    return key


def infer_product_data(title):
    text = str(title).lower()

    if any(word in text for word in ["screw", "screws", "nail", "nails", "anchor", "bolt"]):
        match = re.search(r"(\d+)\s*[- ]?\s*(pack|pc|pcs|piece|pieces|count|ct)", text)
        qty = int(match.group(1)) if match else 1
        return qty, "qty", "box", f"{qty} count box", "qty"

    if any(word in text for word in ["paint", "primer", "stain", "sealer"]):
        if "18.9" in text or "18.96" in text or "5 gal" in text:
            return 1900, "sf", "pail", "18.9 L / 5 gal pail", "sf"
        if "3.78" in text or "3.66" in text or "1 gal" in text or "gallon" in text:
            return 400, "sf", "can", "1 gal / 3.78 L can", "sf"
        return 400, "sf", "can", "assumed 1 gal paint can", "sf"

    if any(word in text for word in ["baseboard", "trim", "moulding", "molding", "casing"]):
        return 8, "ln ft", "piece", "8 linear ft piece", "ln ft"

    if any(word in text for word in ["flooring", "vinyl plank", "laminate", "lvp"]):
        return 20, "sf", "box", "assumed 20 sf / box", "sf"

    if any(word in text for word in ["insulation", "batt", "rockwool", "fiberglass"]):
        return 78, "sf", "bag", "assumed 78 sf / bag", "sf"

    if any(word in text for word in ["drywall", "gypsum", "sheetrock", "plywood", "osb", "sheathing", "panel"]):
        if re.search(r"4\s*[x×]\s*12", text):
            return 48, "sf", "sheet", "4 ft x 12 ft", "sf"
        if re.search(r"4\s*[x×]\s*10", text):
            return 40, "sf", "sheet", "4 ft x 10 ft", "sf"
        return 32, "sf", "sheet", "4 ft x 8 ft", "sf"

    return 1, "qty", "each", "single unit / verify", "qty"


def search_google_shopping(query):
    serpapi_key = get_serpapi_key()

    if not serpapi_key:
        raise ValueError("SERPAPI_KEY is missing from Streamlit Secrets or .env.")

    params = {
        "engine": "google_shopping",
        "q": query,
        "google_domain": "google.ca",
        "gl": "ca",
        "hl": "en",
        "location": "Vancouver, British Columbia, Canada",
        "api_key": serpapi_key,
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
        price = item.get("extracted_price")

        coverage_qty, coverage_unit, store_unit, product_size, takeoff_unit = infer_product_data(title)

        results.append({
            "Vendor": item.get("source", ""),
            "Product": title,
            "Price": price,
            "Displayed Price": item.get("price", ""),
            "Product URL": item.get("product_link") or item.get("link", ""),
            "Coverage Qty": coverage_qty,
            "Coverage Unit": coverage_unit,
            "Store Unit": store_unit,
            "Product Size": product_size,
            "Takeoff Unit": takeoff_unit,
        })

    return results