import math
import pandas as pd
import streamlit as st

from ai_material_assistant import (
    classify_material,
    get_material_questions,
    make_profile,
    build_refined_search_query,
    make_sheet_profile,
    build_sheet_search_query,
)
from live_search import search_google_shopping
from product_parser import parse_product_specs

GST_RATE = 0.05
PST_RATE = 0.07
MAX_OPTIONS = 6

st.set_page_config(
    page_title="Smart Shopper",
    layout="wide",
)

st.title("Smart Shopper")
st.caption("Search → clarify → choose product → enter quantity → compare vendors → select quote product → create quote line")


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
        "selected_quote_index": None,
        "required_qty": 1,
        "extra_percent": 0,
        "sheet_material": "Drywall",
        "sheet_thickness": "1/2 in",
        "sheet_size": "4 ft x 8 ft",
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
        if i == current:
            col.markdown(f"**{labels[i - 1]}**")
        else:
            col.caption(labels[i - 1])


def selected_product():
    products_df = st.session_state["products_df"]
    idx = st.session_state["selected_product_index"]

    if products_df is None or idx is None:
        return None

    return products_df.iloc[idx]


def build_pricing_table(products_df, required_qty, extra_percent):
    adjusted_qty = required_qty * (1 + extra_percent / 100)
    rows = []

    for source_index, row in products_df.iterrows():
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
            "Source Index": source_index,
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

    return df.reset_index(drop=True)


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

            price = row.get("Price", None)
            display_price = row.get("Displayed Price", "")

            if price:
                st.markdown(f"### {money(float(price))}")
            elif display_price:
                st.markdown(f"### {display_price}")

            c1, c2, c3 = st.columns(3)
            c1.caption(f"Size: {row.get('Product Size', '')}")
            c2.caption(f"Coverage: {row.get('Coverage Qty', '')} {row.get('Coverage Unit', '')}")
            c3.caption(f"Unit: {row.get('Store Unit', '')}")

            if row.get("Confidence") == "High":
                st.success("High confidence")
            else:
                st.warning("Check comparability")

            if row.get("Product URL"):
                st.link_button("View Product", row["Product URL"], use_container_width=True)

            if selectable:
                if st.button("Select this product", key=f"select_product_{index}", use_container_width=True):
                    st.session_state["selected_product_index"] = index
                    st.session_state["selected_quote_index"] = None
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

            st.caption(f"Coverage: {row['Coverage / Unit']} | Product data: {row['Product Size']} | Confidence: {row['Confidence']}")

            if row.get("Product URL"):
                st.link_button("View Product", row["Product URL"], use_container_width=True)

            if st.button("Use this for quote", key=f"use_quote_{index}", use_container_width=True):
                st.session_state["selected_quote_index"] = index
                go_to_step(6)


def improve_product_specs(products_df, selected_index):
    row = products_df.iloc[selected_index]

    parsed = parse_product_specs(
        title=row.get("Product", ""),
        description=row.get("Description", ""),
        url=row.get("Product URL", ""),
    )

    if parsed["coverage_qty"] is not None:
        products_df.at[selected_index, "Coverage Qty"] = parsed["coverage_qty"]
        products_df.at[selected_index, "Coverage Unit"] = parsed["coverage_unit"]
        products_df.at[selected_index, "Store Unit"] = parsed["store_unit"]
        products_df.at[selected_index, "Product Size"] = parsed["product_size"]
        products_df.at[selected_index, "Takeoff Unit"] = parsed["takeoff_unit"]
        products_df.at[selected_index, "Confidence"] = parsed["confidence"]

    return products_df, parsed


init_state()
show_progress()


