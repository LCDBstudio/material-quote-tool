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
MAX_OPTIONS = 6

st.set_page_config(
    page_title="Smart Shopper",
    layout="wide",
)

st.title("Smart Shopper")
st.caption("Search → clarify → choose product → enter quantity → compare vendors → create quote line")


# -----------------------------
# Session helpers
# -----------------------------

def init_state():
    defaults = {
        "step": 1,
        "query": "",
        "location": "Vancouver, British Columbia, Canada",
        "clarification": None,
        "profile": None,
        "refined_query": "",
        "products_df": None,
        "selected_product_index": None,
        "required_qty": 1,
        "extra_percent": 0,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def go_to_step(step):
    st.session_state["step"] = step
    st.rerun()


def back_button(target_step):
    if st.button("← Back", use_container_width=True):
        go_to_step(target_step)


def next_button(label, target_step):
    if st.button(label, use_container_width=True):
        go_to_step(target_step)


init_state()


# -----------------------------
# Utility functions
# -----------------------------

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
            "Coverage Qty": coverage_qty,
            "Coverage Unit": coverage_unit,
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


def selected_product():
    products_df = st.session_state["products_df"]
    idx = st.session_state["selected_product_index"]

    if products_df is None or idx is None:
        return None

    return products_df.iloc[idx]


def show_progress():
    labels = [
        "1 Search",
        "2 Clarify",
        "3 Results",
        "4 Quantity",
        "5 Compare",
        "6 Quote",
    ]

    current = st.session_state["step"]

    st.progress(current / 6)

    cols = st.columns(6)
    for i, col in enumerate(cols, start=1):
        label = labels[i - 1]
        if i == current:
            col.markdown(f"**{label}**")
        else:
            col.caption(label)


def product_card(row, index, selectable=True):
    with st.container(border=True):
        img_col, info_col = st.columns([1, 3])

        with img_col:
            if row.get("Thumbnail"):
                st.image(row["Thumbnail"], width=110)
            else:
                st.caption("No image")

        with info_col:
            st.markdown(f"**{row.get('Vendor', '')}**")
            st.write(row.get("Product", ""))

            price_text = row.get("Displayed Price", "")
            price = row.get("Price", None)

            if price:
                st.markdown(f"### {money(float(price))}")
            elif price_text:
                st.markdown(f"### {price_text}")

            c1, c2, c3 = st.columns(3)
            c1.caption(f"Size: {row.get('Product Size', '')}")
            c2.caption(f"Coverage: {row.get('Coverage Qty', '')} {row.get('Coverage Unit', '')}")
            c3.caption(f"Unit: {row.get('Store Unit', '')}")

            if row.get("Confidence") == "High":
                st.success("High confidence")
            else:
                st.warning("Check coverage")

            if row.get("Product URL"):
                st.link_button("View Product", row["Product URL"], use_container_width=True)

            if selectable:
                if st.button("Select this product", key=f"select_{index}", use_container_width=True):
                    st.session_state["selected_product_index"] = index
                    go_to_step(4)


def vendor_option_card(row, index, best=False):
    with st.container(border=True):
        if best:
            st.success("Best Option")

        img_col, info_col = st.columns([1, 3])

        with img_col:
            if row.get("Thumbnail"):
                with st.expander("Photo"):
                    st.image(row["Thumbnail"], width=130)
            else:
                st.caption("No image")

        with info_col:
            st.markdown(f"### {row['Vendor']}")
            st.write(row["Product"])

            c1, c2, c3 = st.columns(3)
            c1.metric("Order Qty", f"{int(row['Order Qty'])} {row['Order Unit']}")
            c2.metric("Unit Price", money(row["Unit Price"]))
            c3.metric("Subtotal", money(row["Subtotal"]))

            st.caption(f"Coverage: {row['Coverage / Unit']} | Product data: {row['Product Size']}")

            if row.get("Product URL"):
                st.link_button("View Product", row["Product URL"], use_container_width=True)


show_progress()


# -----------------------------
# Step 1: Search
# -----------------------------

if st.session_state["step"] == 1:
    st.subheader("Step 1 — Search")

    query = st.text_input(
        "What are you looking for?",
        value=st.session_state["query"],
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
        index=[
            "Vancouver, British Columbia, Canada",
            "Richmond, British Columbia, Canada",
            "Burnaby, British Columbia, Canada",
            "Surrey, British Columbia, Canada",
        ].index(st.session_state["location"]),
    )

    st.session_state["query"] = query
    st.session_state["location"] = location

    if st.button("Continue", use_container_width=True):
        if not query.strip():
            st.warning("Enter a product or material first.")
        else:
            st.session_state["products_df"] = None
            st.session_state["selected_product_index"] = None
            go_to_step(2)


# -----------------------------
# Step 2: Clarify
# -----------------------------

elif st.session_state["step"] == 2:
    st.subheader("Step 2 — Clarify")

    query = st.session_state["query"]
    material_type = classify_material(query)
    questions = get_material_questions(material_type)

    clarification = st.selectbox(
        questions["clarifier_label"],
        questions["options"],
    )

    profile = make_profile(query, clarification)
    refined_query = build_refined_search_query(query, material_type, clarification)

    st.session_state["clarification"] = clarification
    st.session_state["profile"] = profile
    st.session_state["refined_query"] = refined_query

    c1, c2, c3 = st.columns(3)
    c1.metric("Detected Type", material_type.replace("_", " ").title())
    c2.metric("Input Unit", profile["takeoff_unit"])
    c3.metric("Typical Coverage", f"{profile['coverage_qty']} {profile['coverage_unit']}")

    with st.expander("Search query"):
        st.write(refined_query)
        st.write(st.session_state["location"])

    col1, col2 = st.columns(2)
    with col1:
        back_button(1)

    with col2:
        if st.button("Search Products", use_container_width=True):
            with st.spinner("Searching products..."):
                products = search_google_shopping(
                    refined_query,
                    profile,
                    location=st.session_state["location"],
                )
                st.session_state["products_df"] = pd.DataFrame(products)
                st.session_state["selected_product_index"] = None
                go_to_step(3)


# -----------------------------
# Step 3: Product selection
# -----------------------------

elif st.session_state["step"] == 3:
    st.subheader("Step 3 — Choose Product")

    products_df = st.session_state["products_df"]

    if products_df is None or products_df.empty:
        st.warning("No products found. Go back and try a more specific search.")
        back_button(2)
        st.stop()

    st.caption("Choose the closest product by photo, vendor, price, and product data.")

    view_count = st.slider(
        "Number of products to show",
        min_value=3,
        max_value=min(12, len(products_df)),
        value=min(6, len(products_df)),
    )

    for i, (_, row) in enumerate(products_df.head(view_count).iterrows()):
        product_card(row, i, selectable=True)

    col1, col2 = st.columns(2)
    with col1:
        back_button(2)

    with col2:
        if st.session_state["selected_product_index"] is not None:
            next_button("Continue", 4)


# -----------------------------
# Step 4: Quantity
# -----------------------------

elif st.session_state["step"] == 4:
    st.subheader("Step 4 — Quantity")

    product = selected_product()

    if product is None:
        st.warning("Select a product first.")
        back_button(3)
        st.stop()

    product_card(product, st.session_state["selected_product_index"], selectable=False)

    st.markdown("### How much do you need?")

    required_qty = st.number_input(
        f"Required quantity ({product['Takeoff Unit']})",
        min_value=1,
        value=int(st.session_state["required_qty"]),
        step=1,
    )

    with st.expander("Advanced options"):
        extra_percent = st.number_input(
            "Extra allowance / waste (%)",
            min_value=0,
            value=int(st.session_state["extra_percent"]),
            step=1,
        )

    st.session_state["required_qty"] = required_qty
    st.session_state["extra_percent"] = extra_percent

    adjusted_qty = required_qty * (1 + extra_percent / 100)
    coverage_qty = float(product["Coverage Qty"])
    order_qty = math.ceil(adjusted_qty / coverage_qty)
    total_coverage = order_qty * coverage_qty

    q1, q2, q3 = st.columns(3)
    q1.metric("Needed", f"{required_qty:,} {product['Takeoff Unit']}")
    q2.metric("Order Qty", f"{order_qty:,} {product['Store Unit']}")
    q3.metric("Total Coverage", f"{round(total_coverage):,} {product['Coverage Unit']}")

    col1, col2 = st.columns(2)
    with col1:
        back_button(3)

    with col2:
        next_button("Compare Vendors", 5)


# -----------------------------
# Step 5: Vendor comparison
# -----------------------------

elif st.session_state["step"] == 5:
    st.subheader("Step 5 — Vendor Options")

    products_df = st.session_state["products_df"]

    pricing_df = build_pricing_table(
        products_df=products_df,
        required_qty=st.session_state["required_qty"],
        extra_percent=st.session_state["extra_percent"],
    )

    if pricing_df.empty:
        st.warning("No usable prices found.")
        back_button(4)
        st.stop()

    best = pricing_df.sort_values("Subtotal").iloc[0]

    st.success(
        f"Best Option: {best['Vendor']} — order {int(best['Order Qty'])} {best['Order Unit']} — subtotal {money(best['Subtotal'])}"
    )

    for i, (_, row) in enumerate(pricing_df.iterrows()):
        is_best = row["Vendor"] == best["Vendor"] and row["Product"] == best["Product"]
        vendor_option_card(row, i, best=is_best)

    col1, col2 = st.columns(2)
    with col1:
        back_button(4)

    with col2:
        next_button("Create Quote Line", 6)


# -----------------------------
# Step 6: Quote line
# -----------------------------

elif st.session_state["step"] == 6:
    st.subheader("Step 6 — Quote Line")

    pricing_df = build_pricing_table(
        products_df=st.session_state["products_df"],
        required_qty=st.session_state["required_qty"],
        extra_percent=st.session_state["extra_percent"],
    )

    best = pricing_df.sort_values("Subtotal").iloc[0]

    line_name = st.text_input(
        "Line item name",
        value=st.session_state["query"].title(),
    )

    invoice_df = pd.DataFrame([{
        "Line Item": line_name,
        "Product": best["Product"],
        "Vendor": best["Vendor"],
        "Required Qty": int(st.session_state["required_qty"]),
        "Input Unit": best["Takeoff Unit"],
        "Extra %": int(st.session_state["extra_percent"]),
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

    st.success(
        f"Quote total with tax: {money(best['Total'])}"
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

    col1, col2 = st.columns(2)
    with col1:
        back_button(5)

    with col2:
        if st.button("Start New Search", use_container_width=True):
            st.session_state.clear()
            st.rerun()