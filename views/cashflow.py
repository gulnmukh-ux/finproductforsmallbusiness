"""Cash Flow — where cash came from, where it went, and the running balance."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from core.periods import to_period, period_label
from .components import style_fig, explain, money, empty_state, GREEN, RED


def render(ctx):
    st.title("Cash Flow")
    st.caption(ctx.label)
    bank_p = ctx.bank_p
    if bank_p is None or bank_p.empty:
        empty_state("cash flow", "bank transactions")
        return

    explain(
        "Cash flow answers one question: <b>did the bank account grow or shrink, and why?</b> "
        "The waterfall below starts with money in, subtracts each spending group, and lands on what was kept."
    )

    # ---- waterfall ---------------------------------------------------------
    inc = bank_p[bank_p["type"] == "Income"]["amount"].sum()
    exp_by_cat = (
        bank_p[(bank_p["type"] == "Expense") & (bank_p["amount"] < 0)]
        .groupby("category")["amount"].sum().sort_values()
    )
    top = exp_by_cat.head(7)
    other = exp_by_cat.iloc[7:].sum()
    draws = bank_p[bank_p["type"] == "Owner Draw"]["amount"].sum()

    labels = ["Money In"] + list(top.index) + (["Other expenses"] if other < 0 else []) + (["Owner draws"] if draws < 0 else []) + ["Cash kept"]
    values = [inc] + list(top.values) + ([other] if other < 0 else []) + ([draws] if draws < 0 else []) + [0]
    measures = ["absolute"] + ["relative"] * (len(values) - 2) + ["total"]

    fig = go.Figure(go.Waterfall(
        x=labels, y=values, measure=measures,
        increasing=dict(marker=dict(color=GREEN)),
        decreasing=dict(marker=dict(color=RED)),
        totals=dict(marker=dict(color="#2563EB")),
        connector=dict(line=dict(color="#CBD5E1")),
        texttemplate="%{delta:$,.0f}", textposition="outside",
    ))
    fig.update_layout(title=f"Cash waterfall — {ctx.label}")
    st.plotly_chart(style_fig(fig, 460), width="stretch")

    # ---- net cash flow by period + cumulative ------------------------------
    all_tx = ctx.bank_all.copy()
    all_tx["p"] = to_period(all_tx["date"], ctx.freq)
    flows = all_tx[all_tx["type"].isin(["Income", "Expense"])]
    net = flows.groupby("p")["amount"].sum().sort_index()
    cum = all_tx.sort_values("date").set_index("date")["amount"].cumsum()

    c1, c2 = st.columns(2)
    with c1:
        df = pd.DataFrame({"Period": [period_label(p, ctx.freq) for p in net.index], "Net": net.values})
        fig = px.bar(df, x="Period", y="Net", color=df["Net"] > 0,
                     color_discrete_map={True: GREEN, False: RED}, labels={"Net": ""})
        fig.update_layout(title=f"Net cash flow by {ctx.noun}", showlegend=False)
        st.plotly_chart(style_fig(fig), width="stretch")
    with c2:
        fig = px.area(x=cum.index, y=cum.values, labels={"x": "", "y": ""})
        fig.update_traces(line_color="#2563EB", fillcolor="rgba(37,99,235,.12)")
        fig.update_layout(title="Cumulative cash position (relative to first upload)")
        st.plotly_chart(style_fig(fig), width="stretch")

    # ---- runway -------------------------------------------------------------
    monthly = all_tx[all_tx["type"].isin(["Income", "Expense"])].copy()
    monthly["m"] = pd.to_datetime(monthly["date"]).dt.to_period("M")
    m_net = monthly.groupby("m")["amount"].sum()
    m_out = -monthly[monthly["amount"] < 0].groupby("m")["amount"].sum()
    avg_out = m_out.tail(3).mean()
    avg_net = m_net.tail(3).mean()
    st.subheader("Cash cushion check")
    c1, c2, c3 = st.columns(3)
    c1.metric("Avg monthly spending (last 3 mo)", money(avg_out))
    c2.metric("Avg monthly net (last 3 mo)", money(avg_net))
    cushion = st.session_state.get("cash_on_hand", 0.0)
    with c3:
        cushion = st.number_input("Cash in bank today ($)", min_value=0.0, value=float(cushion), step=1000.0, key="cash_on_hand")
    if cushion and avg_out:
        months_cover = cushion / avg_out
        if months_cover < 2:
            st.error(f"⚠️ Today's cash covers **{months_cover:.1f} months** of typical spending. Advisors recommend 3–6 months.")
        elif months_cover < 3:
            st.warning(f"Today's cash covers **{months_cover:.1f} months** of typical spending. Target: 3–6 months.")
        else:
            st.success(f"✅ Today's cash covers **{months_cover:.1f} months** of typical spending — a healthy cushion.")
