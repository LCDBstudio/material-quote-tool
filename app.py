import math
import pandas as pd
import streamlit as st

from ai_material_assistant import (
    classify_material,
    get_material_questions,
    make_profile,
    build_refined_search_query,
)
from live_search import search_google_shopping

GST_RATE = 0.05
PST_RATE = 0.07

st.set_page_config(
    page_title="Smart Material Quote Tool",
    layout="wide",
)

st.title("Smart Material Quote Tool")
st.caption("Search a material, answer a few smart questions, then get quote-ready product quantities and pricing.")


def money(value):
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


def style_price_table(df):
    return df.style.format({
        "Total Coverage": "{:,.2f}",
        "Extra Allowance": "{:,.2f}",
        "Unit Price": "${:,.2f}",
        "Subtotal": "${:,.2f}",
        "GST 5%": "${:,.2f}",
        "PST 7%": "${:,.2f}",
        "Total": "${:,.2f}",
    })


st.subheader("1. What material do you need?")

query = st.text_input(
    "Material search",
    placeholder="Examples: drywall tape, HVAC foil tape, drywall 4x8, paint 18.9L, baseboard, screws",
)

if not query:
    st.info("Type a material to start.")
    st.stop()

material_type = classify_material(query)
questions = get_material_questions(material_type)

st.subheader("2. Quick clarification")

clarification = st.selectbox(
    questions["clarifier_label"],
    questions["options"],
)

profile = make_profile(query, clarification)

refined_query = build_refined_search_query(query, material_type, clarification)

col1, col2, col3, col4 = st.columns(4)

col1.metric("Detected Type", material_type.replace("_", " ").title())
col2.metric("Takeoff Unit", profile["takeoff_unit"])
col3.metric("Store Unit", profile["store_unit"])
col4.metric("Expected Coverage", f"{profile['coverage_qty']} {profile['coverage_unit']}")

with st.expander("Search query used"):
    st.write(refined_query)

st.subheader("3. Find live products")

if st.button("Search Live Products"):
    with st.spinner("Searching live products..."):
        products = search_google_shopping(refined_query, profile)
        st.session_state["products_df"] = pd.DataFrame(products)
        st.session_state["profile"] = profile
        st.session_state["query"] = query

if "products_df" not in st.session_state:
    st.info("Click Search Live Products to continue.")
    st.stop()

products_df = st.session_state["products_df"]

if products_df.empty:
    st.warning("No products found. Try a more specific search.")
    st.stop()

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
    use_container_width=True,
)

st.subheader("4. Confirm product and quantity")

product_options = [
    f"{row['Vendor']} | {row['Product']} | {row['Displayed Price']}"
    for _, row in products_df.iterrows()
]

selected_option = st.selectbox(
    "Select the product you want to price",
    product_options,
)

selected_index = product_options.index(selected_option)
selected_product = products_df.iloc[selected_index]

c1, c2, c3, c4 = st.columns(4)

c1.metric("Product Size", selected_product["Product Size"])
c2.metric("Input Unit", selected_product["Takeoff Unit"])
c3.metric("Coverage / Unit", f"{selected_product['Coverage Qty']} {selected_product['Coverage Unit']}")
c4.metric("Order Unit", selected_product["Store Unit"])

required_qty = st.number_input(
    f"Required quantity ({selected_product['Takeoff Unit']})",
    min_value=0.0,
    value=100.0,
    step=1.0,
)

contingency_percent = st.number_input(
    "Contingency / waste allowance (%)",
    min_value=0.0,
    value=10.0,
    step=1.0,
)

adjusted_qty = required_qty * (1 + contingency_percent / 100)
coverage_qty = float(selected_product["Coverage Qty"])
order_qty = math.ceil(adjusted_qty / coverage_qty)
total_coverage = order_qty * coverage_qty

q1, q2, q3 = st.columns(3)

q1.metric("With Contingency", f"{adjusted_qty:,.2f} {selected_product['Takeoff Unit']}")
q2.metric("Order Qty", f"{order_qty} {selected_product['Store Unit']}")
q3.metric("Total Coverage", f"{total_coverage:,.2f} {selected_product['Coverage Unit']}")

st.subheader("5. Vendor pricing")

pricing_df = build_pricing_table(
    products_df=products_df,
    required_qty=required_qty,
    contingency_percent=contingency_percent,
)

if pricing_df.empty:
    st.warning("No usable prices found.")
    st.stop()

st.dataframe(
    style_price_table(pricing_df),
    use_container_width=True,
)

best = pricing_df.sort_values("Total").iloc[0]

st.success(
    f"Best option: {best['Vendor']} — order {int(best['Order Qty'])} {best['Order Unit']} — total with tax {money(best['Total'])}"
)

st.subheader("6. Invoice / quote line")

scope_name = st.text_input(
    "Scope name",
    value=query.title(),
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
    use_container_width=True,
)

csv = invoice_df.to_csv(index=False).encode("utf-8")

st.download_button(
    "Download quote line CSV",
    csv,
    file_name="material_quote_line.csv",
    mime="text/csv",
)