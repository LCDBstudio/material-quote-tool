import math
import pandas as pd
import streamlit as st

try:
    from live_search import search_google_shopping
except Exception:
    search_google_shopping = None

GST_RATE = 0.05
PST_RATE = 0.07

st.set_page_config(
    page_title="Live Material Quote Tool",
    layout="wide"
)

st.title("Live Material Quote Tool")
st.caption("Search live products, confirm the correct item, then calculate order quantity and invoice pricing.")


def format_money(value):
    return f"${value:,.2f}"


def build_pricing_table(products_df, required_qty, contingency_percent):
    adjusted_qty = required_qty * (1 + contingency_percent / 100)
    rows = []

    for _, row in products_df.iterrows():
        price = row.get("Price")

        if pd.isna(price) or price is None:
            continue

        coverage_qty = float(row.get("Coverage Qty", 1))
        coverage_unit = row.get("Coverage Unit", "qty")
        store_unit = row.get("Store Unit", "each")
        takeoff_unit = row.get("Takeoff Unit", "qty")

        qty_to_buy = math.ceil(adjusted_qty / coverage_qty)
        total_coverage = qty_to_buy * coverage_qty
        extra_allowance = total_coverage - required_qty

        subtotal = qty_to_buy * float(price)
        gst = subtotal * GST_RATE
        pst = subtotal * PST_RATE
        total = subtotal + gst + pst

        rows.append({
            "Vendor": row.get("Vendor", ""),
            "Product": row.get("Product", ""),
            "Product Size": row.get("Product Size", ""),
            "Takeoff Unit": takeoff_unit,
            "Coverage / Unit": f"{coverage_qty:g} {coverage_unit}",
            "Order Qty": qty_to_buy,
            "Order Unit": store_unit,
            "Total Coverage": total_coverage,
            "Extra Allowance": extra_allowance,
            "Unit Price": float(price),
            "Subtotal": subtotal,
            "GST 5%": gst,
            "PST 7%": pst,
            "Total": total,
            "Product URL": row.get("Product URL", ""),
        })

    return pd.DataFrame(rows)


def style_money(df):
    return df.style.format({
        "Total Coverage": "{:,.2f}",
        "Extra Allowance": "{:,.2f}",
        "Unit Price": "${:,.2f}",
        "Subtotal": "${:,.2f}",
        "GST 5%": "${:,.2f}",
        "PST 7%": "${:,.2f}",
        "Total": "${:,.2f}",
    })


st.subheader("1. Search Product")

query = st.text_input(
    "Material search",
    value="drywall screws",
    placeholder="Examples: drywall 4x8, drywall screws, paint 18.9L, baseboard, insulation, vinyl plank"
)

if not query:
    st.info("Type a product to search.")
    st.stop()

if search_google_shopping is None:
    st.error("Live search is not available. Check that live_search.py exists and your .env file has SERPAPI_KEY.")
    st.stop()

if st.button("Search Live Products"):
    st.session_state["last_query"] = query
    with st.spinner("Searching live products..."):
        st.session_state["products"] = pd.DataFrame(search_google_shopping(query))

if "products" not in st.session_state:
    st.info("Click Search Live Products to begin.")
    st.stop()

products_df = st.session_state["products"]

if products_df.empty:
    st.warning("No products found. Try a more specific search.")
    st.stop()

st.subheader("2. Select Correct Product")

st.dataframe(
    products_df[
        [
            "Vendor",
            "Product",
            "Displayed Price",
            "Price",
            "Product Size",
            "Takeoff Unit",
            "Coverage Qty",
            "Coverage Unit",
            "Store Unit",
            "Product URL",
        ]
    ],
    use_container_width=True
)

product_options = [
    f"{row['Vendor']} | {row['Product']} | {row['Displayed Price']}"
    for _, row in products_df.iterrows()
]

selected_option = st.selectbox(
    "Choose the product you want to price",
    product_options
)

selected_index = product_options.index(selected_option)
selected_product = products_df.iloc[selected_index]

st.subheader("3. Product Data")

c1, c2, c3, c4 = st.columns(4)

c1.metric("Detected Type", selected_product["Takeoff Unit"])
c2.metric("Product Size", selected_product["Product Size"])
c3.metric("Coverage / Unit", f"{selected_product['Coverage Qty']} {selected_product['Coverage Unit']}")
c4.metric("Store Unit", selected_product["Store Unit"])

st.info(
    "Coverage is automatically inferred from product type. If it looks wrong, choose a more specific product search."
)

st.subheader("4. Enter Required Quantity")

required_qty = st.number_input(
    f"Required quantity ({selected_product['Takeoff Unit']})",
    min_value=0.0,
    value=100.0,
    step=1.0
)

contingency_percent = st.number_input(
    "Contingency / waste allowance (%)",
    min_value=0.0,
    value=10.0,
    step=1.0
)

adjusted_qty = required_qty * (1 + contingency_percent / 100)
coverage_qty = float(selected_product["Coverage Qty"])
order_qty = math.ceil(adjusted_qty / coverage_qty)
total_coverage = order_qty * coverage_qty

q1, q2, q3 = st.columns(3)

q1.metric("With Contingency", f"{adjusted_qty:,.2f} {selected_product['Takeoff Unit']}")
q2.metric("Order Qty", f"{order_qty} {selected_product['Store Unit']}")
q3.metric("Total Coverage", f"{total_coverage:,.2f} {selected_product['Coverage Unit']}")

st.subheader("5. Pricing Options")

pricing_df = build_pricing_table(
    products_df=products_df,
    required_qty=required_qty,
    contingency_percent=contingency_percent
)

if pricing_df.empty:
    st.warning("No products with usable prices found.")
    st.stop()

st.dataframe(
    style_money(pricing_df),
    use_container_width=True
)

best = pricing_df.sort_values("Total").iloc[0]

st.success(
    f"Best option: {best['Vendor']} — order {int(best['Order Qty'])} {best['Order Unit']} — total with tax {format_money(best['Total'])}"
)

st.subheader("6. Invoice / Quote Line")

scope_name = st.text_input(
    "Scope name",
    value=query.title()
)

invoice_df = pd.DataFrame([{
    "Scope": scope_name,
    "Material": best["Product"],
    "Vendor": best["Vendor"],
    "Takeoff Qty": required_qty,
    "Takeoff Unit": selected_product["Takeoff Unit"],
    "Contingency %": contingency_percent,
    "Order Qty": int(best["Order Qty"]),
    "Order Unit": best["Order Unit"],
    "Unit Price": best["Unit Price"],
    "Subtotal": best["Subtotal"],
    "GST 5%": best["GST 5%"],
    "PST 7%": best["PST 7%"],
    "Total": best["Total"],
    "Product URL": best["Product URL"],
}])

st.dataframe(
    invoice_df.style.format({
        "Takeoff Qty": "{:,.2f}",
        "Contingency %": "{:,.1f}",
        "Unit Price": "${:,.2f}",
        "Subtotal": "${:,.2f}",
        "GST 5%": "${:,.2f}",
        "PST 7%": "${:,.2f}",
        "Total": "${:,.2f}",
    }),
    use_container_width=True
)

csv = invoice_df.to_csv(index=False).encode("utf-8")

st.download_button(
    "Download quote line CSV",
    csv,
    file_name="material_quote_line.csv",
    mime="text/csv"
)