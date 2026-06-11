"""Cost of Service per Client — the allocation model, explained."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from core.allocation import allocate_cost_of_service, allocate_by_service_line, OVERHEAD_METHODS
from .components import style_fig, explain, money, kpi_row, empty_state, GREEN, RED, AMBER


def render(ctx):
    st.title("Cost of Service per Client")
    st.caption(ctx.label)

    if ctx.sales_p is None or ctx.sales_p.empty:
        empty_state("per-client costing", "a sales sheet with client names (plus timesheets for best accuracy)")
        return

    method = st.selectbox(
        "How should shared overhead (rent, software, admin...) be split across clients?",
        OVERHEAD_METHODS,
        help="Revenue share is the standard default. Labor-hours share is better when some small clients "
             "consume a lot of staff time. Even split is rarely right but useful as a sanity check.",
    )
    pnl, notes = allocate_cost_of_service(ctx.sales_p, ctx.bank_p, ctx.payroll_p, ctx.attendance_p, method)
    if pnl.empty:
        st.warning(notes[0] if notes else "Not enough data to build the model.")
        return

    profitable = (pnl["profit"] > 0).sum()
    kpi_row([
        ("Clients analyzed", f"{len(pnl)}", None, None),
        ("Profitable clients", f"{profitable} of {len(pnl)}", None, "Clients whose revenue covers their fully-loaded cost."),
        ("Best margin", f"{pnl['margin_pct'].max():.0f}% ({pnl.loc[pnl['margin_pct'].idxmax(), 'client']})", None, None),
        ("Worst margin", f"{pnl['margin_pct'].min():.0f}% ({pnl.loc[pnl['margin_pct'].idxmin(), 'client']})", None, None),
    ])

    explain(
        "Every client's revenue is matched against three cost layers: <b>staff time</b> (allocated by actual "
        "hours worked per client when timesheets exist), <b>direct costs</b> (materials, subcontractors), and a "
        "<b>fair share of overhead</b> (rent, software, admin). What's left is that client's true profit. "
        "This is how we find clients that look big but quietly lose money."
    )

    # ---- stacked revenue vs cost per client -----------------------------------
    d = pnl.sort_values("revenue", ascending=True)
    fig = go.Figure()
    fig.add_bar(y=d["client"], x=d["direct_labor"], name="Staff time", orientation="h", marker_color="#8B5CF6")
    fig.add_bar(y=d["client"], x=d["direct_costs"], name="Direct costs", orientation="h", marker_color="#F59E0B")
    fig.add_bar(y=d["client"], x=d["overhead"], name="Overhead share", orientation="h", marker_color="#94A3B8")
    fig.add_scatter(y=d["client"], x=d["revenue"], name="Revenue", mode="markers",
                    marker=dict(symbol="line-ns", size=22, line=dict(width=3, color="#10B981")))
    fig.update_layout(barmode="stack", title="Cost stack vs revenue per client (green line = revenue)")
    st.plotly_chart(style_fig(fig, 30 * len(d) + 180), width="stretch")

    # ---- margin chart -----------------------------------------------------------
    d2 = pnl.sort_values("margin_pct")
    colors = [RED if m < 10 else AMBER if m < 25 else GREEN for m in d2["margin_pct"]]
    fig = go.Figure(go.Bar(x=d2["margin_pct"], y=d2["client"], orientation="h", marker_color=colors,
                           texttemplate="%{x:.0f}%", textposition="outside"))
    fig.update_layout(title="Profit margin per client (red < 10%, amber < 25%)")
    fig.update_xaxes(ticksuffix="%")
    st.plotly_chart(style_fig(fig, 30 * len(d2) + 180), width="stretch")

    # ---- table -------------------------------------------------------------------
    st.subheader("Per-client profit & loss")
    table = pnl.rename(columns={
        "client": "Client", "revenue": "Revenue", "direct_labor": "Staff Time",
        "direct_costs": "Direct Costs", "overhead": "Overhead Share",
        "total_cost": "Total Cost", "profit": "Profit", "margin_pct": "Margin",
    })
    st.dataframe(
        table, width="stretch", hide_index=True,
        column_config={
            **{c: st.column_config.NumberColumn(format="$%,.0f") for c in
               ["Revenue", "Staff Time", "Direct Costs", "Overhead Share", "Total Cost", "Profit"]},
            "Margin": st.column_config.NumberColumn(format="%.1f%%"),
        },
    )

    # ---- service line rollup --------------------------------------------------------
    svc = allocate_by_service_line(ctx.sales_p, pnl)
    if not svc.empty:
        st.subheader("Same model, rolled up by service line")
        fig = go.Figure()
        fig.add_bar(x=svc["service"], y=svc["revenue"], name="Revenue", marker_color=GREEN)
        fig.add_bar(x=svc["service"], y=svc["total_cost"], name="Fully-loaded cost", marker_color="#94A3B8")
        fig.update_layout(barmode="group", title="Service line revenue vs fully-loaded cost")
        st.plotly_chart(style_fig(fig), width="stretch")

    # ---- methodology ------------------------------------------------------------------
    with st.expander("📖 How these numbers were calculated (show this to the client)"):
        for n in notes:
            st.markdown(f"- {n}")
        st.markdown(
            "- Owner draws, transfers and income taxes are **excluded** — they are not costs of serving clients.\n"
            "- This is a management model, not an audit. Its job is to rank clients correctly, "
            "and ranking is robust even when individual allocations are approximate."
        )
