"""CFO Advisory Dashboard — entry point.

Run with:  streamlit run app.py
"""

from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import streamlit as st

from core import sample_data
from core.allocation import allocate_cost_of_service
from core.categorize import categorize
from core.ingest import parse_bank_file, parse_client_workbook
from core.insights import generate_insights
from core.periods import FREQ_NOUN, available_periods, filter_period, period_label
from views import (advertising, cashflow, clients, data_review, insights_page,
                   overview, people, revenue, spending, taxes)

st.set_page_config(
    page_title="CFO Advisory Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

OPERATIONAL_KEYS = ["sales", "payroll", "attendance", "enrollment", "commission"]

PAGES = {
    "📌 Executive Overview": overview,
    "💵 Cash Flow": cashflow,
    "🧾 Where the Money Went": spending,
    "📣 Advertising": advertising,
    "👥 People (Payroll & Contractors)": people,
    "📈 Revenue & Service Lines": revenue,
    "🎯 Cost of Service per Client": clients,
    "🏛️ Taxes": taxes,
    "✅ Suggestions & Next Steps": insights_page,
    "🛠️ Data Review & Fix-ups": data_review,
}


def load_demo():
    data = sample_data.generate()
    st.session_state["bank_categorized"] = categorize(data["bank"])
    for k in OPERATIONAL_KEYS:
        st.session_state[k] = data[k]
    st.session_state["business_name"] = "Brightpath Learning Center (demo)"
    st.session_state["unrecognized_sheets"] = []


def merge_frames(key: str, new_df: pd.DataFrame):
    cur = st.session_state.get(key)
    st.session_state[key] = pd.concat([cur, new_df], ignore_index=True) if cur is not None else new_df


# ---------------------------------------------------------------------------
# Sidebar: branding, uploads, period controls
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## 📊 CFO Advisory Dashboard")
    st.session_state.setdefault("business_name", "Your Business")
    st.session_state["business_name"] = st.text_input("Client business name", st.session_state["business_name"])

    st.markdown("### 1 · Upload client files")
    bank_files = st.file_uploader(
        "Bank transactions (CSV / Excel)", type=["csv", "xlsx", "xls"],
        accept_multiple_files=True,
        help="Any bank or QuickBooks export with date, description and amount (or debit/credit) columns.",
    )
    wb_files = st.file_uploader(
        "Client workbooks (sales, payroll, attendance, enrollment…)",
        type=["xlsx", "xls", "csv"], accept_multiple_files=True,
        help="Sheets are auto-detected by name and columns: Sales, Commission, Payroll/Salaries, Attendance/Hours, Enrollment/Admissions.",
    )

    processed = st.session_state.setdefault("processed_files", set())
    for f in (bank_files or []):
        if f.name not in processed:
            try:
                merge_frames("bank_raw", parse_bank_file(f))
                st.session_state["bank_categorized"] = categorize(st.session_state["bank_raw"])
                processed.add(f.name)
                st.success(f"✓ {f.name}")
            except ValueError as e:
                st.error(f"{f.name}: {e}")
    for f in (wb_files or []):
        if f.name not in processed:
            parsed = parse_client_workbook(f)
            unrec = parsed.pop("unrecognized", [])
            if unrec:
                st.session_state.setdefault("unrecognized_sheets", []).extend(unrec)
            for kind, df in parsed.items():
                merge_frames(kind, df)
            processed.add(f.name)
            found = ", ".join(parsed.keys()) or "no recognizable sheets"
            st.success(f"✓ {f.name} → {found}")

    c1, c2 = st.columns(2)
    if c1.button("🎬 Load demo data", width="stretch"):
        load_demo()
        st.rerun()
    if c2.button("🗑️ Clear all data", width="stretch"):
        for k in ["bank_raw", "bank_categorized", "processed_files", "unrecognized_sheets", *OPERATIONAL_KEYS]:
            st.session_state.pop(k, None)
        st.rerun()

    st.markdown("### 2 · Report period")
    freq = st.radio("Frequency", ["Weekly", "Monthly", "Quarterly", "Yearly"], index=1, horizontal=True)

    bank = st.session_state.get("bank_categorized")
    periods = available_periods(bank, freq) if bank is not None else []
    if periods:
        labels = [period_label(p, freq) for p in periods]
        sel = st.selectbox("Period", list(range(len(periods))), index=len(periods) - 1,
                           format_func=lambda i: labels[i])
        period = periods[sel]
    else:
        period = None

    st.markdown("### 3 · Report pages")
    page_name = st.radio("Go to", list(PAGES.keys()), label_visibility="collapsed")

    st.divider()
    st.caption("Built for CFO advisory reviews: bookkeeping, taxes, payroll and growth — explained in plain English.")


# ---------------------------------------------------------------------------
# Build the page context
# ---------------------------------------------------------------------------
if bank is None or bank.empty:
    st.title("📊 CFO Advisory Dashboard")
    st.markdown(
        f"""
### Welcome
This dashboard turns a client's raw files into a boardroom-ready financial review.

**Get started in the sidebar:**
1. Upload **bank transactions** (CSV/Excel from any bank or QuickBooks)
2. Upload **client workbooks** — sales, commissions, salaries, attendance, enrollment (sheets auto-detected)
3. Pick **weekly, monthly, quarterly or yearly** reporting

Or click **🎬 Load demo data** to explore with a realistic sample business.

| What clients ask | Where it's answered |
|---|---|
| *"Where did the money go?"* | Where the Money Went · Cash Flow |
| *"Which ad platform are we overpaying?"* | Advertising |
| *"What does each client really cost us?"* | Cost of Service per Client |
| *"Are we ready for taxes?"* | Taxes |
| *"What should we do next?"* | Suggestions & Next Steps |
"""
    )
    st.stop()

prev = period - 1 if period is not None else None
bank_p = filter_period(bank, period, freq)
bank_prev = filter_period(bank, prev, freq) if prev is not None else bank.iloc[0:0]


def get_op(key: str):
    df = st.session_state.get(key)
    if df is None or df.empty:
        return None, None
    return df, filter_period(df, period, freq)


sales_all, sales_p = get_op("sales")
payroll_all, payroll_p = get_op("payroll")
attendance_all, attendance_p = get_op("attendance")
enrollment_all, enrollment_p = get_op("enrollment")
commission_all, commission_p = get_op("commission")
sales_prev = filter_period(sales_all, prev, freq) if sales_all is not None and prev is not None else None

tax_rate = st.session_state.get("tax_rate", 0.25)
client_pnl, _ = allocate_cost_of_service(sales_p, bank_p, payroll_p, attendance_p) if sales_p is not None else (None, [])
insights = generate_insights(bank_p, bank_prev, bank, client_pnl, FREQ_NOUN[freq], tax_rate)

ctx = SimpleNamespace(
    business_name=st.session_state["business_name"],
    freq=freq,
    noun=FREQ_NOUN[freq],
    period=period,
    label=f"{period_label(period, freq)} · {freq} report",
    bank_all=bank, bank_p=bank_p, bank_prev=bank_prev,
    sales_all=sales_all, sales_p=sales_p, sales_prev=sales_prev,
    payroll_all=payroll_all, payroll_p=payroll_p,
    attendance_all=attendance_all, attendance_p=attendance_p,
    enrollment_all=enrollment_all, enrollment_p=enrollment_p,
    commission_all=commission_all, commission_p=commission_p,
    client_pnl=client_pnl,
    insights=insights,
    tax_rate=tax_rate,
)

PAGES[page_name].render(ctx)
