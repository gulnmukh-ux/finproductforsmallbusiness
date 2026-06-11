"""Per-client cost-of-service allocation.

The hard problem for small service businesses: staff and operating costs
overlap across clients with no clean breakdown. We use a standard
three-tier costing approach:

  1. Direct labor   — payroll/contractor cost allocated to clients by the
                      HOURS each person actually worked per client (from
                      attendance/timesheets). If no timesheets exist, falls
                      back to each client's share of revenue.
  2. Direct costs   — materials, subcontractors, supplies (categories in
                      DIRECT_COST_CATEGORIES) allocated by revenue share.
  3. Overhead       — everything else (rent, software, admin, insurance...)
                      allocated by the chosen driver: revenue share
                      (default), labor-hours share, or evenly per client.

Result: fully-loaded cost, profit and margin per client, plus a plain-
English note about which method was used so the advisor can defend the
numbers in front of the client.
"""

from __future__ import annotations

import pandas as pd

from .categorize import DIRECT_COST_CATEGORIES, OVERHEAD_CATEGORIES_EXCLUDE

OVERHEAD_METHODS = ["Revenue share (recommended)", "Labor hours share", "Split evenly"]


def _shares_from(series: pd.Series) -> pd.Series:
    total = series.sum()
    if total <= 0:
        return pd.Series(dtype=float)
    return series / total


def allocate_cost_of_service(
    sales: pd.DataFrame,
    bank: pd.DataFrame,
    payroll: pd.DataFrame | None,
    attendance: pd.DataFrame | None,
    overhead_method: str = OVERHEAD_METHODS[0],
) -> tuple[pd.DataFrame, list[str]]:
    """Return (per-client P&L DataFrame, methodology notes)."""
    notes: list[str] = []
    if sales is None or sales.empty:
        return pd.DataFrame(), ["Upload a sales/revenue sheet with client names to unlock per-client costing."]

    revenue = sales.groupby("client")["amount"].sum().rename("revenue")
    revenue = revenue[revenue > 0]
    if revenue.empty:
        return pd.DataFrame(), ["No positive revenue rows found in the sales data."]
    rev_share = _shares_from(revenue)
    clients = revenue.index

    # --- labor pool -------------------------------------------------------
    if payroll is not None and not payroll.empty:
        labor_pool = payroll["amount"].sum()
        labor_source = "the payroll sheet"
    else:
        labor_pool = -bank.loc[
            bank["category"].isin(["Payroll & Wages", "Contractors"]) & (bank["amount"] < 0), "amount"
        ].sum()
        labor_source = "payroll-related bank transactions"

    hours_share = None
    if attendance is not None and not attendance.empty:
        hours_by_client = attendance.groupby("client")["hours"].sum()
        hours_by_client = hours_by_client.reindex(clients).dropna()
        if hours_by_client.sum() > 0:
            hours_share = _shares_from(hours_by_client).reindex(clients).fillna(0)

    if hours_share is not None:
        labor_share = hours_share
        notes.append(
            f"**Direct labor** (${labor_pool:,.0f} from {labor_source}) was allocated by the hours "
            "each staff member logged per client in the attendance/timesheet data — the most accurate method."
        )
    else:
        labor_share = rev_share
        notes.append(
            f"**Direct labor** (${labor_pool:,.0f} from {labor_source}) was allocated by each client's share "
            "of revenue. Upload timesheets with a client column to switch to hours-based allocation."
        )

    # --- direct non-labor costs ------------------------------------------
    direct_pool = -bank.loc[
        bank["category"].isin(DIRECT_COST_CATEGORIES) & (bank["amount"] < 0), "amount"
    ].sum()
    notes.append(
        f"**Direct costs** (${direct_pool:,.0f}: materials, supplies, subcontractors) were allocated by revenue share."
    )

    # --- overhead ---------------------------------------------------------
    exclude = set(OVERHEAD_CATEGORIES_EXCLUDE) | set(DIRECT_COST_CATEGORIES) | {"Payroll & Wages", "Contractors", "Payroll Taxes"}
    overhead_pool = -bank.loc[
        (bank["amount"] < 0) & (bank["type"] == "Expense") & ~bank["category"].isin(exclude), "amount"
    ].sum()
    # payroll taxes ride along with labor
    ptax_pool = -bank.loc[bank["category"].eq("Payroll Taxes") & (bank["amount"] < 0), "amount"].sum()

    if overhead_method == "Labor hours share" and hours_share is not None:
        oh_share = hours_share
        notes.append(f"**Overhead** (${overhead_pool:,.0f}: rent, software, admin, insurance, etc.) was allocated by labor-hours share.")
    elif overhead_method == "Split evenly":
        oh_share = pd.Series(1 / len(clients), index=clients)
        notes.append(f"**Overhead** (${overhead_pool:,.0f}) was split evenly across {len(clients)} clients.")
    else:
        oh_share = rev_share
        notes.append(
            f"**Overhead** (${overhead_pool:,.0f}: rent, software, admin, insurance, etc.) was allocated by revenue "
            "share — the standard default when overhead supports all clients roughly in proportion to their size."
        )

    out = pd.DataFrame({"revenue": revenue})
    out["direct_labor"] = (labor_share * (labor_pool + ptax_pool)).reindex(clients).fillna(0)
    out["direct_costs"] = (rev_share * direct_pool).reindex(clients).fillna(0)
    out["overhead"] = (oh_share * overhead_pool).reindex(clients).fillna(0)
    out["total_cost"] = out[["direct_labor", "direct_costs", "overhead"]].sum(axis=1)
    out["profit"] = out["revenue"] - out["total_cost"]
    out["margin_pct"] = out["profit"] / out["revenue"] * 100
    out = out.sort_values("revenue", ascending=False).reset_index()
    return out, notes


def allocate_by_service_line(sales: pd.DataFrame, client_pnl: pd.DataFrame) -> pd.DataFrame:
    """Roll the per-client cost model up to service lines by revenue mix."""
    if sales is None or sales.empty or client_pnl.empty:
        return pd.DataFrame()
    mix = sales.groupby(["client", "service"])["amount"].sum().rename("svc_revenue").reset_index()
    merged = mix.merge(client_pnl, on="client", how="inner")
    merged["w"] = merged["svc_revenue"] / merged["revenue"]
    for col in ["direct_labor", "direct_costs", "overhead", "total_cost"]:
        merged[col] = merged[col] * merged["w"]
    svc = merged.groupby("service").agg(
        revenue=("svc_revenue", "sum"),
        direct_labor=("direct_labor", "sum"),
        direct_costs=("direct_costs", "sum"),
        overhead=("overhead", "sum"),
        total_cost=("total_cost", "sum"),
    ).reset_index()
    svc["profit"] = svc["revenue"] - svc["total_cost"]
    svc["margin_pct"] = svc["profit"] / svc["revenue"] * 100
    return svc.sort_values("revenue", ascending=False)
