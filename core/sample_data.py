"""Realistic demo dataset: 'Brightpath Learning Center', a ~$1.4M/yr
tutoring & test-prep business with heavy ad spend — representative of the
$500K–$3M service businesses this dashboard targets. Lets the advisor demo
the full dashboard before any client files are uploaded.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

RNG = np.random.default_rng(42)

CLIENTS = [
    ("Harrison Family", 1.6), ("Nguyen Family", 1.4), ("Lakeside School District", 3.2),
    ("Patel Family", 1.1), ("Kim Family", 1.0), ("Romero Family", 0.9),
    ("Westview Academy", 2.1), ("Chen Family", 0.8), ("Okafor Family", 0.7),
    ("Brooks Family", 0.6), ("Silva Family", 0.55), ("Thompson Family", 0.5),
]
SERVICES = {
    "1:1 Tutoring": 0.40, "SAT/ACT Test Prep": 0.27, "After-School Program": 0.20,
    "Enrollment & Assessment Fees": 0.08, "Summer Intensive": 0.05,
}
STAFF = [
    ("Maria Gonzalez", "Employee", "Lead Tutor", 6800),
    ("James Carter", "Employee", "Tutor", 5600),
    ("Aisha Bell", "Employee", "Tutor", 5200),
    ("Tom Reilly", "Employee", "Center Manager", 7200),
    ("Dana Liu", "Employee", "Admin/Front Desk", 4100),
    ("Kevin Park", "Contractor", "SAT Specialist", 5200),
    ("Sofia Marin", "Contractor", "Weekend Tutor", 3100),
    ("Raj Mehta", "Contractor", "Math Specialist", 3600),
]
AD_VENDORS = {
    "GOOGLE ADS G.CO/HELPPAY#": 5200, "META PLATFORMS FACEBK *ADS": 3100,
    "YELP ADVERTISING": 950, "TIKTOK ADS": 700, "NEXTDOOR ADS": 320, "MAILCHIMP": 180,
}
RECURRING_EXPENSES = [
    ("OAKWOOD PROPERTY MANAGEMENT RENT", 7800, 1),
    ("GUSTO PAYROLL 240118 PPD", None, 15),       # filled from payroll
    ("GUSTO PAYROLL 240118 PPD ", None, 30),
    ("EFTPS PAYROLL TAX 941", 3650, 16),
    ("NEXT INSURANCE LIABILITY", 410, 3),
    ("COMCAST BUSINESS INTERNET", 240, 7),
    ("PG&E UTILITY PAYMENT", 520, 11),
    ("INTUIT QUICKBOOKS ONLINE", 90, 5),
    ("ZOOM.US SUBSCRIPTION", 150, 5),
    ("CANVA SUBSCRIPTION", 45, 9),
    ("CALENDLY SUBSCRIPTION", 72, 9),
    ("GOOGLE WORKSPACE GSUITE", 144, 12),
    ("CURRICULUM ASSOCIATES MATERIALS", 1400, 18),
    ("AMZN MKTP US SUPPLIES", 380, None),          # random day
    ("STAPLES OFFICE SUPPLIES", 160, None),
    ("STRIPE FEE", 310, 28),
    ("BANK MONTHLY FEE SERVICE CHARGE", 35, 27),
    ("HARTFORD WORKERS COMP", 520, 20),
    ("SHELL OIL GAS STATION", 90, None),
    ("DOORDASH STAFF LUNCH", 120, None),
    ("UDEMY TUTOR TRAINING", 60, None),
]


def generate(months: int = 18, end: str | None = None) -> dict[str, pd.DataFrame]:
    end_ts = pd.Timestamp(end) if end else pd.Timestamp.today().normalize()
    month_starts = pd.date_range(end=end_ts, periods=months, freq="MS")

    sales_rows, bank_rows, payroll_rows, att_rows, enroll_rows, comm_rows = [], [], [], [], [], []

    for i, m in enumerate(month_starts):
        season = 1.0 + 0.25 * np.sin((m.month - 3) / 12 * 2 * np.pi)  # busy spring/fall
        growth = 1.0 + 0.012 * i
        base_rev = 88_000 * season * growth

        # --- sales by client x service ---
        for client, weight in CLIENTS:
            c_rev = base_rev * weight / sum(w for _, w in CLIENTS)
            for svc, share in SERVICES.items():
                amt = c_rev * share * RNG.uniform(0.8, 1.2)
                if amt < 50:
                    continue
                day = int(RNG.integers(2, 27))
                sales_rows.append((m + pd.Timedelta(days=day), client, svc, round(amt, 2)))

        # --- payroll & commissions ---
        for name, wtype, role, monthly in STAFF:
            amt = monthly * RNG.uniform(0.95, 1.08)
            payroll_rows.append((m + pd.Timedelta(days=14), name, wtype, role, round(amt / 2, 2)))
            payroll_rows.append((m + pd.Timedelta(days=27), name, wtype, role, round(amt / 2, 2)))
            if role in ("Center Manager", "SAT Specialist"):
                comm_rows.append((m + pd.Timedelta(days=27), name, round(base_rev * 0.004 * RNG.uniform(0.7, 1.3), 2)))

        # --- attendance: tutors' hours by client (drives labor allocation) ---
        for name, wtype, role, _ in STAFF:
            if "Tutor" not in role and "Specialist" not in role:
                continue
            total_hours = RNG.uniform(110, 150)
            # small clients consume disproportionate staff time (sqrt flattens
            # the revenue weights) — this is what makes some clients unprofitable
            weights = np.array([w for _, w in CLIENTS]) ** 0.45 * RNG.uniform(0.8, 1.25, len(CLIENTS))
            weights /= weights.sum()
            for (client, _), w in zip(CLIENTS, weights):
                h = round(float(total_hours * w), 1)
                if h >= 1:
                    att_rows.append((m + pd.Timedelta(days=int(RNG.integers(1, 28))), name, client, h))

        # --- enrollment funnel ---
        n_new = int(RNG.poisson(6 * season))
        for k in range(n_new):
            status = RNG.choice(["Enrolled", "Enrolled", "Enrolled", "Trial", "Withdrawn"])
            prog = RNG.choice(list(SERVICES.keys())[:3])
            enroll_rows.append((m + pd.Timedelta(days=int(RNG.integers(1, 28))), f"New Family {i:02d}-{k}", prog, status))

        # --- bank: income deposits (weekly Stripe batches) ---
        month_revenue = sum(r[3] for r in sales_rows if r[0].to_period("M") == m.to_period("M"))
        for wk in range(4):
            dep = month_revenue / 4 * RNG.uniform(0.85, 1.15)
            bank_rows.append((m + pd.Timedelta(days=2 + 7 * wk), "STRIPE TRANSFER ST-PAYOUT CLIENT PAYMENTS", round(dep, 2)))

        # --- bank: ad spend (gently rising) ---
        for vendor, base in AD_VENDORS.items():
            amt = base * RNG.uniform(0.85, 1.2) * (1 + 0.02 * i)
            bank_rows.append((m + pd.Timedelta(days=int(RNG.integers(3, 25))), vendor, -round(amt, 2)))

        # --- bank: payroll outflow mirrors payroll sheet ---
        month_pay = sum(r[4] for r in payroll_rows if r[0].to_period("M") == m.to_period("M"))
        bank_rows.append((m + pd.Timedelta(days=15), "GUSTO PAYROLL 240118 PPD", -round(month_pay / 2, 2)))
        bank_rows.append((m + pd.Timedelta(days=28), "GUSTO PAYROLL 240118 PPD", -round(month_pay / 2, 2)))

        # --- bank: recurring expenses ---
        for desc, amt, day in RECURRING_EXPENSES:
            if amt is None:
                continue
            d = day if day else int(RNG.integers(2, 27))
            bank_rows.append((m + pd.Timedelta(days=d - 1), desc, -round(amt * RNG.uniform(0.9, 1.12), 2)))

        # --- owner draw & quarterly estimated taxes ---
        bank_rows.append((m + pd.Timedelta(days=25), "OWNER DRAW TRANSFER TO PERSONAL", -6000.0))
        if m.month in (1, 4, 6, 9):
            bank_rows.append((m + pd.Timedelta(days=13), "IRS USATAXPYMT ESTIMATED TAX", -round(7200 * RNG.uniform(0.9, 1.1), 2)))

    bank = pd.DataFrame(bank_rows, columns=["date", "description", "amount"]).sort_values("date").reset_index(drop=True)
    return {
        "bank": bank,
        "sales": pd.DataFrame(sales_rows, columns=["date", "client", "service", "amount"]),
        "payroll": pd.DataFrame(payroll_rows, columns=["date", "name", "worker_type", "role", "amount"]),
        "attendance": pd.DataFrame(att_rows, columns=["date", "name", "client", "hours"]),
        "enrollment": pd.DataFrame(enroll_rows, columns=["date", "client", "program", "status"]),
        "commission": pd.DataFrame(comm_rows, columns=["date", "name", "amount"]),
    }
