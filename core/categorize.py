"""Rule-based transaction categorization and vendor extraction.

Categories are tuned for small service businesses ($500K–$3M revenue):
heavy advertising, payroll/contractors, rent, software subscriptions.
The advisor can override any category in the Data Review screen.
"""

from __future__ import annotations

import re

import pandas as pd

# Order matters: first match wins. (category, [keywords]) on the cleaned
# lowercase description.
CATEGORY_RULES: list[tuple[str, list[str]]] = [
    ("Transfers", ["transfer", "xfer", "zelle to savings", "online transfer", "to checking", "to savings"]),
    ("Owner Draws / Distributions", ["owner draw", "distribution", "owners draw", "member draw", "shareholder"]),
    ("Advertising & Marketing", [
        "google ads", "googleads", "google adwords", "adwords", "meta platforms", "facebook ads", "facebk",
        "fb ads", "instagram", "tiktok", "yelp", "linkedin", "bing ads", "microsoft ads", "snapchat",
        "groupon", "thumbtack", "angi", "nextdoor", "mailchimp", "klaviyo", "hubspot", "constant contact",
        "advertis", "marketing", "promo", "sponsor", "billboard", "seo ", "ppc",
    ]),
    ("Payroll & Wages", [
        "gusto", "adp", "paychex", "quickbooks payroll", "intuit payroll", "payroll", "direct dep",
        "salary", "wages", "rippling", "justworks", "onpay", "trinet",
    ]),
    ("Contractors", ["upwork", "fiverr", "1099", "contractor", "freelance", "consulting fee", "subcontract"]),
    ("Payroll Taxes", ["eftps", "irs usataxpymt", "941", "940", "edd", "state withholding", "futa", "suta", "payroll tax"]),
    ("Income Taxes", ["irs", "franchise tax", "estimated tax", "dept of revenue", "tax payment", "state tax"]),
    ("Rent & Facilities", ["rent", "lease", "landlord", "property mgmt", "property management", "wework", "regus", "storage"]),
    ("Utilities", ["electric", "edison", "pg&e", "pge ", "water", "gas co", "utility", "utilities", "waste", "internet", "comcast", "spectrum", "at&t", "verizon", "t-mobile"]),
    ("Software & Subscriptions", [
        "quickbooks", "intuit", "adobe", "zoom", "google workspace", "gsuite", "microsoft 365", "office 365",
        "slack", "dropbox", "canva", "calendly", "shopify", "squarespace", "wix", "godaddy", "aws",
        "openai", "anthropic", "notion", "monday.com", "asana", "subscription", "saas", "software",
    ]),
    ("Merchant & Bank Fees", [
        "stripe fee", "square fee", "paypal fee", "merchant fee", "processing fee", "service charge",
        "monthly fee", "overdraft", "wire fee", "bank fee", "nsf fee", "interchange",
    ]),
    ("Insurance", ["insurance", "geico", "state farm", "hartford", "hiscox", "next insurance", "workers comp", "liability"]),
    ("Professional Services", ["attorney", "legal", "law office", "cpa", "accounting", "bookkeep", "notary", "advisory"]),
    ("Loan & Interest Payments", ["loan pmt", "loan payment", "sba", "kabbage", "ondeck", "amex loan", "interest charge", "principal", "capital one loan"]),
    ("Supplies & Materials", ["amazon", "amzn", "staples", "office depot", "costco", "uline", "home depot", "lowes", "supplies", "walmart", "target"]),
    ("Travel & Vehicle", ["uber", "lyft", "delta", "united", "southwest", "airbnb", "hotel", "marriott", "hilton", "shell", "chevron", "exxon", "gas station", "parking", "mileage", "fuel"]),
    ("Meals & Entertainment", ["restaurant", "doordash", "grubhub", "ubereats", "starbucks", "cafe", "catering", "chipotle", "pizza"]),
    ("Training & Education", ["udemy", "coursera", "conference", "seminar", "training", "certification", "workshop", "tuition"]),
    ("Cost of Goods / Direct Costs", ["wholesale", "inventory", "materials", "cogs", "distributor", "vendor payment", "curriculum", "textbook"]),
]

