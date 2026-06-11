"""Excel report export — a leave-behind workbook for the client."""

from __future__ import annotations

import io

import pandas as pd


def build_excel_report(
    period_label: str,
    bank_period: pd.DataFrame,
    sales_period: pd.DataFrame | None,
    client_pnl: pd.DataFrame | None,
    insights: list,
) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as xw:
        money = xw.book.add_format({"num_format": "$#,##0"})
        bold = xw.book.add_format({"bold": True, "font_size": 12})

        inc = bank_period[bank_period["type"] == "Income"]["amount"].sum()
        exp = -bank_period[(bank_period["type"] == "Expense") & (bank_period["amount"] < 0)]["amount"].sum()
        summary = pd.DataFrame({
            "Metric": ["Period", "Money In", "Money Out", "Net Cash Flow"],
            "Value": [period_label, round(inc), round(exp), round(inc - exp)],
        })
        summary.to_excel(xw, sheet_name="Summary", index=False)
        xw.sheets["Summary"].set_column("A:A", 24, bold)
        xw.sheets["Summary"].set_column("B:B", 22)

        cat = (
            bank_period[(bank_period["type"] == "Expense") & (bank_period["amount"] < 0)]
            .groupby("category")["amount"].sum().abs().sort_values(ascending=False)
            .rename("Spent").reset_index()
        )
        cat.to_excel(xw, sheet_name="Expenses by Category", index=False)
        xw.sheets["Expenses by Category"].set_column("A:A", 32)
        xw.sheets["Expenses by Category"].set_column("B:B", 16, money)

        ven = (
            bank_period[(bank_period["type"] == "Expense") & (bank_period["amount"] < 0)]
            .groupby(["vendor", "category"])["amount"].sum().abs().sort_values(ascending=False)
            .rename("Spent").reset_index().head(50)
        )
        ven.to_excel(xw, sheet_name="Top Vendors", index=False)
        xw.sheets["Top Vendors"].set_column("A:B", 30)
        xw.sheets["Top Vendors"].set_column("C:C", 16, money)

        if sales_period is not None and not sales_period.empty:
            svc = sales_period.groupby("service")["amount"].sum().sort_values(ascending=False).rename("Revenue").reset_index()
            svc.to_excel(xw, sheet_name="Revenue by Service", index=False)
            xw.sheets["Revenue by Service"].set_column("A:A", 32)
            xw.sheets["Revenue by Service"].set_column("B:B", 16, money)

        if client_pnl is not None and not client_pnl.empty:
            pnl = client_pnl.rename(columns={
                "client": "Client", "revenue": "Revenue", "direct_labor": "Direct Labor",
                "direct_costs": "Direct Costs", "overhead": "Overhead Share",
                "total_cost": "Total Cost", "profit": "Profit", "margin_pct": "Margin %",
            }).round({"Margin %": 1})
            pnl.to_excel(xw, sheet_name="Per-Client Profitability", index=False)
            ws = xw.sheets["Per-Client Profitability"]
            ws.set_column("A:A", 28)
            ws.set_column("B:G", 14, money)
            ws.set_column("H:H", 10)

        if insights:
            ins = pd.DataFrame(
                [(i.severity.title(), i.title, i.detail, i.next_step) for i in insights],
                columns=["Priority", "Finding", "Detail", "Recommended Next Step"],
            )
            ins.to_excel(xw, sheet_name="Suggestions", index=False)
            wrap = xw.book.add_format({"text_wrap": True, "valign": "top"})
            xw.sheets["Suggestions"].set_column("A:A", 10)
            xw.sheets["Suggestions"].set_column("B:B", 40, wrap)
            xw.sheets["Suggestions"].set_column("C:D", 60, wrap)

        raw = bank_period[["date", "description", "vendor", "category", "amount"]].copy()
        raw["date"] = pd.to_datetime(raw["date"]).dt.date
        raw.to_excel(xw, sheet_name="Transactions", index=False)
        xw.sheets["Transactions"].set_column("A:A", 12)
        xw.sheets["Transactions"].set_column("B:B", 48)
        xw.sheets["Transactions"].set_column("C:D", 28)
        xw.sheets["Transactions"].set_column("E:E", 14, money)

    return buf.getvalue()
