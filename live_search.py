import os
import requests
import streamlit as st

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from ai_material_assistant import infer_product_data_from_title


def get_serpapi_key():
    key = os.getenv("SERPAPI_KEY")

    if not key:
        try:
            key = st.secrets["SERPAPI_KEY"]
        except Exception:
            key = None

    return key


def search_google_shopping(query, fallback_profile, location="Vancouver, British Columbia, Canada"):
    serpapi_key = get_serpapi_key()

    if not serpapi_key:
        raise ValueError("SERPAPI_KEY is missing from Streamlit Secrets or .env.")

    params = {
        "engine": "google_shopping",
        "q": query,
        "google_domain": "google.ca",
        "gl": "ca",
        "hl": "en",
        "location": location,
        "api_key": serpapi_key,
    }

    response = requests.get(
        "https://serpapi.com/search.json",
        params=params,
        timeout=30,
    )
    response.raise_for_status()

    data = response.json()
    results = []

    for item in data.get("shopping_results", []):
        title = item.get("title", "")
        price = item.get("extracted_price")

        coverage_qty, coverage_unit, store_unit, product_size, takeoff_unit = infer_product_data_from_title(
            title,
            fallback_profile,
        )

        description_parts = []

        if item.get("source"):
            description_parts.append(f"Sold by {item.get('source')}")

        if item.get("delivery"):
            description_parts.append(str(item.get("delivery")))

        if item.get("rating"):
            description_parts.append(f"Rating: {item.get('rating')}")

        if item.get("reviews"):
            description_parts.append(f"{item.get('reviews')} reviews")

        results.append({
            "Vendor": item.get("source", ""),
            "Product": title,
            "Description": " | ".join(description_parts),
            "Thumbnail": item.get("thumbnail", ""),
            "Price": price,
            "Displayed Price": item.get("price", ""),
            "Product URL": item.get("product_link") or item.get("link", ""),
            "Takeoff Unit": takeoff_unit,
            "Coverage Qty": coverage_qty,
            "Coverage Unit": coverage_unit,
            "Store Unit": store_unit,
            "Product Size": product_size,
        })

    return results