if st.session_state["step"] == 1:
    st.subheader("Step 1 — Search")

    st.session_state["query"] = st.text_input(
        "What are you looking for?",
        value=st.session_state["query"],
        placeholder="Examples: 1/2 drywall, 3/4 plywood, HVAC foil tape, paint 18.9L",
    )

    locations = [
        "Vancouver, British Columbia, Canada",
        "Richmond, British Columbia, Canada",
        "Burnaby, British Columbia, Canada",
        "Surrey, British Columbia, Canada",
    ]

    st.session_state["location"] = st.selectbox(
        "Search location",
        locations,
        index=locations.index(st.session_state["location"]),
    )

    if st.button("Continue", use_container_width=True):
        if not st.session_state["query"].strip():
            st.warning("Enter a product or material first.")
        else:
            st.session_state["products_df"] = None
            st.session_state["selected_product_index"] = None
            st.session_state["selected_quote_index"] = None
            go_to_step(2)


elif st.session_state["step"] == 2:
    st.subheader("Step 2 — Clarify")

    query = st.session_state["query"]
    material_type = classify_material(query)

    if material_type == "sheet_goods":
        st.markdown("### Sheet material filters")

        sheet_material = st.selectbox(
            "Sheet material",
            ["Drywall", "Plywood", "OSB", "Cement Board", "MDF Panel"],
            index=["Drywall", "Plywood", "OSB", "Cement Board", "MDF Panel"].index(st.session_state["sheet_material"])
            if st.session_state["sheet_material"] in ["Drywall", "Plywood", "OSB", "Cement Board", "MDF Panel"] else 0,
        )

        thickness_options = {
            "Drywall": ["1/4 in", "3/8 in", "1/2 in", "5/8 in"],
            "Plywood": ["1/4 in", "3/8 in", "1/2 in", "5/8 in", "3/4 in"],
            "OSB": ["7/16 in", "1/2 in", "5/8 in", "3/4 in"],
            "Cement Board": ["1/4 in", "1/2 in", "5/8 in"],
            "MDF Panel": ["1/4 in", "1/2 in", "5/8 in", "3/4 in"],
        }

        thickness = st.selectbox(
            "Thickness",
            thickness_options[sheet_material],
        )

        sheet_size = st.selectbox(
            "Sheet size",
            ["4 ft x 8 ft", "4 ft x 10 ft", "4 ft x 12 ft", "2 ft x 4 ft"],
            index=["4 ft x 8 ft", "4 ft x 10 ft", "4 ft x 12 ft", "2 ft x 4 ft"].index(st.session_state["sheet_size"])
            if st.session_state["sheet_size"] in ["4 ft x 8 ft", "4 ft x 10 ft", "4 ft x 12 ft", "2 ft x 4 ft"] else 0,
        )

        st.session_state["sheet_material"] = sheet_material
        st.session_state["sheet_thickness"] = thickness
        st.session_state["sheet_size"] = sheet_size

        profile = make_sheet_profile(sheet_material, thickness, sheet_size)
        refined_query = build_sheet_search_query(sheet_material, thickness, sheet_size)

        st.session_state["clarification"] = f"{thickness} {sheet_material} {sheet_size}"
        st.session_state["profile"] = profile
        st.session_state["refined_query"] = refined_query

        c1, c2, c3 = st.columns(3)
        c1.metric("Material", sheet_material)
        c2.metric("Thickness", thickness)
        c3.metric("Coverage", f"{profile['coverage_qty']} sf / sheet")

    else:
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
        st.write(st.session_state["refined_query"])
        st.write(st.session_state["location"])

    col1, col2 = st.columns(2)
    with col1:
        back_button(1)

    with col2:
        if st.button("Search Products", use_container_width=True):
            with st.spinner("Searching comparable products..."):
                products = search_google_shopping(
                    st.session_state["refined_query"],
                    st.session_state["profile"],
                    location=st.session_state["location"],
                )
                st.session_state["products_df"] = pd.DataFrame(products)
                st.session_state["selected_product_index"] = None
                st.session_state["selected_quote_index"] = None
                go_to_step(3)