INCOME_RULES: list[tuple[str, list[str]]] = [
    ("Client Payments", ["stripe", "square", "paypal", "deposit", "payment received", "invoice", "ach credit", "client", "venmo cashout", "zelle from", "clover"]),
    ("Refunds Received", ["refund", "reversal", "rebate"]),
    ("Loan Proceeds", ["loan proceeds", "loan deposit", "sba deposit", "advance"]),
    ("Interest Income", ["interest paid", "interest earned", "int paid"]),
]

# Known advertising platforms → canonical vendor names, used for the
# ad-vendor breakdown.
AD_VENDOR_PATTERNS: dict[str, list[str]] = {
    "Google Ads": ["google ads", "googleads", "adwords", "google adwords"],
    "Meta (Facebook/Instagram)": ["meta platforms", "facebook", "facebk", "fb ads", "instagram"],
    "TikTok Ads": ["tiktok"],
    "Yelp": ["yelp"],
    "LinkedIn Ads": ["linkedin"],
    "Microsoft/Bing Ads": ["bing ads", "microsoft ads"],
    "Nextdoor": ["nextdoor"],
    "Thumbtack": ["thumbtack"],
    "Angi": ["angi", "angies list"],
    "Groupon": ["groupon"],
    "Mailchimp": ["mailchimp"],
    "Klaviyo": ["klaviyo"],
    "HubSpot": ["hubspot"],
}

_NOISE = re.compile(
    r"\b(pos|ach|debit|credit|card|purchase|payment|pmt|online|web|recurring|"
    r"des|id|ref|check|chk|wd|dep|visa|mc|sq|tst|ppd|ccd|co|ed|epay)\b|"
    r"[#*]|\d{3,}|x{2,}\d*",
    re.IGNORECASE,
)


def extract_vendor(description: str) -> str:
    """Pull a human-readable vendor name out of a raw bank description."""
    d = str(description).lower()
    for vendor, pats in AD_VENDOR_PATTERNS.items():
        if any(p in d for p in pats):
            return vendor
    cleaned = _NOISE.sub(" ", str(description))
    cleaned = re.sub(r"[^A-Za-z&' ]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    words = cleaned.split()[:3]
    if not words:
        return "Unknown"
    return " ".join(words).title()


def _match(desc: str, rules: list[tuple[str, list[str]]]) -> str | None:
    for cat, kws in rules.items() if isinstance(rules, dict) else rules:
        if any(kw in desc for kw in kws):
            return cat
    return None


def categorize(bank: pd.DataFrame) -> pd.DataFrame:
    """Add vendor, category and type columns to normalized bank data."""
    df = bank.copy()
    desc = df["description"].astype(str).str.lower()

    df["vendor"] = df["description"].map(extract_vendor)

    cats = []
    for d, amt in zip(desc, df["amount"]):
        if amt > 0:
            cats.append(_match(d, INCOME_RULES) or _match(d, CATEGORY_RULES[:1]) or "Other Income")
        else:
            cats.append(_match(d, CATEGORY_RULES) or "Uncategorized")
    df["category"] = cats

    df["type"] = "Expense"
    df.loc[df["amount"] > 0, "type"] = "Income"
    df.loc[df["category"] == "Transfers", "type"] = "Transfer"
    df.loc[df["category"] == "Owner Draws / Distributions", "type"] = "Owner Draw"
    return df


# Categories that are generally tax-deductible business expenses (used on
# the tax page; advisory-level grouping, not tax advice).
DEDUCTIBLE_CATEGORIES = [
    "Advertising & Marketing", "Payroll & Wages", "Contractors", "Payroll Taxes",
    "Rent & Facilities", "Utilities", "Software & Subscriptions", "Merchant & Bank Fees",
    "Insurance", "Professional Services", "Supplies & Materials", "Travel & Vehicle",
    "Training & Education", "Cost of Goods / Direct Costs",
]

# Costs treated as DIRECT cost of delivering service (vs overhead) in the
# per-client cost-of-service model.
DIRECT_COST_CATEGORIES = ["Cost of Goods / Direct Costs", "Contractors", "Supplies & Materials"]

OVERHEAD_CATEGORIES_EXCLUDE = ["Transfers", "Owner Draws / Distributions", "Income Taxes", "Uncategorized"]
