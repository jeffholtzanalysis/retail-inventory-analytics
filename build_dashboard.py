"""
Injects assets/dashboard_summary.json (produced by notebooks/analysis.ipynb)
into dashboard_template.html to produce dashboard.html at the repo root,
which is what GitHub Pages serves.

Run:
    python3 build_dashboard.py
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
summary = json.loads((ROOT / "assets" / "dashboard_summary.json").read_text())
template = (ROOT / "dashboard_template.html").read_text()

output = template.replace("/*__DASHBOARD_DATA__*/", json.dumps(summary))
(ROOT / "dashboard.html").write_text(output)
print("Wrote dashboard.html")
