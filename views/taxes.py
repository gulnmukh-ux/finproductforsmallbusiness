"""Taxes — set-aside planning, deductible spending, quarterly calendar."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core.categorize import DEDUCTIBLE_CATEGORIES
from .components import style_fig, explain, money, kpi_row, GREEN, RED, AMBER


def render(ctx):
    st.title("Tax Planning")
    st.caption(ctx.label)

    bank = ctx.bank_all
    if bank is None or bank.empty:
        st.info("Upload bank transactions to see tax planning.")
        return

    c1, c2 = st.columns(2)
    with c1:
        entity = st.selectbox("Business entity type", ["LLC / Sole proprietor", "S-Corporation", "Partnership", "C-Corporation"])
    with c2:
        rate = st.slider("Assumed effective tax rate (federal + state + SE)", 10, 45, int(ctx.tax_rate * 100),
                         help="Your CPA sets the real number; 25–30% is a common planning assumption for pass-through owners.") / 100
    st.session_state["tax_rate"] = rate

    year = pd.to_datetime(bank["date"]).dt.year.max()
    ytd = bank[pd.to_datetime(bank["date"]).dt.year == year]
    income = ytd[ytd["type"] == "Income"]["amount"].sum()
    expenses = -ytd[(ytd["type"] == "Expense") & (ytd["amount"] < 0)]["amount"].sum()
    profit = income - expenses
    est_tax = max(profit, 0) * rate
    paid = -ytd[ytd["category"] == "Income Taxes"]["amount"].sum()
    gap = est_tax - paid

    kpi_row([
        (f"{year} profit so far (cash basis)", money(profit), None, "Income minus expenses from bank data. Your CPA will adjust for non-cash items."),
        ("Estimated tax on that profit", money(est_tax), None, f"Profit × {rate * 100:.0f}% assumed rate."),
        ("Tax payments made", money(paid), None, "IRS / state tax payments found in the bank data."),
        ("Still to set aside", money(max(gap, 0)), None, None),
    ])

    if profit > 0:
        if gap > est_tax * 0.4:
            st.error(f"⚠️ Roughly **{money(gap)}** of {year} taxes appear unfunded. Surprise tax bills are the #1 cash crisis for small businesses.")
        elif gap > 0:
            st.warning(f"About **{money(gap)}** still to set aside for {year} taxes.")
        else:
            st.success("✅ Tax payments are tracking ahead of estimated liability.")

    explain(
        "The golden rule for owners: <b>move a fixed percentage of every customer deposit into a separate "
        "tax account the day it arrives.</b> Then quarterly payments are a transfer, not a crisis. "
        f"At the assumed rate, that's <b>{rate * 100:.0f}¢ of every profit dollar</b>."
    )

    # ---- set-aside gauge ----------------------------------------------------
    if est_tax > 0:
        funded = min(paid / est_tax, 1.0) * 100
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=funded,
            number={"suffix": "% funded"},
            gauge={
                "axis": {"range": [0, 100], "ticksuffix": "%"},
                "bar": {"color": "#2563EB"},
                "steps": [
                    {"range": [0, 50], "color": "#FEE2E2"},
                    {"range": [50, 80], "color": "#FEF3C7"},
                    {"range": [80, 100], "color": "#D1FAE5"},
                ],
            },
            title={"text": f"{year} estimated taxes funded"},
        ))
        st.plotly_chart(style_fig(fig, 300), width="stretch")

    # ---- quarterly calendar ----------------------------------------------------
    st.subheader("Estimated tax payment calendar")
    today = pd.Timestamp.today().normalize()
    quarters = [
        (f"Q1 {year}", pd.Timestamp(year, 4, 15)),
        (f"Q2 {year}", pd.Timestamp(year, 6, 15)),
        (f"Q3 {year}", pd.Timestamp(year, 9, 15)),
        (f"Q4 {year}", pd.Timestamp(year + 1, 1, 15)),
    ]
    cal = pd.DataFrame({
        "Quarter": [q for q, _ in quarters],
        "Due date": [d.strftime("%b %d, %Y") for _, d in quarters],
        "Suggested payment": [money(est_tax / 4)] * 4,
        "Status": ["Past due date" if d < today else "Upcoming" for _, d in quarters],
    })
    st.dataframe(cal, width="stretch", hide_index=True)

    # ---- deductible spending summary ----------------------------------------------
    st.subheader(f"Deductible business spending, {year} year-to-date")
    ded = (
        ytd[(ytd["amount"] < 0) & ytd["category"].isin(DEDUCTIBLE_CATEGORIES)]
        .groupby("category")["amount"].sum().abs().sort_values(ascending=True)
    )
    if not ded.empty:
        fig = go.Figure(go.Bar(x=ded.values, y=ded.index, orientation="h", marker_color="#14B8A6",
                               texttemplate="%{x:$,.0f}", textposition="outside"))
        fig.update_layout(title=f"Total likely-deductible spending: {money(ded.sum())}")
        st.plotly_chart(style_fig(fig, 30 * len(ded) + 160), width="stretch")
        explain(
            "Every dollar here likely reduces taxable profit — but only if it's documented. "
            "Keep receipts for anything over $75, and keep business and personal spending in separate accounts."
        )

    st.caption(
        "⚖️ This page is planning guidance from cash-basis bank data, not tax advice. "
        "Final numbers come from the tax return prepared by your accountant."
    )
