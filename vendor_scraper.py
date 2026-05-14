from playwright.sync_api import sync_playwright
from urllib.parse import quote_plus
import re
import pandas as pd

VENDORS = {
    "Home Depot": "https://www.homedepot.ca/search?q={query}",
    "RONA": "https://www.rona.ca/search?query={query}",
}

def extract_prices(text):
    raw_prices = re.findall(r"\$ ?([0-9]+(?:\.[0-9]{2})?)", text)
    prices = []

    for p in raw_prices:
        value = float(p)
        if 0.25 <= value <= 5000:
            prices.append(value)

    return prices

def search_one_vendor(page, vendor, search_url, keyword):
    url = search_url.format(query=quote_plus(keyword))

    try:
        page.goto(url, wait_until="load", timeout=60000)
        page.wait_for_timeout(5000)

        try:
            page.get_by_text("Accept All").click(timeout=2000)
        except:
            pass

        text = page.locator("body").inner_text()
        prices = extract_prices(text)

        return {
            "Vendor": vendor,
            "Keyword Used": keyword,
            "Lowest Possible Price": min(prices) if prices else None,
            "Prices Found": prices[:8],
            "Search URL": url,
            "Status": "OK" if prices else "No price found",
        }

    except Exception as e:
        return {
            "Vendor": vendor,
            "Keyword Used": keyword,
            "Lowest Possible Price": None,
            "Prices Found": [],
            "Search URL": url,
            "Status": str(e)[:120],
        }

def search_material_across_vendors(material_profile):
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        for vendor, search_url in VENDORS.items():
            for keyword in material_profile["search_keywords"]:
                result = search_one_vendor(page, vendor, search_url, keyword)
                result["Material"] = material_profile["material"]
                result["Category"] = material_profile["category"]
                result["Coverage Qty"] = material_profile["coverage_qty"]
                result["Coverage Unit"] = material_profile["coverage_unit"]
                result["Store Unit"] = material_profile["store_unit"]
                results.append(result)

        browser.close()

    df = pd.DataFrame(results)

    if "Lowest Possible Price" in df.columns:
        df["Standardized Price"] = df["Lowest Possible Price"] / df["Coverage Qty"]

    return df