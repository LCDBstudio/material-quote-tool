from playwright.sync_api import sync_playwright
from urllib.parse import quote_plus
import re

def extract_price(text):
    match = re.search(r"\$?\s*([0-9]+(?:\.[0-9]{2})?)", text.replace(",", ""))
    return float(match.group(1)) if match else None

def get_home_depot_price(search_term="2x4x8 stud", postal_code="V6X 1A1"):
    search_url = "https://www.homedepot.ca/search?q=" + quote_plus(search_term)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False) browser = p.chromium.launch(headless=True)
        page = browser.new_page()

       page.goto(search_url, wait_until="load", timeout=60000)
        page.wait_for_timeout(4000)

        try:
            page.get_by_text("Accept All").click(timeout=3000)
        except:
            pass

        try:
            page.get_by_placeholder("Postal Code, City, or Store Number").fill(postal_code)
            page.keyboard.press("Enter")
            page.wait_for_timeout(4000)
            page.get_by_text("Select").first.click(timeout=5000)
            page.wait_for_timeout(6000)
        except:
            pass

        body_text = page.locator("body").inner_text()
        browser.close()

        price = extract_price(body_text)

        return {
            "Material": search_term,
            "Supplier": "Home Depot",
            "Postal Code": postal_code,
            "Price": price,
        }

if __name__ == "__main__":
    print(get_home_depot_price())