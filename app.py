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
MAX_OPTIONS = 5

st.set_page_config(
    page_title="Smart Shopper",
    layout="wide",
)

st.title("Smart Shopper")
st.caption("Search products, compare local options, and create simple quote-ready line items.")


def money(value):
    return f"${value:,.2f}"


def local_score(vendor):
    vendor_text = str(vendor).lower()
    local_vendors = [
        "home depot",
        "rona",
        "canadian tire",
        "lowe",
        "windsor plywood",
        "home hardware",
        "kent",
    ]

    return 1 if any(v in vendor_text for v in local_vendors) else 0


def build_pricing_table(products_df, required_qty, extra_percent):
    adjusted_qty = required_qty * (1 + extra_percent / 100)
    rows = []

    for _, row in products_df.iterrows():
        price = row.get("Price")

        if pd.isna(price) or price is None:
            continue

        coverage_qty = float(row.get("Coverage Qty", 1))
        coverage_unit = row.get("Coverage Unit", "qty")
        store_unit = row.get("Store Unit", "each")

        order_qty = math.ceil(adjusted_qty / coverage_qty)
        total_coverage = order_qty * coverage_qty
        subtotal = order_qty * float(price)
        gst = subtotal * GST_RATE
        pst = subtotal * PST_RATE
        total = subtotal + gst + pst

        rows.append({
            "Local Score": local_score(row.get("Vendor", "")),
            "Vendor": row.get("Vendor", ""),
            "Product": row.get("Product", ""),
            "Description": row.get("Description", ""),
            "Thumbnail": row.get("Thumbnail", ""),
            "Product Size": row.get("Product Size", ""),
            "Confidence": row.get("Confidence", "Medium"),
            "Takeoff Unit": row.get("Takeoff Unit", "qty"),
            "Coverage / Unit": f"{coverage_qty:g} {coverage_unit}",
            "Order Qty": int(order_qty),
            "Order Unit": store_unit,
            "Total Coverage": round(total_coverage),
            "Unit Price": float(price),
            "Subtotal": subtotal,
            "GST 5%": gst,
            "PST 7%": pst,
            "Total": total,
            "Product URL": row.get("Product URL", ""),
        })

    df = pd.DataFrame(rows)

    if not df.empty:
        df = df.sort_values(
            by=["Local Score", "Subtotal"],
            ascending=[False, True]
        ).head(MAX_OPTIONS)

    return df


def show_option_card(row, index):
    with st.container(border=True):
        st.markdown(f"### Option {index + 1}: {row['Vendor']}")

        if row["Confidence"] == "High":
            st.success("High confidence product data")
        else:
            st.warning("Check product coverage before quoting")

        st.write(row["Product"])

        if row.get("Description"):
            st.caption(row["Description"])

        with st.expander("Show photo"):
            if row.get("Thumbnail"):
                st.image(row["Thumbnail"], width=160)
            else:
                st.write("No product image available.")

        c1, c2, c3 = st.columns(3)
        c1.metric("Order Qty", f"{int(row['Order Qty'])} {row['Order Unit']}")
        c2.metric("Unit Price", money(row["Unit Price"]))
        c3.metric("Subtotal", money(row["Subtotal"]))

        d1, d2 = st.columns(2)
        d1.caption(f"Coverage: {row['Coverage / Unit']}")
        d2.caption(f"Product data: {row['Product Size']}")

        if row.get("Product URL"):
            st.link_button("View Product", row["Product URL"], use_container_width=True)


st.subheader("Step 1 — Search")

query = st.text_input(
    "What are you looking for?",
    placeholder="Examples: drywall tape, HVAC foil tape, paint 18.9L, baseboard, drywall screws",
)

location = st.selectbox(
    "Search location",
    [
        "Vancouver, British Columbia, Canada",
        "Richmond, British Columbia, Canada",
        "Burnaby, British Columbia, Canada",
        "Surrey, British Columbia, Canada",
    ],
)

if not query:
    st.info("Type a product name to start.")
    st.stop()

material_type = classify_material(query)
questions = get_material_questions(material_type)

st.subheader("Step 2 — Clarify")

clarification = st.selectbox(
    questions["clarifier_label"],
    questions["options"],
)

