"""Suggestions & Next Steps — the full advisory list."""

from __future__ import annotations

import streamlit as st

from .components import insight_card, explain


def render(ctx):
    st.title("Suggestions & Next Steps")
    st.caption(ctx.label)

    if not ctx.insights:
        st.info("Upload bank transactions (or load demo data) to generate suggestions.")
        return

    explain(
        "These are generated from this period's numbers and ranked by urgency: "
        "<b style='color:#EF4444'>red = act now</b>, <b style='color:#F59E0B'>amber = keep an eye on</b>, "
        "<b style='color:#10B981'>green = going well</b>. Use them as the agenda for the advisory call."
    )

    n_action = sum(1 for i in ctx.insights if i.severity == "action")
    n_watch = sum(1 for i in ctx.insights if i.severity == "watch")
    n_good = sum(1 for i in ctx.insights if i.severity == "good")
    c1, c2, c3 = st.columns(3)
    c1.metric("🔴 Act now", n_action)
    c2.metric("🟡 Watch", n_watch)
    c3.metric("🟢 Going well", n_good)
    st.divider()

    for ins in ctx.insights:
        insight_card(ins.severity, ins.title, ins.detail, ins.next_step)

    st.divider()
    st.subheader("Standing agenda for every review")
    st.markdown(
        """
1. **Cash first** — did we keep money this period, and how many months of cushion do we have?
2. **Top 3 expense moves** — pick the biggest categories and decide: keep, cut, or renegotiate.
3. **Advertising ROI** — cost per new client by platform; shift budget to what converts.
4. **Client profitability** — re-price or restructure anything under a 10% margin.
5. **Tax set-aside** — confirm the % of deposits moving to the tax account matches the estimate.
6. **One growth bet** — fund the best-margin service line or client profile with what we saved in #2–3.
        """
    )
