"""Data Review & Fix-ups — verify auto-categorization, fix what's wrong.

This is where the advisor handles the 'fixations': uncategorized rows,
mis-categorized vendors, duplicates, and unrecognized Excel sheets.
Edits persist for the session and flow into every chart.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core.categorize import CATEGORY_RULES, INCOME_RULES
from .components import explain, money

ALL_CATEGORIES = sorted(
    {c for c, _ in CATEGORY_RULES} | {c for c, _ in INCOME_RULES}
    | {"Other Income", "Uncategorized", "Transfers", "Owner Draws / Distributions"}
)


def render(ctx):
    st.title("Data Review & Fix-ups")
    bank = st.session_state.get("bank_categorized")
    if bank is None or bank.empty:
        st.info("Upload bank transactions (or load demo data) first.")
        return

    n_uncat = (bank["category"] == "Uncategorized").sum()
    uncat_amt = -bank.loc[(bank["category"] == "Uncategorized") & (bank["amount"] < 0), "amount"].sum()

    c1, c2, c3 = st.columns(3)
    c1.metric("Transactions loaded", f"{len(bank):,}")
    c2.metric("Needing review", f"{n_uncat:,}")
    c3.metric("Unreviewed spending", money(uncat_amt))

    # ---- duplicate check -----------------------------------------------------
    dupes = bank[bank.duplicated(subset=["date", "description", "amount"], keep=False)]
    if not dupes.empty:
        st.warning(
            f"⚠️ **{len(dupes)} possible duplicate transactions** (same date, description and amount) — "
            "often caused by uploading overlapping bank exports."
        )
        with st.expander("Show possible duplicates"):
            st.dataframe(dupes.sort_values(["description", "date"]), width="stretch", hide_index=True)
        if st.button("Remove duplicates (keep first of each)"):
            st.session_state["bank_categorized"] = bank.drop_duplicates(
                subset=["date", "description", "amount"], keep="first"
            ).reset_index(drop=True)
            st.rerun()

    # ---- unrecognized sheets ----------------------------------------------------
    unrec = st.session_state.get("unrecognized_sheets", [])
    if unrec:
        st.warning(
            "These Excel sheets couldn't be auto-classified and were skipped: "
            + ", ".join(f"`{s}`" for s in unrec)
            + ". Rename them (e.g. 'Sales', 'Payroll', 'Attendance') or make sure they have date/amount columns, then re-upload."
        )

    explain(
        "Fix categories below — changes apply to <b>every chart and report instantly</b>. "
        "Tip: sort by Category to batch-fix all 'Uncategorized' rows at once. "
        "Changing a vendor's category here also reclassifies every other transaction from the same vendor if you tick the box."
    )

    apply_vendor_wide = st.checkbox("Apply category changes to ALL transactions from the same vendor", value=True)
    only_uncat = st.checkbox("Show only rows needing review", value=n_uncat > 0)

    view = bank[bank["category"] == "Uncategorized"] if only_uncat else bank
    edited = st.data_editor(
        view[["date", "description", "vendor", "category", "amount"]],
        width="stretch",
        hide_index=False,
        disabled=["date", "description", "amount"],
        column_config={
            "date": st.column_config.DateColumn("Date"),
            "description": st.column_config.TextColumn("Bank description", width="large"),
            "vendor": st.column_config.TextColumn("Vendor"),
            "category": st.column_config.SelectboxColumn("Category", options=ALL_CATEGORIES),
            "amount": st.column_config.NumberColumn("Amount", format="$%,.2f"),
        },
        key="review_editor",
    )

    if st.button("💾 Apply fixes", type="primary"):
        updated = bank.copy()
        changed = edited[
            (edited["category"] != view["category"]) | (edited["vendor"] != view["vendor"])
        ]
        for idx, row in changed.iterrows():
            updated.loc[idx, ["vendor", "category"]] = [row["vendor"], row["category"]]
            if apply_vendor_wide:
                same_vendor = updated["vendor"] == row["vendor"]
                updated.loc[same_vendor, "category"] = row["category"]
        # re-derive type from category
        updated["type"] = "Expense"
        updated.loc[updated["amount"] > 0, "type"] = "Income"
        updated.loc[updated["category"] == "Transfers", "type"] = "Transfer"
        updated.loc[updated["category"] == "Owner Draws / Distributions", "type"] = "Owner Draw"
        st.session_state["bank_categorized"] = updated
        st.success(f"Applied {len(changed)} fix(es).")
        st.rerun()
