"""
Loads the CSVs in data/ into a local SQLite database using sql/schema.sql,
then runs every query in sql/queries.sql and prints the results.

This exists to prove the SQL in this repo actually runs (not just
copy-pasted) and to produce sql/sample_output.txt for reference.

Run:
    python3 sql/run_queries.py
"""

import sqlite3
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "sql" / "retail.db"
OUTPUT_PATH = ROOT / "sql" / "sample_output.txt"


def build_database() -> sqlite3.Connection:
    DB_PATH.unlink(missing_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript((ROOT / "sql" / "schema.sql").read_text())

    pd.read_csv(ROOT / "data" / "stores.csv").to_sql("stores", conn, if_exists="append", index=False)
    pd.read_csv(ROOT / "data" / "products.csv").to_sql("products", conn, if_exists="append", index=False)
    pd.read_csv(ROOT / "data" / "inventory_transactions.csv").to_sql(
        "inventory_transactions", conn, if_exists="append", index=False
    )
    return conn


def split_queries(sql_text: str) -> list[tuple[str, str]]:
    """Split queries.sql into (title, sql) pairs using the '-- N. Title' comment headers."""
    chunks = []
    current_title = None
    current_lines: list[str] = []
    for line in sql_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("-- ") and stripped[3:4].isdigit():
            if current_title is not None:
                chunks.append((current_title, "\n".join(current_lines)))
            current_title = stripped.lstrip("- ").split("---")[0].strip()
            current_lines = []
        elif current_title is not None:
            current_lines.append(line)
    if current_title is not None:
        chunks.append((current_title, "\n".join(current_lines)))
    return chunks


def main() -> None:
    conn = build_database()
    queries_sql = (ROOT / "sql" / "queries.sql").read_text()
    queries = split_queries(queries_sql)

    lines = []
    for title, sql in queries:
        lines.append("=" * 78)
        lines.append(title)
        lines.append("=" * 78)
        df = pd.read_sql_query(sql, conn)
        lines.append(df.to_string(index=False))
        lines.append("")
        print(f"[ok] {title} -> {len(df)} rows")

    OUTPUT_PATH.write_text("\n".join(lines))
    print(f"\nWrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
