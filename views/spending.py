"""Where the Money Went — expense categories + vendor breakdown."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from core.periods import to_period, period_label
from .components import style_fig, explain, money, empty_state


def render(ctx):
    st.title("Where the Money Went")
    st.caption(ctx.label)
    bank_p = ctx.bank_p
    exp = bank_p[(bank_p["type"] == "Expense") & (bank_p["amount"] < 0)].copy() if bank_p is not None else pd.DataFrame()
    if exp.empty:
        empty_state("spending", "bank transactions")
        return
    exp["spent"] = -exp["amount"]
    total = exp["spent"].sum()

    explain(
        f"Total spending this {ctx.noun}: <b>{money(total)}</b>. The boxes below are sized by how much went to "
        "each category — click a box to zoom into the vendors inside it."
    )

    # ---- treemap: category → vendor ----------------------------------------
    tm = exp.groupby(["category", "vendor"])["spent"].sum().reset_index()
    fig = px.treemap(tm, path=["category", "vendor"], values="spent",
                     color="category", hover_data={"spent": ":$,.0f"})
    fig.update_traces(textinfo="label+value", texttemplate="%{label}<br>%{value:$,.0f}")
    fig.update_layout(title="Spending map — every dollar, by category and vendor")
    st.plotly_chart(style_fig(fig, 520), width="stretch")

    # ---- category trend ------------------------------------------------------
    all_exp = ctx.bank_all[(ctx.bank_all["type"] == "Expense") & (ctx.bank_all["amount"] < 0)].copy()
    all_exp["p"] = to_period(all_exp["date"], ctx.freq)
    top_cats = exp.groupby("category")["spent"].sum().nlargest(6).index
    trend = all_exp[all_exp["category"].isin(top_cats)].groupby(["p", "category"])["amount"].sum().abs().reset_index()
    trend["Period"] = trend["p"].map(lambda p: period_label(p, ctx.freq))
    trend = trend.sort_values("p")
    fig = px.line(trend, x="Period", y="amount", color="category", markers=True, labels={"amount": "", "category": ""})
    fig.update_layout(title=f"Top categories over time, by {ctx.noun}")
    st.plotly_chart(style_fig(fig), width="stretch")

    # ---- vendor table ----------------------------------------------------------
    st.subheader("Vendor breakdown")
    prev = ctx.bank_prev
    prev_v = (
        -prev[(prev["type"] == "Expense") & (prev["amount"] < 0)].groupby("vendor")["amount"].sum()
        if prev is not None and not prev.empty else pd.Series(dtype=float)
    )
    ven = exp.groupby(["vendor", "category"])["spent"].sum().reset_index().sort_values("spent", ascending=False)
    ven["% of spend"] = ven["spent"] / total * 100
    ven["vs prior"] = ven.apply(
        lambda r: (r["spent"] / prev_v[r["vendor"]] - 1) * 100 if r["vendor"] in prev_v.index and prev_v[r["vendor"]] > 0 else None,
        axis=1,
    )
    st.dataframe(
        ven.rename(columns={"vendor": "Vendor", "category": "Category", "spent": "Spent"}),
        width="stretch", hide_index=True,
        column_config={
            "Spent": st.column_config.NumberColumn(format="$%,.0f"),
            "% of spend": st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=float(ven["% of spend"].max())),
            "vs prior": st.column_config.NumberColumn(f"vs last {ctx.noun}", format="%+.0f%%"),
        },
    )
