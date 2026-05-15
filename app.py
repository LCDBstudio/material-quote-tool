import math
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

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

st.set_page_config(page_title="Smart Shopper", layout="wide")

st.markdown("""
<style>
.stButton > button[kind="primary"] {
    background-color: #1f77ff !important;
    color: white !important;
    border: 1px solid #1f77ff !important;
    font-weight: 700 !important;
}

@media (max-width: 768px) {
    h1 {
        font-size: 2.4rem !important;
        line-height: 1.1 !important;
    }

    .block-container {
        padding-top: 2rem !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }

    .mobile-cart-box {
        position: sticky;
        top: 0;
        z-index: 999;
        background: #0e1117;
        padding: 10px 0;
        border-bottom: 1px solid #333;
    }
}
</style>
""", unsafe_allow_html=True)

st.title("Smart Shopper")
st.caption("Search → clarify → choose product → quantity → compare vendors → build full quote cart")


def init_state():
    defaults = {
        "step": 1,
        "query": "",
        "location": "Vancouver, British Columbia, Canada",
        "clarification": None,
        "profile": None,
        "refined_query": "",
        "products_df": None,
        "pricing_df": None,
        "selected_product_index": None,
        "required_qty": 1,
        "extra_percent": 0,
        "quote_items": [],
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_app():
    st.session_state.clear()
    st.rerun()


def go_to_step(step):
    st.session_state["step"] = step
    st.rerun()


def back_button(target_step, key):
    if st.button("← Back", key=key, use_container_width=True):
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
    current = st.session_state["step"]
    step_names = {
        1: "Search",
        2: "Clarify",
        3: "Results",
        4: "Quantity",
        5: "Compare",
        6: "Quote Cart",
    }

    st.progress(current / 6)
    st.markdown(f"**Step {current} of 6 — {step_names[current]}**")


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
            "Required Qty": int(required_qty),
            "Extra %": int(extra_percent),
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
            ascending=[False, True],
        ).head(MAX_OPTIONS)

    return df.reset_index(drop=True)


def add_quote_item(row):
    item = {
        "Line Item": st.session_state["query"].title(),
        "Product": row["Product"],
        "Vendor": row["Vendor"],
        "Required Qty": int(row["Required Qty"]),
        "Input Unit": row["Takeoff Unit"],
        "Extra %": int(row["Extra %"]),
        "Order Qty": int(row["Order Qty"]),
        "Order Unit": row["Order Unit"],
        "Unit Price": row["Unit Price"],
        "Subtotal": row["Subtotal"],
        "GST 5%": row["GST 5%"],
        "PST 7%": row["PST 7%"],
        "Total": row["Total"],
        "Product URL": row["Product URL"],
    }

    st.session_state["quote_items"].append(item)


def duplicate_quote_item(index):
    item_copy = st.session_state["quote_items"][index].copy()
    st.session_state["quote_items"].append(item_copy)
    st.rerun()


def delete_quote_item(index):
    st.session_state["quote_items"].pop(index)
    st.rerun()


def quote_totals():
    items = st.session_state["quote_items"]
    subtotal = sum(item["Subtotal"] for item in items)
    gst = sum(item["GST 5%"] for item in items)
    pst = sum(item["PST 7%"] for item in items)
    total = sum(item["Total"] for item in items)
    return subtotal, gst, pst, total


def show_top_cart_button():
    items = st.session_state.get("quote_items", [])

    if not items:
        return

    subtotal, gst, pst, total = quote_totals()

    st.markdown('<div class="mobile-cart-box">', unsafe_allow_html=True)

    if st.button(
        f"View Quote Cart — {len(items)} item(s) — {money(total)}",
        key=f"top_cart_button_step_{st.session_state['step']}",
        type="primary",
        use_container_width=True,
    ):
        go_to_step(6)

    st.markdown("</div>", unsafe_allow_html=True)


