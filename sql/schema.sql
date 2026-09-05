-- Retail Inventory Analytics — schema
-- Target: any standard SQL engine (written/tested against SQLite; portable to
-- Postgres/MySQL with minor type tweaks, e.g. TEXT -> VARCHAR, DATE stays DATE).

CREATE TABLE stores (
    store_id     TEXT PRIMARY KEY,
    store_name   TEXT NOT NULL,
    region       TEXT NOT NULL
);

CREATE TABLE products (
    product_id     TEXT PRIMARY KEY,
    product_name   TEXT NOT NULL,
    category       TEXT NOT NULL,
    supplier       TEXT NOT NULL,
    unit_cost      NUMERIC NOT NULL,
    unit_price     NUMERIC NOT NULL,
    reorder_point  INTEGER NOT NULL,
    reorder_qty    INTEGER NOT NULL,
    lead_time_days INTEGER NOT NULL
);

-- One row per store/product/day: what was demanded, sold, received, and left
-- in stock at end of day.
CREATE TABLE inventory_transactions (
    date                 DATE NOT NULL,
    store_id             TEXT NOT NULL REFERENCES stores(store_id),
    product_id           TEXT NOT NULL REFERENCES products(product_id),
    units_demanded       INTEGER NOT NULL,
    units_sold           INTEGER NOT NULL,
    units_received       INTEGER NOT NULL,
    units_in_stock_eod   INTEGER NOT NULL,
    stockout_flag        INTEGER NOT NULL CHECK (stockout_flag IN (0, 1)),
    promotion_flag       INTEGER NOT NULL CHECK (promotion_flag IN (0, 1)),
    PRIMARY KEY (date, store_id, product_id)
);

CREATE INDEX idx_txn_product ON inventory_transactions(product_id);
CREATE INDEX idx_txn_store ON inventory_transactions(store_id);
CREATE INDEX idx_txn_date ON inventory_transactions(date);