profile = make_profile(query, clarification)
refined_query = build_refined_search_query(query, material_type, clarification)

a, b, c = st.columns(3)
a.metric("Type", material_type.replace("_", " ").title())
b.metric("Input Unit", profile["takeoff_unit"])
c.metric("Typical Coverage", f"{profile['coverage_qty']} {profile['coverage_unit']}")

with st.expander("Search details"):
    st.write("Search query:", refined_query)
    st.write("Location:", location)

st.subheader("Step 3 — Search Products")

if st.button("Search Products", use_container_width=True):
    with st.spinner("Searching products..."):
        products = search_google_shopping(refined_query, profile, location=location)
        st.session_state["products_df"] = pd.DataFrame(products)
        st.session_state["query"] = query

if "products_df" not in st.session_state:
    st.info("Click Search Products to continue.")
    st.stop()

products_df = st.session_state["products_df"]

if products_df.empty:
    st.warning("No products found. Try a more specific search.")
    st.stop()

st.subheader("Step 4 — Pick Product")

product_options = [
    f"{row['Vendor']} | {row['Product']} | {row['Displayed Price']}"
    for _, row in products_df.iterrows()
]

selected_option = st.selectbox(
    "Choose closest product match",
    product_options,
)

selected_index = product_options.index(selected_option)
selected_product = products_df.iloc[selected_index]

p1, p2, p3 = st.columns(3)
p1.metric("Product Size", selected_product["Product Size"])
p2.metric("Coverage", f"{selected_product['Coverage Qty']} {selected_product['Coverage Unit']}")
p3.metric("Order Unit", selected_product["Store Unit"])

st.subheader("Step 5 — Quantity")

required_qty = st.number_input(
    f"How much do you need? ({selected_product['Takeoff Unit']})",
    min_value=1,
    value=1,
    step=1,
)

with st.expander("Advanced options"):
    extra_percent = st.number_input(
        "Extra allowance / waste (%)",
        min_value=0,
        value=0,
        step=1,
    )

adjusted_qty = required_qty * (1 + extra_percent / 100)
coverage_qty = float(selected_product["Coverage Qty"])
order_qty = math.ceil(adjusted_qty / coverage_qty)
total_coverage = order_qty * coverage_qty

q1, q2, q3 = st.columns(3)
q1.metric("Needed", f"{round(required_qty):,} {selected_product['Takeoff Unit']}")
q2.metric("Order Qty", f"{order_qty:,} {selected_product['Store Unit']}")
q3.metric("Total Coverage", f"{round(total_coverage):,} {selected_product['Coverage Unit']}")

st.subheader("Step 6 — Vendor Options")

pricing_df = build_pricing_table(
    products_df=products_df,
    required_qty=required_qty,
    extra_percent=extra_percent,
)

if pricing_df.empty:
    st.warning("No usable prices found.")
    st.stop()

st.caption(f"Showing top {min(MAX_OPTIONS, len(pricing_df))} options. Local vendors are prioritized when detected.")

for i, (_, row) in enumerate(pricing_df.iterrows()):
    show_option_card(row, i)

best = pricing_df.sort_values("Subtotal").iloc[0]

st.subheader("Step 7 — Quote Line")

line_name = st.text_input(
    "Line item name",
    value=query.title(),
)

invoice_df = pd.DataFrame([{
    "Line Item": line_name,
    "Product": best["Product"],
    "Vendor": best["Vendor"],
    "Required Qty": int(required_qty),
    "Input Unit": selected_product["Takeoff Unit"],
    "Extra %": int(extra_percent),
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
        "Unit Price": "${:,.2f}",
        "Subtotal": "${:,.2f}",
        "GST 5%": "${:,.2f}",
        "PST 7%": "${:,.2f}",
        "Total": "${:,.2f}",
    }),
    use_container_width=True,
    hide_index=True,
)

if best.get("Product URL"):
    st.link_button("Open Quote Product", best["Product URL"], use_container_width=True)

csv = invoice_df.to_csv(index=False).encode("utf-8")

st.download_button(
    "Download CSV",
    csv,
    file_name="smart_shopper_quote_line.csv",
    mime="text/csv",
    use_container_width=True,
)