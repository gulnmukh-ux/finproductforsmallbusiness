"""Advertising — which ad vendor gets the most money, and is it working."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from core.periods import to_period, period_label
from .components import style_fig, explain, money, delta_str, kpi_row, empty_state, GREEN


def render(ctx):
    st.title("Advertising Spend")
    st.caption(ctx.label)
    bank_p, bank_all = ctx.bank_p, ctx.bank_all
    ads_p = bank_p[bank_p["category"] == "Advertising & Marketing"].copy() if bank_p is not None else pd.DataFrame()
    if ads_p.empty:
        empty_state("advertising", "bank transactions that include ad platform charges (Google, Meta, Yelp, ...)")
        return

    ads_p["spent"] = -ads_p["amount"]
    ad_total = ads_p["spent"].sum()
    revenue = bank_p[bank_p["type"] == "Income"]["amount"].sum()
    prev_ads = -ctx.bank_prev[ctx.bank_prev["category"] == "Advertising & Marketing"]["amount"].sum() if not ctx.bank_prev.empty else None

    new_enrollments = None
    if ctx.enrollment_p is not None and not ctx.enrollment_p.empty:
        new_enrollments = (ctx.enrollment_p["status"].str.lower() != "withdrawn").sum()

    kpis = [
        ("Total ad spend", money(ad_total), delta_str(ad_total, prev_ads, ctx.noun), "All advertising & marketing payments this period."),
        ("Ad spend as % of revenue", f"{ad_total / revenue * 100:.1f}%" if revenue else "—", None, "Healthy range for most service businesses: 5–15%."),
        ("Revenue per ad dollar", f"${revenue / ad_total:,.2f}" if ad_total else "—", None, "Rough efficiency: total revenue ÷ total ad spend."),
    ]
    if new_enrollments is not None:
        kpis.append(("Cost per new sign-up", money(ad_total / new_enrollments) if new_enrollments else "—", None,
                     "Ad spend ÷ new enrollments this period (from the enrollment sheet)."))
    kpi_row(kpis)

    explain(
        "This page answers: <b>who do we pay the most for ads, and is the spend pulling new business in?</b> "
        "If one platform takes most of the budget, ask it to prove its cost per new client."
    )

    # ---- vendor ranking -----------------------------------------------------
    c1, c2 = st.columns([1.1, 1])
    by_vendor = ads_p.groupby("vendor")["spent"].sum().sort_values()
    with c1:
        fig = go.Figure(go.Bar(
            x=by_vendor.values, y=by_vendor.index, orientation="h",
            marker_color="#2563EB", texttemplate="%{x:$,.0f}", textposition="outside",
        ))
        fig.update_layout(title="Ad spend by vendor — who gets the most?")
        st.plotly_chart(style_fig(fig, 400), width="stretch")
    with c2:
        fig = px.pie(values=by_vendor.values, names=by_vendor.index, hole=0.5)
        fig.update_traces(textinfo="percent+label", textposition="outside")
        fig.update_layout(title="Share of ad budget", showlegend=False)
        st.plotly_chart(style_fig(fig, 400), width="stretch")

    # ---- ad spend vs revenue over time ---------------------------------------
    hist = bank_all.copy()
    hist["p"] = to_period(hist["date"], ctx.freq)
    ads_t = -hist[hist["category"] == "Advertising & Marketing"].groupby("p")["amount"].sum()
    rev_t = hist[hist["type"] == "Income"].groupby("p")["amount"].sum()
    idx = sorted(set(ads_t.index) | set(rev_t.index))
    labels = [period_label(p, ctx.freq) for p in idx]
    fig = go.Figure()
    fig.add_bar(x=labels, y=ads_t.reindex(idx).fillna(0).values, name="Ad spend", marker_color="#F59E0B")
    fig.add_scatter(x=labels, y=rev_t.reindex(idx).fillna(0).values, name="Revenue", yaxis="y2",
                    mode="lines+markers", line=dict(color=GREEN, width=3))
    fig.update_layout(
        title=f"Does revenue follow ad spend? (by {ctx.noun})",
        yaxis=dict(title="Ad spend"),
        yaxis2=dict(title="Revenue", overlaying="y", side="right", showgrid=False),
    )
    st.plotly_chart(style_fig(fig, 420), width="stretch")

    # ---- per-vendor trend ------------------------------------------------------
    vt = -hist[hist["category"] == "Advertising & Marketing"].groupby(["p", "vendor"])["amount"].sum()
    vt = vt.reset_index().rename(columns={"amount": "spent"})
    vt["Period"] = vt["p"].map(lambda p: period_label(p, ctx.freq))
    vt = vt.sort_values("p")
    fig = px.line(vt, x="Period", y="spent", color="vendor", markers=True, labels={"spent": "", "vendor": ""})
    fig.update_layout(title="Spend per ad vendor over time")
    st.plotly_chart(style_fig(fig), width="stretch")