def show_persistent_quote_sidebar():
    with st.sidebar:
        st.markdown("## Quote Cart")

        items = st.session_state.get("quote_items", [])

        if not items:
            st.info("No items yet.")
            return

        subtotal, gst, pst, total = quote_totals()

        st.metric("Items", len(items))
        st.metric("Subtotal", money(subtotal))
        st.metric("Tax", money(gst + pst))
        st.metric("Total", money(total))

        st.divider()

        for i, item in enumerate(items):
            with st.container(border=True):
                st.markdown(f"**{i + 1}. {item['Line Item']}**")
                st.caption(item["Vendor"])
                st.caption(item["Product"][:90])
                st.write(f"Qty: {item['Order Qty']} {item['Order Unit']}")
                st.write(f"Total: {money(item['Total'])}")

                c1, c2 = st.columns(2)

                with c1:
                    if st.button("Duplicate", key=f"duplicate_quote_item_{i}", use_container_width=True):
                        duplicate_quote_item(i)

                with c2:
                    if st.button("Delete", key=f"delete_quote_item_{i}", use_container_width=True):
                        delete_quote_item(i)

        st.divider()

        if st.button("View Full Quote", key="sidebar_view_full_quote", type="primary", use_container_width=True):
            go_to_step(6)

        if st.button("Clear Quote Cart / Reset App", key="sidebar_clear_quote_cart", use_container_width=True):
            reset_app()


def show_quote_banner():
    items = st.session_state["quote_items"]

    st.divider()
    st.markdown("### Quote Cart")

    if not items:
        st.info("No quote lines added yet.")
        return

    subtotal, gst, pst, total = quote_totals()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Items", len(items))
    c2.metric("Subtotal", money(subtotal))
    c3.metric("Tax", money(gst + pst))
    c4.metric("Total", money(total))

    with st.expander("View quote cart"):
        quote_df = pd.DataFrame(items)

        st.dataframe(
            quote_df.style.format({
                "Unit Price": "${:,.2f}",
                "Subtotal": "${:,.2f}",
                "GST 5%": "${:,.2f}",
                "PST 7%": "${:,.2f}",
                "Total": "${:,.2f}",
            }),
            use_container_width=True,
            hide_index=True,
        )

        if st.button("Go to Quote Cart", key="quote_banner_go_to_cart", type="primary", use_container_width=True):
            go_to_step(6)


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
                if st.button(
                    "Select this product",
                    key=f"select_product_{index}",
                    type="primary",
                    use_container_width=True,
                ):
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

            st.caption(
                f"Coverage: {row['Coverage / Unit']} | "
                f"Product data: {row['Product Size']} | "
                f"Confidence: {row['Confidence']}"
            )

            if row.get("Product URL"):
                st.link_button("View Product", row["Product URL"], use_container_width=True)

            if st.button(
                "Add this item to quote",
                key=f"add_quote_{index}",
                type="primary",
                use_container_width=True,
            ):
                add_quote_item(row)
                st.success("Added to quote cart.")


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


def print_button():
    components.html(
        """
        <button onclick="window.parent.print()"
            style="
                width:100%;
                padding:8px 10px;
                background:transparent;
                color:inherit;
                border:1px solid #444;
                border-radius:6px;
                font-weight:600;
                cursor:pointer;
                font-size:14px;">
            Print / Save PDF
        </button>
        """,
        height=42,
    )


init_state()
show_persistent_quote_sidebar()
show_progress()
show_top_cart_button()


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

    if st.button("Continue", key="step1_continue", type="primary", use_container_width=True):
        if not st.session_state["query"].strip():
            st.warning("Enter a product or material first.")
        else:
            st.session_state["products_df"] = None
            st.session_state["selected_product_index"] = None
            go_to_step(2)

    show_quote_banner()


elif st.session_state["step"] == 2:
    st.subheader("Step 2 — Clarify")

    query = st.session_state["query"]
    material_type = classify_material(query)

    if material_type == "sheet_goods":
        st.markdown("### Sheet material filters")

        sheet_material = st.selectbox(
            "Sheet material",
            ["Drywall", "Plywood", "OSB", "Cement Board", "MDF Panel"],
            key="sheet_material_select",
        )

        thickness_options = {
            "Drywall": ["1/4 in", "3/8 in", "1/2 in", "5/8 in"],
            "Plywood": ["1/4 in", "3/8 in", "1/2 in", "5/8 in", "3/4 in"],
            "OSB": ["7/16 in", "1/2 in", "5/8 in", "3/4 in"],
            "Cement Board": ["1/4 in", "1/2 in", "5/8 in"],
            "MDF Panel": ["1/4 in", "1/2 in", "5/8 in", "3/4 in"],
        }

        thickness = st.selectbox("Thickness", thickness_options[sheet_material], key="sheet_thickness_select")

        sheet_size = st.selectbox(
            "Sheet size",
            ["4 ft x 8 ft", "4 ft x 10 ft", "4 ft x 12 ft", "2 ft x 4 ft"],
            key="sheet_size_select",
        )

        profile = make_sheet_profile(sheet_material, thickness, sheet_size)
        refined_query = build_sheet_search_query(sheet_material, thickness, sheet_size)

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
            key="general_clarification",
        )

        profile = make_profile(query, clarification)
        refined_query = build_refined_search_query(query, material_type, clarification)

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
        back_button(1, "step2_back")

    with col2:
        if st.button("Search Products", key="step2_search_products", type="primary", use_container_width=True):
            with st.spinner("Searching comparable products..."):
                products = search_google_shopping(
                    st.session_state["refined_query"],
                    st.session_state["profile"],
                    location=st.session_state["location"],
                )
                st.session_state["products_df"] = pd.DataFrame(products)
                st.session_state["selected_product_index"] = None
                go_to_step(3)

    show_quote_banner()


