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
MAX_OPTIONS = 8

st.set_page_config(
    page_title="Smart Material Quote Tool",
    layout="wide",
)

st.title("Smart Material Quote Tool")
st.caption("Search material → answer quick questions → compare vendor options → create quote line.")


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

        order_qty = math.ceil(adjusted_qty / coverage_qty)
        total_coverage = order_qty * coverage_qty
        extra_allowance = total_coverage - required_qty

        subtotal = order_qty * float(price)
        gst = subtotal * GST_RATE
        pst = subtotal * PST_RATE
        total = subtotal + gst + pst

        rows.append({
            "Vendor": row.get("Vendor", ""),
            "Product": row.get("Product", ""),
            "Product Size": row.get("Product Size", ""),
            "Takeoff Unit": takeoff_unit,
            "Coverage / Unit": f"{coverage_qty:g} {coverage_unit}",
            "Order Qty": int(order_qty),
            "Order Unit": store_unit,
            "Total Coverage": round(total_coverage),
            "Extra Allowance": round(extra_allowance),
            "Unit Price": float(price),
            "Subtotal": subtotal,
            "GST 5%": gst,
            "PST 7%": pst,
            "Total": total,
            "Product URL": row.get("Product URL", ""),
        })

    df = pd.DataFrame(rows)

    if not df.empty:
        df = df.sort_values("Subtotal", ascending=True).head(MAX_OPTIONS)

    return df


def show_product_card(row, index):
    with st.container(border=True):
        st.markdown(f"### Option {index + 1}: {row['Vendor']}")
        st.write(row["Product"])

        c1, c2, c3, c4 = st.columns(4)

        c1.metric("Order Qty", f"{int(row['Order Qty'])} {row['Order Unit']}")
        c2.metric("Unit Price", money(row["Unit Price"]))
        c3.metric("Subtotal", money(row["Subtotal"]))
        c4.metric("Coverage", row["Coverage / Unit"])

        st.caption(f"Product size: {row['Product Size']}")

        if row.get("Product URL"):
            st.markdown(f"[Open product link]({row['Product URL']})")


def show_invoice_table(invoice_df):
    st.dataframe(
        invoice_df.style.format({
            "Takeoff Qty": "{:,.0f}",
            "Contingency %": "{:,.0f}",
            "Unit Price": "${:,.2f}",
            "Subtotal": "${:,.2f}",
            "GST 5%": "${:,.2f}",
            "PST 7%": "${:,.2f}",
            "Total": "${:,.2f}",
        }),
        use_container_width=True,
        hide_index=True,
    )


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

c1, c2, c3 = st.columns(3)
c1.metric("Detected Type", material_type.replace("_", " ").title())
c2.metric("Input Unit", profile["takeoff_unit"])
c3.metric("Typical Coverage", f"{profile['coverage_qty']} {profile['coverage_unit']}")

with st.expander("Search query used"):
    st.write(refined_query)

st.subheader("3. Search live products")

if st.button("Search Live Products", use_container_width=True):
    with st.spinner("Searching vendor products..."):
        products = search_google_shopping(refined_query, profile)
        st.session_state["products_df"] = pd.DataFrame(products)
        st.session_state["query"] = query
        st.session_state["profile"] = profile

if "products_df" not in st.session_state:
    st.info("Click Search Live Products to continue.")
    st.stop()

products_df = st.session_state["products_df"]

if products_df.empty:
    st.warning("No products found. Try a more specific search.")
    st.stop()

st.subheader("4. Choose product")

product_options = [
    f"{row['Vendor']} | {row['Product']} | {row['Displayed Price']}"
    for _, row in products_df.iterrows()
]

selected_option = st.selectbox(
    "Select the closest product match",
    product_options,
)

selected_index = product_options.index(selected_option)
selected_product = products_df.iloc[selected_index]

p1, p2, p3, p4 = st.columns(4)

p1.metric("Product Size", selected_product["Product Size"])
p2.metric("Input Unit", selected_product["Takeoff Unit"])
p3.metric("Coverage", f"{selected_product['Coverage Qty']} {selected_product['Coverage Unit']}")
p4.metric("Order Unit", selected_product["Store Unit"])

if selected_product.get("Product URL"):
    st.markdown(f"[Open selected product]({selected_product['Product URL']})")

st.subheader("5. Enter quantity")

q_col1, q_col2 = st.columns(2)

with q_col1:
    required_qty = st.number_input(
        f"Required quantity ({selected_product['Takeoff Unit']})",
        min_value=0,
        value=100,
        step=1,
    )

with q_col2:
    contingency_percent = st.number_input(
        "Contingency / waste allowance (%)",
        min_value=0,
        value=10,
        step=1,
    )

adjusted_qty = required_qty * (1 + contingency_percent / 100)
coverage_qty = float(selected_product["Coverage Qty"])
order_qty = math.ceil(adjusted_qty / coverage_qty)
total_coverage = order_qty * coverage_qty

m1, m2, m3 = st.columns(3)
m1.metric("With Contingency", f"{round(adjusted_qty):,} {selected_product['Takeoff Unit']}")
m2.metric("Order Qty", f"{order_qty:,} {selected_product['Store Unit']}")
m3.metric("Total Coverage", f"{round(total_coverage):,} {selected_product['Coverage Unit']}")

st.subheader("6. Vendor pricing options")

pricing_df = build_pricing_table(
    products_df=products_df,
    required_qty=required_qty,
    contingency_percent=contingency_percent,
)

if pricing_df.empty:
    st.warning("No usable prices found.")
    st.stop()

st.caption(f"Showing lowest {min(MAX_OPTIONS, len(pricing_df))} options by material subtotal. Taxes are shown only in the invoice section.")

for i, (_, row) in enumerate(pricing_df.iterrows()):
    show_product_card(row, i)

best = pricing_df.sort_values("Subtotal").iloc[0]

st.success(
    f"Best material subtotal: {best['Vendor']} — order {int(best['Order Qty'])} {best['Order Unit']} — subtotal {money(best['Subtotal'])}"
)

st.subheader("7. Invoice / quote line")

scope_name = st.text_input(
    "Scope name",
    value=query.title(),
)

invoice_df = pd.DataFrame([{
    "Scope": scope_name,
    "Material": best["Product"],
    "Vendor": best["Vendor"],
    "Takeoff Qty": int(required_qty),
    "Takeoff Unit": selected_product["Takeoff Unit"],
    "Contingency %": int(contingency_percent),
    "Order Qty": int(best["Order Qty"]),
    "Order Unit": best["Order Unit"],
    "Unit Price": best["Unit Price"],
    "Subtotal": best["Subtotal"],
    "GST 5%": best["GST 5%"],
    "PST 7%": best["PST 7%"],
    "Total": best["Total"],
    "Product URL": best["Product URL"],
}])

show_invoice_table(invoice_df)

if best.get("Product URL"):
    st.markdown(f"[Open quoted product]({best['Product URL']})")

csv = invoice_df.to_csv(index=False).encode("utf-8")

st.download_button(
    "Download quote line CSV",
    csv,
    file_name="material_quote_line.csv",
    mime="text/csv",
    use_container_width=True,
)