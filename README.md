# 📊 CFO Advisory Dashboard

A presentation-ready financial dashboard for CFO advisors serving small businesses
($500K–$3M/year). Upload a client's raw files, pick a period, and walk them through
their numbers in plain English — cash flow, where the money went, advertising ROI,
per-client cost of service, tax readiness, and concrete next steps.

## Quick start

```bash
pip install -r requirements.txt
streamlit run app.py
```

Then click **🎬 Load demo data** in the sidebar to explore with a realistic sample
business before uploading real client files.

## What it does

| Page | Answers the client's question |
|---|---|
| **Executive Overview** | "How are we doing?" — KPIs, money in vs out, top 3 priorities, one-click Excel report |
| **Cash Flow** | "Did the bank account grow or shrink, and why?" — waterfall, net flow trend, runway/cushion check |
| **Where the Money Went** | "Where did it all go?" — interactive spending map by category → vendor, trends, vendor table |
| **Advertising** | "Which ad vendor do we pay the most — and is it working?" — per-platform spend, revenue per ad dollar, cost per new sign-up |
| **People** | "What does our team cost?" — employee vs contractor split, pay per person, % of revenue, cost per client-hour |
| **Revenue & Service Lines** | "What sells?" — service line mix, top clients, enrollment/admissions funnel |
| **Cost of Service per Client** | "Which clients actually make us money?" — fully-loaded cost & margin per client (see methodology below) |
| **Taxes** | "Are we ready for tax time?" — estimated set-aside, funding gauge, quarterly calendar, deductible spending |
| **Suggestions & Next Steps** | "What should we do?" — auto-generated, prioritized findings with concrete next steps |
| **Data Review & Fix-ups** | Fix auto-categorization, catch duplicates, handle unrecognized sheets |

All pages support **weekly, monthly, quarterly and yearly** reporting with
prior-period comparison.

## Files it accepts

**Bank transactions** (CSV or Excel) — any bank or QuickBooks export. Columns are
auto-detected: date, description/memo/payee, and either a signed amount or
debit/credit pair. Transactions are auto-categorized (advertising platforms,
payroll processors, rent, software, fees, taxes…) and every category is editable.

**Client workbooks** (Excel) — sheets are auto-classified by name and structure:

| Sheet kind | Typical columns | Unlocks |
|---|---|---|
| Sales / Revenue / Invoices | date, client, service, amount | Service-line revenue, per-client costing |
| Payroll / Salaries | date, name, type (W-2/1099), role, amount | People page detail, labor allocation |
| Commission | date, name, amount | Commission tracking |
| Attendance / Timesheets | date, name, client, hours | Hours-based cost allocation, utilization |
| Enrollment / Admissions | date, client, program, status | Funnel, cost per new sign-up |

## Per-client cost-of-service methodology

The hardest question for service businesses — *"what does each client really cost
us?"* — is answered with a standard three-tier allocation:

1. **Direct labor** — payroll + payroll taxes, allocated by the **hours each staff
   member actually worked per client** (from timesheets). Falls back to revenue
   share when no timesheets exist.
2. **Direct costs** — materials, supplies, subcontractors, allocated by revenue share.
3. **Overhead** — rent, software, insurance, admin…, allocated by a selectable
   driver: revenue share (default), labor-hours share, or even split.

Owner draws, transfers and income taxes are excluded — they're not costs of serving
clients. The dashboard shows its work: a methodology panel explains every allocation
in client-friendly language.

## Project layout

```
app.py                 # entry point: uploads, period controls, navigation
core/
  ingest.py            # tolerant parsing of bank exports & client workbooks
  categorize.py        # rule-based categorization + ad-vendor detection
  periods.py           # weekly/monthly/quarterly/yearly logic
  allocation.py        # per-client cost-of-service model
  insights.py          # suggestions & next-steps engine
  export.py            # Excel leave-behind report
  sample_data.py       # realistic demo business
views/                 # one module per report page + shared components
```

## Notes

- Data lives only in the browser session — nothing is written to disk or sent anywhere.
- Tax figures are cash-basis planning estimates, not tax advice.
- To present to a client remotely, deploy free on [Streamlit Community Cloud](https://streamlit.io/cloud)
  or run locally and share your screen.
