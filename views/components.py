"""Shared UI helpers: KPI rows, chart styling, plain-English blocks."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

PALETTE = ["#2563EB", "#0EA5E9", "#10B981", "#F59E0B", "#EF4444",
           "#8B5CF6", "#EC4899", "#14B8A6", "#F97316", "#64748B"]
GREEN, AMBER, RED = "#10B981", "#F59E0B", "#EF4444"

px.defaults.color_discrete_sequence = PALETTE


def money(x: float, decimals: int = 0) -> str:
    if pd.isna(x):
        return "—"
    return f"${x:,.{decimals}f}"


def style_fig(fig: go.Figure, height: int = 380) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=40, b=10),
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(family="Inter, sans-serif", size=13, color="#0F172A"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        hoverlabel=dict(bgcolor="white"),
    )
    fig.update_yaxes(gridcolor="#EEF2F7", zerolinecolor="#CBD5E1", automargin=True)
    fig.update_xaxes(gridcolor="#EEF2F7", automargin=True)
    return fig


def kpi_row(items: list[tuple[str, str, str | None, str | None]]):
    """items: (label, value, delta, help_text). Delta may be None."""
    cols = st.columns(len(items))
    for col, (label, value, delta, help_text) in zip(cols, items):
        with col:
            st.metric(label, value, delta=delta, help=help_text)


def delta_str(current: float, previous: float | None, freq_noun: str, invert: bool = False) -> str | None:
    """Human delta vs prior period, e.g. '+12% vs last month'."""
    if previous is None or pd.isna(previous) or previous == 0:
        return None
    pct = (current - previous) / abs(previous) * 100
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.0f}% vs last {freq_noun}"


def explain(text: str):
    """Plain-English context box for non-finance owners."""
    st.markdown(
        f"""<div style="background:#F0F6FF;border-left:4px solid #2563EB;padding:.8rem 1rem;
        border-radius:0 8px 8px 0;margin:.4rem 0 1rem 0;color:#1E3A5F;font-size:.95rem;">
        💡 {text}</div>""",
        unsafe_allow_html=True,
    )


def insight_card(severity: str, title: str, detail: str, next_step: str):
    color = {"action": RED, "watch": AMBER, "good": GREEN}[severity]
    badge = {"action": "ACT NOW", "watch": "KEEP AN EYE ON", "good": "GOING WELL"}[severity]
    st.markdown(
        f"""<div style="border:1px solid #E2E8F0;border-left:6px solid {color};border-radius:10px;
        padding:1rem 1.2rem;margin-bottom:.9rem;background:white;box-shadow:0 1px 3px rgba(15,23,42,.06);">
        <div style="font-size:.72rem;font-weight:700;letter-spacing:.08em;color:{color};margin-bottom:.3rem;">{badge}</div>
        <div style="font-size:1.05rem;font-weight:700;color:#0F172A;margin-bottom:.4rem;">{title}</div>
        <div style="color:#334155;font-size:.93rem;margin-bottom:.55rem;">{detail}</div>
        <div style="color:#0F172A;font-size:.93rem;"><b>👉 Next step:</b> {next_step}</div>
        </div>""",
        unsafe_allow_html=True,
    )


def empty_state(what: str, needs: str):
    st.info(f"**No data for {what} yet.** Upload {needs} in the sidebar, or click *Load demo data* to explore.")
