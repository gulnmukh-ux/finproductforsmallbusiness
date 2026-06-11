"""Flexible ingestion of bank exports and client Excel workbooks.

Real-world client files are messy: column names vary by bank/bookkeeper,
amounts come signed or as debit/credit pairs, and Excel workbooks mix
sales, payroll, attendance and enrollment sheets. Everything here is
heuristic-based so the advisor doesn't have to reformat files first.
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Column-name heuristics
# ---------------------------------------------------------------------------

DATE_CANDIDATES = [
    "date", "transaction date", "trans date", "posting date", "post date",
    "posted date", "value date", "completed date", "pay date", "period",
    "week", "month", "invoice date", "payment date",
]
DESC_CANDIDATES = [
    "description", "memo", "payee", "details", "transaction", "narrative",
    "name", "merchant", "reference", "transaction description",
]
AMOUNT_CANDIDATES = [
    "amount", "transaction amount", "amt", "total", "value", "amount (usd)",
    "gross", "net amount", "payment", "paid", "price", "revenue", "sales",
]
DEBIT_CANDIDATES = ["debit", "withdrawal", "withdrawals", "money out", "outflow", "paid out", "charge"]
CREDIT_CANDIDATES = ["credit", "deposit", "deposits", "money in", "inflow", "paid in"]

CLIENT_CANDIDATES = ["client", "customer", "student", "account", "patient", "member", "family", "client name", "customer name"]
SERVICE_CANDIDATES = ["service", "service line", "program", "product", "item", "category", "class", "course", "department", "type"]
PERSON_CANDIDATES = ["employee", "name", "staff", "worker", "contractor", "team member", "person", "payee", "employee name"]
HOURS_CANDIDATES = ["hours", "hrs", "time", "hours worked", "duration", "billable hours"]
WORKER_TYPE_CANDIDATES = ["type", "worker type", "employment type", "classification", "status", "role type", "w21099", "w2 1099"]
STATUS_CANDIDATES = ["status", "enrollment status", "stage", "state"]


def _norm(col: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", str(col).strip().lower())


def _find_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    """Return the original column name best matching the candidate list."""
    normed = {_norm(c): c for c in df.columns}
    for cand in candidates:  # exact match first, in priority order
        if cand in normed:
            return normed[cand]
    for cand in candidates:  # then substring match
        for n, orig in normed.items():
            if cand in n:
                return orig
    return None


def _clean_amount(series: pd.Series) -> pd.Series:
    """Parse '$1,234.56', '(500.00)', '1.234,56'-style values to floats."""
    if pd.api.types.is_numeric_dtype(series):
        return series.astype(float)
    s = series.astype(str).str.strip()
    neg = s.str.match(r"^\(.*\)$") | s.str.startswith("-")
    s = s.str.replace(r"[()$,€£\s]", "", regex=True).str.replace("−", "-", regex=False)
    out = pd.to_numeric(s, errors="coerce").abs()
    return out * np.where(neg, -1.0, 1.0)


def _read_any(file) -> dict[str, pd.DataFrame]:
    """Read a CSV or Excel upload into {sheet_name: DataFrame}."""
    name = getattr(file, "name", str(file)).lower()
    if name.endswith((".xlsx", ".xls", ".xlsm")):
        return pd.read_excel(file, sheet_name=None)
    # real bank CSVs are often ragged or oddly quoted — try strict, then
    # progressively more forgiving parsers
    attempts = [
        dict(),
        dict(encoding="latin-1"),
        dict(engine="python", skipinitialspace=True, on_bad_lines="skip"),
        dict(engine="python", skipinitialspace=True, on_bad_lines="skip", encoding="latin-1"),
    ]
    last_err: Exception | None = None
    for kwargs in attempts:
        try:
            file.seek(0)
            return {"data": pd.read_csv(file, **kwargs)}
        except Exception as e:  # noqa: BLE001 - we surface the last error below
            last_err = e
    raise ValueError(f"Could not read this CSV file: {last_err}")


# ---------------------------------------------------------------------------
# Bank transactions
# ---------------------------------------------------------------------------

def parse_bank_file(file) -> pd.DataFrame:
    """Normalize a bank export to columns: date, description, amount.

    Positive amount = money in, negative = money out.
    """
    frames = []
    for _, raw in _read_any(file).items():
        if raw.empty:
            continue
        raw = raw.dropna(how="all").dropna(axis=1, how="all")
        date_col = _find_col(raw, DATE_CANDIDATES)
        desc_col = _find_col(raw, DESC_CANDIDATES)
        amt_col = _find_col(raw, AMOUNT_CANDIDATES)
        debit_col = _find_col(raw, DEBIT_CANDIDATES)
        credit_col = _find_col(raw, CREDIT_CANDIDATES)
        if date_col is None or (amt_col is None and debit_col is None and credit_col is None):
            continue

        df = pd.DataFrame()
        df["date"] = pd.to_datetime(raw[date_col], errors="coerce")
        df["description"] = raw[desc_col].astype(str).str.strip() if desc_col else ""
        if amt_col is not None:
            df["amount"] = _clean_amount(raw[amt_col])
        else:
            debit = _clean_amount(raw[debit_col]).fillna(0).abs() if debit_col else 0.0
            credit = _clean_amount(raw[credit_col]).fillna(0).abs() if credit_col else 0.0
            df["amount"] = credit - debit
        df = df.dropna(subset=["date", "amount"])
        df = df[df["amount"] != 0]
        frames.append(df)

    if not frames:
        raise ValueError(
            "Could not find date and amount columns in this file. "
            "Expected something like Date / Description / Amount (or Debit & Credit)."
        )
    out = pd.concat(frames, ignore_index=True).sort_values("date").reset_index(drop=True)
    return out


# ---------------------------------------------------------------------------
# Client operational workbooks (sales, payroll, attendance, enrollment...)
# ---------------------------------------------------------------------------

SHEET_KIND_KEYWORDS = {
    "sales": ["sales", "revenue", "invoice", "income", "billing", "collections"],
    "commission": ["commission", "commissions", "bonus"],
    "payroll": ["payroll", "salary", "salaries", "wages", "compensation", "pay"],
    "attendance": ["attendance", "hours", "timesheet", "time sheet", "schedule", "sessions"],
    "enrollment": ["enrollment", "enrolment", "admission", "admissions", "intake", "signups", "leads", "students", "clients"],
}


def _classify_sheet(sheet_name: str, df: pd.DataFrame) -> str | None:
    n = _norm(sheet_name)
    for kind, kws in SHEET_KIND_KEYWORDS.items():
        if any(kw in n for kw in kws):
            return kind
    # fall back to column shape
    if _find_col(df, HOURS_CANDIDATES) and _find_col(df, PERSON_CANDIDATES):
        return "attendance"
    if _find_col(df, SERVICE_CANDIDATES) and _find_col(df, AMOUNT_CANDIDATES):
        return "sales"
    if _find_col(df, PERSON_CANDIDATES) and _find_col(df, AMOUNT_CANDIDATES):
        return "payroll"
    if _find_col(df, STATUS_CANDIDATES) and _find_col(df, CLIENT_CANDIDATES):
        return "enrollment"
    return None


def _normalize_sales(raw: pd.DataFrame) -> pd.DataFrame:
    df = pd.DataFrame()
    date_col = _find_col(raw, DATE_CANDIDATES)
    df["date"] = pd.to_datetime(raw[date_col], errors="coerce") if date_col else pd.NaT
    client_col = _find_col(raw, CLIENT_CANDIDATES)
    df["client"] = raw[client_col].astype(str).str.strip() if client_col else "Unassigned"
    svc_col = _find_col(raw, SERVICE_CANDIDATES)
    df["service"] = raw[svc_col].astype(str).str.strip() if svc_col else "General"
    amt_col = _find_col(raw, AMOUNT_CANDIDATES)
    df["amount"] = _clean_amount(raw[amt_col]) if amt_col else np.nan
    return df.dropna(subset=["amount"]).query("amount != 0")


def _normalize_payroll(raw: pd.DataFrame) -> pd.DataFrame:
    df = pd.DataFrame()
    date_col = _find_col(raw, DATE_CANDIDATES)
    df["date"] = pd.to_datetime(raw[date_col], errors="coerce") if date_col else pd.NaT
    person_col = _find_col(raw, PERSON_CANDIDATES)
    df["name"] = raw[person_col].astype(str).str.strip() if person_col else "Unknown"
    type_col = _find_col(raw, WORKER_TYPE_CANDIDATES)
    if type_col:
        t = raw[type_col].astype(str).str.lower()
        df["worker_type"] = np.where(
            t.str.contains("1099|contract|freelan|vendor", regex=True), "Contractor", "Employee"
        )
    else:
        df["worker_type"] = "Employee"
    role_col = _find_col(raw, ["role", "position", "title", "department", "job"])
    df["role"] = raw[role_col].astype(str).str.strip() if role_col else ""
    amt_col = _find_col(raw, ["gross pay", "gross", "salary", "wages", "amount", "total pay", "pay", "total"])
    df["amount"] = _clean_amount(raw[amt_col]) if amt_col else np.nan
    return df.dropna(subset=["amount"]).query("amount != 0")


def _normalize_attendance(raw: pd.DataFrame) -> pd.DataFrame:
    df = pd.DataFrame()
    date_col = _find_col(raw, DATE_CANDIDATES)
    df["date"] = pd.to_datetime(raw[date_col], errors="coerce") if date_col else pd.NaT
    person_col = _find_col(raw, PERSON_CANDIDATES)
    df["name"] = raw[person_col].astype(str).str.strip() if person_col else "Unknown"
    client_col = _find_col(raw, CLIENT_CANDIDATES)
    df["client"] = raw[client_col].astype(str).str.strip() if client_col else "Unassigned"
    hours_col = _find_col(raw, HOURS_CANDIDATES)
    df["hours"] = pd.to_numeric(raw[hours_col], errors="coerce") if hours_col else np.nan
    return df.dropna(subset=["hours"]).query("hours > 0")


def _normalize_enrollment(raw: pd.DataFrame) -> pd.DataFrame:
    df = pd.DataFrame()
    date_col = _find_col(raw, DATE_CANDIDATES)
    df["date"] = pd.to_datetime(raw[date_col], errors="coerce") if date_col else pd.NaT
    client_col = _find_col(raw, CLIENT_CANDIDATES)
    df["client"] = raw[client_col].astype(str).str.strip() if client_col else "Unknown"
    svc_col = _find_col(raw, SERVICE_CANDIDATES)
    df["program"] = raw[svc_col].astype(str).str.strip() if svc_col else "General"
    status_col = _find_col(raw, STATUS_CANDIDATES)
    df["status"] = raw[status_col].astype(str).str.strip().str.title() if status_col else "Enrolled"
    return df.dropna(subset=["client"])


def _normalize_commission(raw: pd.DataFrame) -> pd.DataFrame:
    df = pd.DataFrame()
    date_col = _find_col(raw, DATE_CANDIDATES)
    df["date"] = pd.to_datetime(raw[date_col], errors="coerce") if date_col else pd.NaT
    person_col = _find_col(raw, PERSON_CANDIDATES)
    df["name"] = raw[person_col].astype(str).str.strip() if person_col else "Unknown"
    amt_col = _find_col(raw, AMOUNT_CANDIDATES)
    df["amount"] = _clean_amount(raw[amt_col]) if amt_col else np.nan
    return df.dropna(subset=["amount"]).query("amount != 0")


_NORMALIZERS = {
    "sales": _normalize_sales,
    "payroll": _normalize_payroll,
    "attendance": _normalize_attendance,
    "enrollment": _normalize_enrollment,
    "commission": _normalize_commission,
}


def parse_client_workbook(file) -> dict[str, pd.DataFrame]:
    """Classify every sheet in a client workbook and normalize what we can.

    Returns {kind: normalized DataFrame} for kinds found. Sheets that can't
    be classified are returned under 'unrecognized' as a list of names.
    """
    out: dict[str, list[pd.DataFrame]] = {}
    unrecognized: list[str] = []
    for sheet_name, raw in _read_any(file).items():
        raw = raw.dropna(how="all").dropna(axis=1, how="all")
        if raw.empty:
            continue
        kind = _classify_sheet(sheet_name, raw)
        if kind is None:
            unrecognized.append(sheet_name)
            continue
        try:
            norm = _NORMALIZERS[kind](raw)
        except Exception:
            unrecognized.append(sheet_name)
            continue
        if not norm.empty:
            out.setdefault(kind, []).append(norm)

    result = {k: pd.concat(v, ignore_index=True) for k, v in out.items()}
    if unrecognized:
        result["unrecognized"] = unrecognized  # type: ignore[assignment]
    return result
