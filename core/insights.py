"""Rule-based suggestions & next steps.

Every insight is written for an owner WITHOUT a finance background:
what we saw → why it matters → what to do next. Severity drives the
visual treatment: 'action' (red), 'watch' (amber), 'good' (green).
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class Insight:
    severity: str  # action | watch | good
    title: str
    detail: str
    next_step: str


def _money(x: float) -> str:
    return f"${x:,.0f}"


def generate_insights(
    bank_period: pd.DataFrame,
    bank_prev: pd.DataFrame,
    bank_all: pd.DataFrame,
    client_pnl: pd.DataFrame | None,
    freq_noun: str,
    tax_rate: float = 0.25,
) -> list[Insight]:
    out: list[Insight] = []
    if bank_period is None or bank_period.empty:
        return out

    exp = bank_period[(bank_period["type"] == "Expense") & (bank_period["amount"] < 0)]
    inc = bank_period[bank_period["type"] == "Income"]
    revenue = inc["amount"].sum()
    spend = -exp["amount"].sum()
    net = revenue - spend

    prev_exp = bank_prev[(bank_prev["type"] == "Expense") & (bank_prev["amount"] < 0)] if bank_prev is not None and not bank_prev.empty else pd.DataFrame(columns=bank_period.columns)
    prev_revenue = bank_prev[bank_prev["type"] == "Income"]["amount"].sum() if not prev_exp.empty or (bank_prev is not None and not bank_prev.empty) else 0.0

    # --- cash position / runway -------------------------------------------
    if net < 0:
        months_data = bank_all.assign(m=pd.to_datetime(bank_all["date"]).dt.to_period("M"))
        burn = months_data.groupby("m")["amount"].sum()
        avg_burn = burn.tail(3).mean()
        if avg_burn < 0:
            out.append(Insight(
                "action",
                f"More money went out than came in this {freq_noun}",
                f"You spent {_money(abs(net))} more than you brought in. Over the last 3 months the business "
                f"has been losing about {_money(abs(avg_burn))} per month on average.",
                "Decide which of the three biggest expense categories below can be cut 10–15% this month, "
                "and review pricing — a small price increase often closes this gap fastest.",
            ))
        else:
            out.append(Insight(
                "watch",
                f"Cash flow was negative this {freq_noun}",
                f"Outflows exceeded inflows by {_money(abs(net))}. This can be normal (e.g., a large one-time "
                "payment), but it's worth confirming it isn't a trend.",
                "Check whether a one-time expense caused this; if not, revisit the spending plan for next "
                f"{freq_noun}.",
            ))
    else:
        out.append(Insight(
            "good",
            f"You kept {_money(net)} of the {_money(revenue)} that came in",
            f"That's a {net / revenue * 100:.0f}% cash margin this {freq_noun}." if revenue else "Positive cash flow.",
            "Consider moving a fixed percentage of this surplus into a tax set-aside account and a reserve fund.",
        ))

    # --- advertising -------------------------------------------------------
    ads = exp[exp["category"] == "Advertising & Marketing"]
    ad_spend = -ads["amount"].sum()
    if ad_spend > 0 and revenue > 0:
        ad_pct = ad_spend / revenue * 100
        top_ad = ads.groupby("vendor")["amount"].sum().sort_values()
        top_name, top_amt = (top_ad.index[0], -top_ad.iloc[0]) if len(top_ad) else ("", 0)
        prev_ads = -prev_exp[prev_exp["category"] == "Advertising & Marketing"]["amount"].sum() if not prev_exp.empty else 0
        if ad_pct > 20:
            out.append(Insight(
                "action",
                f"Advertising is eating {ad_pct:.0f}¢ of every revenue dollar",
                f"You spent {_money(ad_spend)} on ads against {_money(revenue)} of income. Your largest ad "
                f"vendor is {top_name} at {_money(top_amt)}. Healthy service businesses usually keep this at 5–15%.",
                f"Ask {top_name} (or your agency) for a cost-per-new-client report. Pause the worst-performing "
                "campaign for 30 days and watch whether new-client volume actually drops.",
            ))
        elif ad_pct > 12:
            out.append(Insight(
                "watch",
                f"Advertising is {ad_pct:.0f}% of revenue — on the high side",
                f"{_money(ad_spend)} went to ads this {freq_noun}, led by {top_name} ({_money(top_amt)}).",
                "Start tracking which platform each new client came from so next quarter we can cut the "
                "channels that don't convert.",
            ))
        if prev_ads > 0 and ad_spend > prev_ads * 1.25 and prev_revenue > 0 and revenue < prev_revenue * 1.05:
            out.append(Insight(
                "action",
                "Ad spend jumped but revenue didn't follow",
                f"Advertising rose from {_money(prev_ads)} to {_money(ad_spend)} (+{(ad_spend / prev_ads - 1) * 100:.0f}%) "
                f"while revenue stayed roughly flat ({_money(prev_revenue)} → {_money(revenue)}).",
                "Freeze ad budgets at last period's level until we can attribute new clients to specific campaigns.",
            ))

    # --- payroll -----------------------------------------------------------
    payroll_spend = -exp[exp["category"].isin(["Payroll & Wages", "Contractors", "Payroll Taxes"])]["amount"].sum()
    if payroll_spend > 0 and revenue > 0:
        pp = payroll_spend / revenue * 100
        if pp > 50:
            out.append(Insight(
                "action",
                f"People costs are {pp:.0f}% of revenue",
                f"Payroll, contractors and payroll taxes totaled {_money(payroll_spend)} against {_money(revenue)} "
                "of income. Above ~50%, most service businesses struggle to be profitable.",
                "Review the per-client cost page: identify which clients or service lines don't cover the staff "
                "time they consume, then re-price or restructure those first.",
            ))
        elif pp > 40:
            out.append(Insight(
                "watch",
                f"People costs are {pp:.0f}% of revenue",
                f"{_money(payroll_spend)} this {freq_noun}. The comfortable zone for service businesses is 30–45%.",
                "Before the next hire, check utilization — can existing staff absorb more billable work?",
            ))

    # --- vendor concentration ----------------------------------------------
    # exclude payroll processors & taxes — they pass money through, you don't
    # negotiate with them the way you do a true vendor
    negotiable = exp[~exp["category"].isin(["Payroll & Wages", "Payroll Taxes", "Income Taxes"])]
    by_vendor = negotiable.groupby("vendor")["amount"].sum().abs().sort_values(ascending=False)
    neg_spend = -negotiable["amount"].sum()
    if len(by_vendor) >= 3 and neg_spend > 0:
        top_v, top_amt = by_vendor.index[0], by_vendor.iloc[0]
        if top_amt / neg_spend > 0.25 and top_v not in ("Unknown",):
            out.append(Insight(
                "watch",
                f"A quarter of non-payroll spending goes to one vendor: {top_v}",
                f"{_money(top_amt)} of {_money(neg_spend)} non-payroll spend ({top_amt / neg_spend * 100:.0f}%).",
                f"Schedule an annual pricing review with {top_v} — vendors this large usually have room to "
                "negotiate, and you should have a backup option identified.",
            ))

    # --- client concentration & margins -------------------------------------
    if client_pnl is not None and not client_pnl.empty:
        total_rev = client_pnl["revenue"].sum()
        top = client_pnl.iloc[0]
        if total_rev > 0 and top["revenue"] / total_rev > 0.30:
            out.append(Insight(
                "watch",
                f"{top['client']} is {top['revenue'] / total_rev * 100:.0f}% of your revenue",
                "If this client left, it would take a large bite out of the business overnight.",
                "Make retention of this client a standing agenda item, and set a goal to grow two mid-size "
                "clients so no single client exceeds ~25% of revenue.",
            ))
        losers = client_pnl[client_pnl["margin_pct"] < 10]
        if not losers.empty:
            names = ", ".join(losers["client"].head(3))
            out.append(Insight(
                "action",
                f"{len(losers)} client(s) earn you less than a 10% margin",
                f"After assigning staff time and a fair share of overhead, {names} barely cover (or don't cover) "
                "their cost of service.",
                "For each: raise price, reduce the service hours included, or move them to a lighter service "
                "tier. A 10–15% price adjustment on unprofitable clients rarely causes churn.",
            ))
        winners = client_pnl[client_pnl["margin_pct"] > 40]
        if not winners.empty:
            out.append(Insight(
                "good",
                f"Your most profitable client profile: {winners.iloc[0]['client']}",
                f"{len(winners)} client(s) deliver margins above 40%. These are the clients your marketing "
                "should be cloning.",
                "Write down what these clients have in common (service mix, size, how they found you) and "
                "point next quarter's ad budget at that profile.",
            ))

    # --- taxes ---------------------------------------------------------------
    ytd = bank_all[pd.to_datetime(bank_all["date"]).dt.year == pd.to_datetime(bank_all["date"]).dt.year.max()]
    ytd_net = ytd[ytd["type"] == "Income"]["amount"].sum() + ytd[ytd["type"] == "Expense"]["amount"].sum()
    tax_paid = -ytd[ytd["category"].isin(["Income Taxes"])]["amount"].sum()
    if ytd_net > 0:
        est_tax = ytd_net * tax_rate
        if tax_paid < est_tax * 0.6:
            out.append(Insight(
                "action",
                f"Estimated taxes look underfunded by roughly {_money(est_tax - tax_paid)}",
                f"Year-to-date profit is about {_money(ytd_net)}. At an assumed {tax_rate * 100:.0f}% effective rate, "
                f"that's ~{_money(est_tax)} of tax, but only {_money(tax_paid)} in tax payments shows in the bank data.",
                "Open a separate tax savings account and auto-transfer a fixed % of every deposit. See the "
                "Taxes page for the quarterly payment schedule.",
            ))

    # --- uncategorized hygiene ----------------------------------------------
    uncat = bank_period[bank_period["category"] == "Uncategorized"]
    if len(uncat) > 0 and spend > 0:
        u_amt = -uncat[uncat["amount"] < 0]["amount"].sum()
        if u_amt / max(spend, 1) > 0.05:
            out.append(Insight(
                "watch",
                f"{_money(u_amt)} of spending isn't categorized yet",
                f"{len(uncat)} transactions couldn't be auto-classified, so every chart on this dashboard is "
                "slightly understated.",
                "Open the Data Review screen and assign categories — it takes a few minutes and sharpens "
                "every number here.",
            ))

    order = {"action": 0, "watch": 1, "good": 2}
    out.sort(key=lambda i: order[i.severity])
    return out
