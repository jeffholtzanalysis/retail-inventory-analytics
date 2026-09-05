"""
Generates a synthetic but realistic retail inventory & sales dataset for FY2025.

Simulates daily point-of-sale demand and inventory replenishment (with lead
times and reorder points) for a chain of stores across the US, so the
resulting data has genuine stockouts, seasonality, and turnover patterns to
analyze -- rather than random noise.

Run:
    python3 data/generate_data.py

Outputs (all under data/):
    stores.csv                 dimension table
    products.csv                dimension table
    inventory_transactions.csv  daily fact table (one row per store/product/day)
"""

import numpy as np
import pandas as pd

RNG = np.random.default_rng(seed=42)

START_DATE = pd.Timestamp("2025-01-01")
END_DATE = pd.Timestamp("2025-12-31")
DATES = pd.date_range(START_DATE, END_DATE, freq="D")

# ---------------------------------------------------------------------------
# Dimension: stores
# ---------------------------------------------------------------------------
STORES = pd.DataFrame(
    [
        ("S01", "Chicago Loop", "Midwest"),
        ("S02", "Atlanta Midtown", "Southeast"),
        ("S03", "Denver Uptown", "West"),
        ("S04", "Boston Back Bay", "Northeast"),
        ("S05", "Austin Downtown", "South"),
        ("S06", "Seattle Capitol Hill", "Northwest"),
    ],
    columns=["store_id", "store_name", "region"],
)

# Relative baseline traffic multiplier per store (some stores just sell more)
STORE_DEMAND_MULT = {
    "S01": 1.25,
    "S02": 1.05,
    "S03": 0.85,
    "S04": 1.10,
    "S05": 0.95,
    "S06": 0.80,
}

# ---------------------------------------------------------------------------
# Dimension: products
# ---------------------------------------------------------------------------
CATEGORY_CATALOG = {
    "Beverages": [
        ("Sparkling Water 12pk", 4.20, 7.99),
        ("Cold Brew Coffee 32oz", 3.10, 5.49),
        ("Orange Juice 64oz", 2.75, 4.99),
        ("Energy Drink 4pk", 5.60, 9.49),
    ],
    "Snacks": [
        ("Tortilla Chips Family Size", 2.30, 4.79),
        ("Trail Mix 16oz", 3.90, 6.99),
        ("Pretzel Sticks 14oz", 1.80, 3.49),
        ("Granola Bars 12ct", 3.20, 5.99),
    ],
    "Dairy": [
        ("Whole Milk 1 Gallon", 2.60, 3.99),
        ("Greek Yogurt 4pk", 3.40, 5.49),
        ("Shredded Cheese 16oz", 3.80, 5.99),
        ("Butter 1lb", 3.10, 4.79),
    ],
    "Bakery": [
        ("Sourdough Loaf", 1.90, 4.49),
        ("Bagels 6pk", 1.60, 3.99),
        ("Croissants 4pk", 2.20, 4.99),
    ],
    "Frozen": [
        ("Frozen Pizza 12in", 3.50, 6.99),
        ("Ice Cream Pint", 2.40, 4.99),
        ("Frozen Vegetables 16oz", 1.50, 2.99),
        ("Frozen Waffles 10ct", 2.10, 3.99),
    ],
    "Household": [
        ("Paper Towels 6pk", 6.80, 11.99),
        ("Dish Soap 24oz", 1.90, 3.49),
        ("Laundry Detergent 50oz", 7.20, 12.99),
        ("Trash Bags 30ct", 5.40, 9.49),
    ],
    "Personal Care": [
        ("Shampoo 12oz", 3.60, 6.99),
        ("Toothpaste 2pk", 2.10, 4.49),
        ("Body Wash 18oz", 3.20, 5.99),
    ],
    "Produce": [
        ("Bananas (lb)", 0.35, 0.69),
        ("Avocados 4pk", 2.80, 4.99),
        ("Baby Spinach 5oz", 1.70, 3.49),
        ("Roma Tomatoes (lb)", 0.90, 1.79),
    ],
}

SUPPLIERS = ["Heartland Foods Co", "Pacific Distributors", "Summit Wholesale", "Coastal Supply Group"]

