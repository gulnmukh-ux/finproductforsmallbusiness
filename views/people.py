"""People — employees, contractors, commissions, payroll load."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from core.periods import to_period, period_label
from .components import style_fig, explain, money, kpi_row, delta_str, empty_state


def render(ctx):
    st.title("People: Employees & Contractors")
    st.caption(ctx.label)

    bank_p = ctx.bank_p
    payroll_p = ctx.payroll_p
    has_sheet = payroll_p is not None and not payroll_p.empty

    bank_people = -bank_p[bank_p["category"].isin(["Payroll & Wages", "Contractors", "Payroll Taxes"]) & (bank_p["amount"] < 0)]["amount"].sum() if bank_p is not None and not bank_p.empty else 0
    revenue = bank_p[bank_p["type"] == "Income"]["amount"].sum() if bank_p is not None and not bank_p.empty else 0

    if not has_sheet and bank_people == 0:
        empty_state("people costs", "a payroll/salary Excel sheet or bank transactions with payroll activity")
        return

    if has_sheet:
        emp = payroll_p[payroll_p["worker_type"] == "Employee"]["amount"].sum()
        con = payroll_p[payroll_p["worker_type"] == "Contractor"]["amount"].sum()
        total_comp = emp + con
        headcount = payroll_p["name"].nunique()
    else:
        emp = -bank_p[bank_p["category"] == "Payroll & Wages"]["amount"].clip(upper=0).sum()
        con = -bank_p[bank_p["category"] == "Contractors"]["amount"].clip(upper=0).sum()
        total_comp = emp + con
        headcount = None

    comm = ctx.commission_p["amount"].sum() if ctx.commission_p is not None and not ctx.commission_p.empty else 0

    kpis = [
        ("Total people cost", money(max(total_comp, bank_people)), None,
         "Wages + contractor payments (+ payroll taxes when read from the bank)."),
        ("Employees (W-2)", money(emp), None, None),
        ("Contractors (1099)", money(con), None, None),
        ("People cost % of revenue", f"{max(total_comp, bank_people) / revenue * 100:.0f}%" if revenue else "—", None,
         "Comfortable zone for service businesses: 30–45%."),
    ]
    if comm:
        kpis[2] = ("Contractors (1099)", money(con), None, None)
        kpis.append(("Commissions", money(comm), None, "From the commission sheet."))
    kpi_row(kpis[:4])

    explain(
        "Staff is usually the #1 cost in a service business. The split between <b>employees (W-2)</b> and "
        "<b>contractors (1099)</b> matters for taxes, and the trend tells you whether the team is growing "
        "faster than revenue."
    )

    # ---- per-person breakdown (needs sheet) ----------------------------------
    if has_sheet:
        c1, c2 = st.columns([1.2, 1])
        with c1:
            pp = payroll_p.groupby(["name", "worker_type", "role"])["amount"].sum().reset_index().sort_values("amount")
            fig = px.bar(pp, x="amount", y="name", color="worker_type", orientation="h",
                         hover_data=["role"], labels={"amount": "", "name": "", "worker_type": ""},
                         color_discrete_map={"Employee": "#2563EB", "Contractor": "#F59E0B"})
            fig.update_layout(title="Pay per person this period")
            st.plotly_chart(style_fig(fig, 420), width="stretch")
        with c2:
            split = payroll_p.groupby("worker_type")["amount"].sum()
            fig = px.pie(values=split.values, names=split.index, hole=0.55,
                         color=split.index, color_discrete_map={"Employee": "#2563EB", "Contractor": "#F59E0B"})
            fig.update_traces(textinfo="percent+label")
            fig.update_layout(title="Employee vs contractor mix", showlegend=False)
            st.plotly_chart(style_fig(fig, 420), width="stretch")

    # ---- trend: people cost vs revenue ----------------------------------------
    hist = ctx.bank_all.copy()
    hist["p"] = to_period(hist["date"], ctx.freq)
    ppl_t = -hist[hist["category"].isin(["Payroll & Wages", "Contractors", "Payroll Taxes"])].groupby("p")["amount"].sum()
    rev_t = hist[hist["type"] == "Income"].groupby("p")["amount"].sum()
    idx = sorted(set(ppl_t.index) | set(rev_t.index))
    labels = [period_label(p, ctx.freq) for p in idx]
    pct = (ppl_t.reindex(idx).fillna(0) / rev_t.reindex(idx)).replace([float("inf")], None) * 100
    fig = go.Figure()
    fig.add_bar(x=labels, y=ppl_t.reindex(idx).fillna(0).values, name="People cost", marker_color="#8B5CF6")
    fig.add_scatter(x=labels, y=pct.values, name="% of revenue", yaxis="y2", mode="lines+markers",
                    line=dict(color="#EF4444", width=3))
    fig.update_layout(
        title=f"People cost and its share of revenue, by {ctx.noun}",
        yaxis=dict(title="People cost"),
        yaxis2=dict(title="% of revenue", overlaying="y", side="right", showgrid=False, ticksuffix="%"),
    )
    st.plotly_chart(style_fig(fig, 420), width="stretch")

    # ---- utilization (needs attendance) -----------------------------------------
    if ctx.attendance_p is not None and not ctx.attendance_p.empty and has_sheet:
        st.subheader("Staff utilization")
        hours = ctx.attendance_p.groupby("name")["hours"].sum()
        pay = payroll_p.groupby("name")["amount"].sum()
        util = pd.DataFrame({"Hours with clients": hours, "Pay": pay}).dropna()
        if not util.empty:
            util["Cost per client-hour"] = util["Pay"] / util["Hours with clients"]
            util = util.sort_values("Cost per client-hour", ascending=False).reset_index(names="Name")
            st.dataframe(
                util, width="stretch", hide_index=True,
                column_config={
                    "Pay": st.column_config.NumberColumn(format="$%,.0f"),
                    "Hours with clients": st.column_config.NumberColumn(format="%.0f"),
                    "Cost per client-hour": st.column_config.NumberColumn(format="$%,.0f"),
                },
            )
            explain(
                "<b>Cost per client-hour</b> = what you pay someone ÷ hours they spend serving clients. "
                "A high number isn't bad by itself (managers serve fewer hours), but big gaps between "
                "similar roles are worth a conversation."
            )