elif st.session_state["step"] == 3:
    st.subheader("Step 3 — Refine & Choose Product")

    products_df = st.session_state["products_df"]

    if products_df is None or products_df.empty:
        st.warning("No products found. Try refining your search.")
        back_button(2, "step3_back_no_products")
        st.stop()

    st.markdown("### Refine search")

    refine_query = st.text_input(
        "Search again if results are not close enough",
        value=st.session_state["refined_query"],
        placeholder="Example: 1/2 inch drywall 4x8, drywall paper tape 500 ft, KILZ primer 3.78L",
        key="step3_refine_query",
    )

    col_a, col_b = st.columns(2)

    with col_a:
        if st.button("Search Again", key="step3_search_again", type="primary", use_container_width=True):
            with st.spinner("Searching refined products..."):
                products = search_google_shopping(
                    refine_query,
                    st.session_state["profile"],
                    location=st.session_state["location"],
                )
                st.session_state["refined_query"] = refine_query
                st.session_state["products_df"] = pd.DataFrame(products)
                st.session_state["selected_product_index"] = None
                st.rerun()

    with col_b:
        back_button(2, "step3_back_to_filters")

    with st.expander("Search tips"):
        st.write("Use specific terms like:")
        st.write("- thickness: 1/2 in, 5/8 in, 3/4 in")
        st.write("- size: 4x8, 4x10, 4x12")
        st.write("- type: Type X drywall, pressure treated plywood, paper drywall tape")
        st.write("- package: 500 pack, 250 ft roll, 18.9L pail")

    st.markdown("### Product results")

    view_count = st.slider(
        "Number of products to show",
        min_value=3,
        max_value=min(12, len(products_df)),
        value=min(6, len(products_df)),
        key="step3_view_count",
    )

    for i, (_, row) in enumerate(products_df.head(view_count).iterrows()):
        product_card(row, i, selectable=True)

    show_quote_banner()


elif st.session_state["step"] == 4:
    st.subheader("Step 4 — Verify Quantity")

    product = selected_product()

    if product is None:
        st.warning("Select a product first.")
        back_button(3, "step4_back_no_product")
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
        st.success(f"{parsed['reason']} Source: {parsed.get('source', 'Product text')}")
    elif parsed["confidence"] == "Medium":
        st.warning(f"{parsed['reason']} You can edit the coverage below.")
    else:
        st.error(f"{parsed['reason']} You must verify coverage manually.")

    st.markdown("### Confirm product coverage")

    c1, c2, c3 = st.columns(3)

    with c1:
        coverage_qty = st.number_input(
            "Coverage per product unit",
            min_value=0.01,
            value=float(product["Coverage Qty"]),
            step=1.0,
            key="step4_coverage_qty",
        )

    with c2:
        coverage_unit = st.selectbox(
            "Coverage unit",
            ["sf", "ln ft", "qty"],
            index=["sf", "ln ft", "qty"].index(product["Coverage Unit"])
            if product["Coverage Unit"] in ["sf", "ln ft", "qty"] else 0,
            key="step4_coverage_unit",
        )

    with c3:
        store_unit = st.text_input(
            "Order unit",
            value=str(product["Store Unit"]),
            key="step4_store_unit",
        )

    st.session_state["products_df"].at[
        st.session_state["selected_product_index"], "Coverage Qty"
    ] = coverage_qty

    st.session_state["products_df"].at[
        st.session_state["selected_product_index"], "Coverage Unit"
    ] = coverage_unit

    st.session_state["products_df"].at[
        st.session_state["selected_product_index"], "Store Unit"
    ] = store_unit

    st.session_state["products_df"].at[
        st.session_state["selected_product_index"], "Product Size"
    ] = f"{coverage_qty:g} {coverage_unit} / {store_unit}"

    product = selected_product()

    st.markdown("### How much do you need?")

    required_qty = st.number_input(
        f"Required quantity ({product['Takeoff Unit']})",
        min_value=1,
        value=int(st.session_state["required_qty"]),
        step=1,
        key="step4_required_qty",
    )

    with st.expander("Advanced options"):
        extra_percent = st.number_input(
            "Extra allowance / waste (%)",
            min_value=0,
            value=int(st.session_state["extra_percent"]),
            step=1,
            key="step4_extra_percent",
        )

        if product["Takeoff Unit"] == "sf":
            coats = st.number_input(
                "Number of coats / layers",
                min_value=1,
                value=1,
                step=1,
                key="step4_coats",
            )
        else:
            coats = 1

    st.session_state["required_qty"] = required_qty
    st.session_state["extra_percent"] = extra_percent

    adjusted_qty = required_qty * coats * (1 + extra_percent / 100)
    coverage_qty = float(product["Coverage Qty"])
    order_qty = math.ceil(adjusted_qty / coverage_qty)
    total_coverage = order_qty * coverage_qty

    q1, q2, q3 = st.columns(3)
    q1.metric("Needed", f"{round(adjusted_qty):,} {product['Takeoff Unit']}")
    q2.metric("Order Qty", f"{order_qty:,} {product['Store Unit']}")
    q3.metric("Total Coverage", f"{round(total_coverage):,} {product['Coverage Unit']}")

    if parsed["confidence"] != "High":
        st.info("This item uses estimated coverage. Confirm the product page before ordering.")

    col1, col2 = st.columns(2)

    with col1:
        back_button(3, "step4_back")

    with col2:
        if st.button("Compare Vendors", key="step4_compare_vendors", type="primary", use_container_width=True):
            go_to_step(5)

    show_quote_banner()