product_rows = []
pid = 1
for category, items in CATEGORY_CATALOG.items():
    for name, cost, price in items:
        product_rows.append(
            {
                "product_id": f"P{pid:03d}",
                "product_name": name,
                "category": category,
                "supplier": SUPPLIERS[RNG.integers(0, len(SUPPLIERS))],
                "unit_cost": cost,
                "unit_price": price,
                # base daily demand differs a lot by product type
                "base_daily_demand": {
                    "Produce": RNG.uniform(10, 22),
                    "Dairy": RNG.uniform(8, 16),
                    "Bakery": RNG.uniform(6, 14),
                    "Beverages": RNG.uniform(7, 15),
                    "Snacks": RNG.uniform(5, 12),
                    "Frozen": RNG.uniform(4, 10),
                    "Household": RNG.uniform(2, 6),
                    "Personal Care": RNG.uniform(2, 5),
                }[category],
                "reorder_point": None,  # filled below
                "reorder_qty": None,
                "lead_time_days": int(RNG.integers(2, 6)),
            }
        )
        pid += 1

PRODUCTS = pd.DataFrame(product_rows)
# reorder point ~ 6 days of average demand; reorder qty ~ 14 days of demand
PRODUCTS["reorder_point"] = (PRODUCTS["base_daily_demand"] * 6).round().astype(int)
PRODUCTS["reorder_qty"] = (PRODUCTS["base_daily_demand"] * 14).round().astype(int)

# ---------------------------------------------------------------------------
# Seasonality helpers
# ---------------------------------------------------------------------------
DOW_MULT = np.array([0.90, 0.88, 0.92, 0.98, 1.15, 1.35, 1.20])  # Mon..Sun

def month_seasonality(month: int, category: str) -> float:
    # General holiday bump in Nov/Dec, summer bump for beverages/produce, etc.
    base = 1.0
    if month in (11, 12):
        base *= 1.35 if category != "Produce" else 1.15
    if month in (6, 7, 8) and category in ("Beverages", "Produce", "Frozen"):
        base *= 1.25
    if month in (1,) and category in ("Personal Care", "Household"):
        base *= 1.10  # new year restocking
    return base


def promo_flag(rng: np.random.Generator, month: int) -> bool:
    # ~1 promo week per product per quarter, more likely in Nov/Dec
    p = 0.10 if month in (11, 12) else 0.05
    return rng.random() < p


# ---------------------------------------------------------------------------
# Simulate daily inventory + sales per store/product
# ---------------------------------------------------------------------------
records = []

for _, store in STORES.iterrows():
    store_mult = STORE_DEMAND_MULT[store["store_id"]]
    for _, prod in PRODUCTS.iterrows():
        stock = int(prod["reorder_qty"] * 1.5)  # starting inventory
        pending_receipts = {}  # date -> qty arriving

        for day in DATES:
            month = day.month
            dow = day.dayofweek  # Monday=0
            season = month_seasonality(month, prod["category"])
            promo = promo_flag(RNG, month)
            promo_mult = 1.6 if promo else 1.0

            expected_demand = (
                prod["base_daily_demand"] * store_mult * DOW_MULT[dow] * season * promo_mult
            )
            demand = max(0, int(RNG.poisson(max(expected_demand, 0.1))))

            # receive any inbound stock scheduled for today
            receipt_qty = pending_receipts.pop(day, 0)
            stock += receipt_qty

            units_sold = min(demand, stock)
            stockout = 1 if demand > stock else 0
            stock -= units_sold

            # reorder if below reorder point and nothing already inbound
            if stock <= prod["reorder_point"] and not pending_receipts:
                arrival = day + pd.Timedelta(days=int(prod["lead_time_days"]))
                pending_receipts[arrival] = pending_receipts.get(arrival, 0) + prod["reorder_qty"]

            records.append(
                (
                    day.date().isoformat(),
                    store["store_id"],
                    prod["product_id"],
                    int(demand),
                    int(units_sold),
                    int(receipt_qty),
                    int(stock),
                    stockout,
                    int(promo),
                )
            )

TXN = pd.DataFrame(
    records,
    columns=[
        "date",
        "store_id",
        "product_id",
        "units_demanded",
        "units_sold",
        "units_received",
        "units_in_stock_eod",
        "stockout_flag",
        "promotion_flag",
    ],
)

# ---------------------------------------------------------------------------
# Write outputs
# ---------------------------------------------------------------------------
STORES.to_csv("data/stores.csv", index=False)
PRODUCTS.drop(columns=["base_daily_demand"]).to_csv("data/products.csv", index=False)
TXN.to_csv("data/inventory_transactions.csv", index=False)

print(f"stores: {len(STORES)} rows")
print(f"products: {len(PRODUCTS)} rows")
print(f"transactions: {len(TXN):,} rows")
print(f"date range: {TXN['date'].min()} to {TXN['date'].max()}")