elif st.session_state["step"] == 3:
    st.subheader("Step 3 — Choose Product")

    products_df = st.session_state["products_df"]

    if products_df is None or products_df.empty:
        st.warning("No products found. Go back and try a more specific search.")
        back_button(2)
        st.stop()

    st.caption("Choose the closest comparable product by photo, vendor, price, thickness, and sheet size.")

    view_count = st.slider(
        "Number of products to show",
        min_value=3,
        max_value=min(12, len(products_df)),
        value=min(6, len(products_df)),
    )

    for i, (_, row) in enumerate(products_df.head(view_count).iterrows()):
        product_card(row, i, selectable=True)

    back_button(2)


elif st.session_state["step"] == 4:
    st.subheader("Step 4 — Quantity")

    product = selected_product()

    if product is None:
        st.warning("Select a product first.")
        back_button(3)
        st.stop()

    st.markdown("### Selected product")
    product_card(product, st.session_state["selected_product_index"], selectable=False)

    with st.spinner("Checking product page for better specs..."):
        updated_df, parsed = improve_product_specs(
            st.session_state["products_df"],
            st.session_state["selected_product_index"],
        )
        st.session_state["products_df"] = updated_df
        product = selected_product()

    if parsed["confidence"] == "High":
        st.success(f"Product data improved: {parsed['reason']}")
    else:
        st.warning(parsed["reason"])

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


elif st.session_state["step"] == 5:
    st.subheader("Step 5 — Vendor Options")

    pricing_df = build_pricing_table(
        products_df=st.session_state["products_df"],
        required_qty=st.session_state["required_qty"],
        extra_percent=st.session_state["extra_percent"],
    )

    if pricing_df.empty:
        st.warning("No usable prices found.")
        back_button(4)
        st.stop()

    st.session_state["pricing_df"] = pricing_df

    best = pricing_df.sort_values("Subtotal").iloc[0]

    st.success(
        f"Best Option: {best['Vendor']} — order {int(best['Order Qty'])} {best['Order Unit']} — subtotal {money(best['Subtotal'])}"
    )

    st.caption("Select the exact option you want to use for the quote line.")

    for i, (_, row) in enumerate(pricing_df.iterrows()):
        is_best = row["Vendor"] == best["Vendor"] and row["Product"] == best["Product"]
        vendor_option_card(row, i, best=is_best)

    back_button(4)


elif st.session_state["step"] == 6:
    st.subheader("Step 6 — Quote Line")

    pricing_df = st.session_state.get("pricing_df")

    if pricing_df is None or pricing_df.empty:
        pricing_df = build_pricing_table(
            products_df=st.session_state["products_df"],
            required_qty=st.session_state["required_qty"],
            extra_percent=st.session_state["extra_percent"],
        )

    selected_quote_index = st.session_state.get("selected_quote_index")

    if selected_quote_index is None:
        st.warning("No quote option selected. Go back and choose a vendor option.")
        back_button(5)
        st.stop()

    selected = pricing_df.iloc[selected_quote_index]

    line_name = st.text_input(
        "Line item name",
        value=st.session_state["query"].title(),
    )

    invoice_df = pd.DataFrame([{
        "Line Item": line_name,
        "Product": selected["Product"],
        "Vendor": selected["Vendor"],
        "Required Qty": int(st.session_state["required_qty"]),
        "Input Unit": selected["Takeoff Unit"],
        "Extra %": int(st.session_state["extra_percent"]),
        "Order Qty": int(selected["Order Qty"]),
        "Order Unit": selected["Order Unit"],
        "Unit Price": selected["Unit Price"],
        "Subtotal": selected["Subtotal"],
        "GST 5%": selected["GST 5%"],
        "PST 7%": selected["PST 7%"],
        "Total": selected["Total"],
        "Product URL": selected["Product URL"],
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

    st.success(f"Quote total with tax: {money(selected['Total'])}")

    if selected.get("Product URL"):
        st.link_button("Open Quote Product", selected["Product URL"], use_container_width=True)

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