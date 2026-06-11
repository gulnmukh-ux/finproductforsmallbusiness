"""Executive Overview — the page you open in front of the client."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from core.export import build_excel_report
from core.periods import to_period, period_label
from .components import kpi_row, money, delta_str, style_fig, explain, insight_card, empty_state, GREEN, RED


def render(ctx):
    st.title("Executive Overview")
    st.caption(f"{ctx.business_name} · {ctx.label}")

    bank_p, bank_prev = ctx.bank_p, ctx.bank_prev
    if bank_p is None or bank_p.empty:
        empty_state("this period", "bank transactions")
        return

    inc = bank_p[bank_p["type"] == "Income"]["amount"].sum()
    exp = -bank_p[(bank_p["type"] == "Expense") & (bank_p["amount"] < 0)]["amount"].sum()
    draws = -bank_p[bank_p["type"] == "Owner Draw"]["amount"].sum()
    net = inc - exp

    prev_inc = bank_prev[bank_prev["type"] == "Income"]["amount"].sum() if not bank_prev.empty else None
    prev_exp = -bank_prev[(bank_prev["type"] == "Expense") & (bank_prev["amount"] < 0)]["amount"].sum() if not bank_prev.empty else None

    kpi_row([
        ("Money In", money(inc), delta_str(inc, prev_inc, ctx.noun),
         "All deposits from customers and other income this period."),
        ("Money Out", money(exp), delta_str(exp, prev_exp, ctx.noun),
         "All business spending this period (excludes transfers and owner draws)."),
        ("Kept (Net Cash Flow)", money(net),
         delta_str(net, (prev_inc - prev_exp) if prev_inc is not None and prev_exp is not None else None, ctx.noun),
         "Money In minus Money Out. The single most important number to watch."),
        ("Owner Draws", money(draws), None,
         "Money the owner(s) took out of the business. Tracked separately from expenses."),
    ])

    if inc > 0:
        margin = net / inc * 100
        verdict = (
            f"For every **$1** that came in this {ctx.noun}, the business kept **{max(net, 0) / inc:.2f}¢**"
            if net >= 0 else
            f"The business spent **{money(abs(net))} more than it earned** this {ctx.noun}"
        )
        explain(f"{verdict}. Cash margin: **{margin:.0f}%**. A healthy service business typically keeps 15–30%.")

    # ---- trend: money in vs out over all periods -------------------------
    st.subheader("The big picture")
    trend = ctx.bank_all.copy()
    trend["p"] = to_period(trend["date"], ctx.freq)
    g = trend.groupby(["p", "type"])["amount"].sum().reset_index()
    g["amount"] = g["amount"].abs()
    g = g[g["type"].isin(["Income", "Expense"])]
    g["Period"] = g["p"].map(lambda p: period_label(p, ctx.freq))
    g = g.sort_values("p")
    fig = px.bar(
        g, x="Period", y="amount", color="type", barmode="group",
        color_discrete_map={"Income": GREEN, "Expense": RED},
        labels={"amount": "", "type": ""},
    )
    fig.update_layout(title=f"Money in vs money out, by {ctx.noun}")
    st.plotly_chart(style_fig(fig), width="stretch")

    # ---- mini panels ------------------------------------------------------
    c1, c2 = st.columns(2)
    with c1:
        cat = (
            bank_p[(bank_p["type"] == "Expense") & (bank_p["amount"] < 0)]
            .groupby("category")["amount"].sum().abs().sort_values(ascending=False).head(6)
        )
        if not cat.empty:
            fig = px.pie(values=cat.values, names=cat.index, hole=0.55)
            fig.update_traces(textposition="outside", textinfo="label+percent")
            fig.update_layout(title="Where the money went (top 6)", showlegend=False)
            st.plotly_chart(style_fig(fig, 360), width="stretch")
    with c2:
        if ctx.sales_p is not None and not ctx.sales_p.empty:
            svc = ctx.sales_p.groupby("service")["amount"].sum().sort_values()
            fig = go.Figure(go.Bar(x=svc.values, y=svc.index, orientation="h", marker_color="#2563EB"))
            fig.update_layout(title="Revenue by service line")
            st.plotly_chart(style_fig(fig, 360), width="stretch")
        else:
            top_v = (
                bank_p[(bank_p["type"] == "Expense") & (bank_p["amount"] < 0)]
                .groupby("vendor")["amount"].sum().abs().sort_values().tail(8)
            )
            fig = go.Figure(go.Bar(x=top_v.values, y=top_v.index, orientation="h", marker_color="#2563EB"))
            fig.update_layout(title="Biggest vendors this period")
            st.plotly_chart(style_fig(fig, 360), width="stretch")

    # ---- top 3 priorities --------------------------------------------------
    if ctx.insights:
        st.subheader("Top priorities")
        for ins in ctx.insights[:3]:
            insight_card(ins.severity, ins.title, ins.detail, ins.next_step)
        st.caption("Full list on the **Suggestions & Next Steps** page.")

    # ---- export ------------------------------------------------------------
    st.divider()
    data = build_excel_report(ctx.label, bank_p, ctx.sales_p, ctx.client_pnl, ctx.insights)
    st.download_button(
        "📥 Download this report as Excel (client leave-behind)",
        data=data,
        file_name=f"{ctx.business_name.replace(' ', '_')}_{ctx.label.replace(' ', '_')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