elif st.session_state["step"] == 5:
    st.subheader("Step 5 — Vendor Options")

    pricing_df = build_pricing_table(
        products_df=st.session_state["products_df"],
        required_qty=st.session_state["required_qty"],
        extra_percent=st.session_state["extra_percent"],
    )

    if pricing_df.empty:
        st.warning("No usable prices found.")
        back_button(4, "step5_back_empty")
        st.stop()

    st.session_state["pricing_df"] = pricing_df

    best = pricing_df.sort_values("Subtotal").iloc[0]

    st.success(
        f"Best Option: {best['Vendor']} — order {int(best['Order Qty'])} {best['Order Unit']} — subtotal {money(best['Subtotal'])}"
    )

    st.caption("Choose one or more products to add to the quote cart.")

    for i, (_, row) in enumerate(pricing_df.iterrows()):
        is_best = row["Vendor"] == best["Vendor"] and row["Product"] == best["Product"]
        vendor_option_card(row, i, best=is_best)

    col1, col2 = st.columns(2)

    with col1:
        back_button(4, "step5_back")

    with col2:
        if st.button("Go to Quote Cart", key="step5_go_to_cart", type="primary", use_container_width=True):
            go_to_step(6)

    show_quote_banner()


elif st.session_state["step"] == 6:
    st.subheader("Step 6 — Quote Cart")

    items = st.session_state["quote_items"]

    if not items:
        st.info("No quote lines added yet. Go back to Step 5 and add an item.")
        back_button(5, "step6_back_empty")
        st.stop()

    quote_df = pd.DataFrame(items)

    st.dataframe(
        quote_df.style.format({
            "Unit Price": "${:,.2f}",
            "Subtotal": "${:,.2f}",
            "GST 5%": "${:,.2f}",
            "PST 7%": "${:,.2f}",
            "Total": "${:,.2f}",
        }),
        use_container_width=True,
        hide_index=True,
    )

    subtotal, gst, pst, total = quote_totals()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Items", len(items))
    c2.metric("Subtotal", money(subtotal))
    c3.metric("Tax", money(gst + pst))
    c4.metric("Total", money(total))

    csv = quote_df.to_csv(index=False).encode("utf-8")

    action_col1, action_col2 = st.columns(2)

    with action_col1:
        print_button()

    with action_col2:
        st.download_button(
            "Download CSV",
            csv,
            file_name="smart_shopper_full_quote.csv",
            mime="text/csv",
            use_container_width=True,
        )

    if st.button("Clear Quote Cart / Reset App", key="step6_clear_cart", use_container_width=True):
        reset_app()

    nav_col1, nav_col2 = st.columns(2)

    with nav_col1:
        back_button(5, "step6_back")

    with nav_col2:
        if st.button("Add Another Item", key="step6_add_another", type="primary", use_container_width=True):
            go_to_step(1)