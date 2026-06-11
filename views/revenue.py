"""Revenue — service lines, clients, enrollment funnel."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from core.periods import to_period, period_label
from .components import style_fig, explain, money, kpi_row, delta_str, empty_state, GREEN


def render(ctx):
    st.title("Revenue & Service Lines")
    st.caption(ctx.label)
    sales_p = ctx.sales_p
    if sales_p is None or sales_p.empty:
        empty_state("revenue detail", "a sales/revenue Excel sheet (date, client, service, amount)")
        # still show bank-derived income trend
        if ctx.bank_all is not None and not ctx.bank_all.empty:
            hist = ctx.bank_all[ctx.bank_all["type"] == "Income"].copy()
            hist["p"] = to_period(hist["date"], ctx.freq)
            t = hist.groupby("p")["amount"].sum().sort_index()
            fig = px.bar(x=[period_label(p, ctx.freq) for p in t.index], y=t.values, labels={"x": "", "y": ""})
            fig.update_traces(marker_color=GREEN)
            fig.update_layout(title=f"Deposits (income) by {ctx.noun} — from bank data")
            st.plotly_chart(style_fig(fig), width="stretch")
        return

    total = sales_p["amount"].sum()
    prev_total = ctx.sales_prev["amount"].sum() if ctx.sales_prev is not None and not ctx.sales_prev.empty else None
    n_clients = sales_p["client"].nunique()
    avg_per_client = total / n_clients if n_clients else 0

    kpi_row([
        ("Revenue (billed)", money(total), delta_str(total, prev_total, ctx.noun), "From the sales sheet — may differ from bank deposits by timing."),
        ("Active clients", f"{n_clients}", None, "Clients with billed revenue this period."),
        ("Avg revenue per client", money(avg_per_client), None, None),
        ("Top service line", sales_p.groupby("service")["amount"].sum().idxmax(), None, None),
    ])

    # ---- service line mix over time ------------------------------------------
    hist = ctx.sales_all.copy()
    hist["p"] = to_period(hist["date"], ctx.freq)
    g = hist.groupby(["p", "service"])["amount"].sum().reset_index()
    g["Period"] = g["p"].map(lambda p: period_label(p, ctx.freq))
    g = g.sort_values("p")
    fig = px.bar(g, x="Period", y="amount", color="service", labels={"amount": "", "service": ""})
    fig.update_layout(title=f"Revenue by service line, by {ctx.noun}", barmode="stack")
    st.plotly_chart(style_fig(fig, 420), width="stretch")

    c1, c2 = st.columns(2)
    with c1:
        svc = sales_p.groupby("service")["amount"].sum().sort_values()
        fig = go.Figure(go.Bar(x=svc.values, y=svc.index, orientation="h", marker_color="#2563EB",
                               texttemplate="%{x:$,.0f}", textposition="outside"))
        fig.update_layout(title="Service lines this period")
        st.plotly_chart(style_fig(fig, 380), width="stretch")
    with c2:
        cl = sales_p.groupby("client")["amount"].sum().sort_values().tail(10)
        fig = go.Figure(go.Bar(x=cl.values, y=cl.index, orientation="h", marker_color="#10B981",
                               texttemplate="%{x:$,.0f}", textposition="outside"))
        fig.update_layout(title="Top 10 clients this period")
        st.plotly_chart(style_fig(fig, 380), width="stretch")

    explain(
        "Watch two things here: <b>which service lines grow</b> (put marketing behind those) and "
        "<b>how much revenue depends on the top client</b> — above ~25–30% is a concentration risk."
    )

    # ---- enrollment funnel ------------------------------------------------------
    if ctx.enrollment_p is not None and not ctx.enrollment_p.empty:
        st.subheader("New business funnel (enrollment / admissions)")
        e = ctx.enrollment_p
        c1, c2 = st.columns([1, 1.2])
        with c1:
            counts = e["status"].value_counts()
            fig = px.pie(values=counts.values, names=counts.index, hole=0.5)
            fig.update_traces(textinfo="value+label")
            fig.update_layout(title="Sign-ups by status", showlegend=False)
            st.plotly_chart(style_fig(fig, 340), width="stretch")
        with c2:
            byprog = e.groupby(["program", "status"]).size().reset_index(name="count")
            fig = px.bar(byprog, x="program", y="count", color="status", labels={"count": "", "program": "", "status": ""})
            fig.update_layout(title="Sign-ups by program")
            st.plotly_chart(style_fig(fig, 340), width="stretch")
