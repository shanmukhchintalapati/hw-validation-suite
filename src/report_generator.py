"""
report_generator.py
-------------------
Produces pass/fail HTML and CSV reports from validation results.
Covers: automation documentation, reporting, continuous improvement metrics.
"""

import csv
import os
from datetime import datetime
from src.logger import get_logger

logger = get_logger(__name__)

REPORT_DIR = os.path.join(os.path.dirname(__file__), "..", "reports")
os.makedirs(REPORT_DIR, exist_ok=True)


def _ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def generate_csv(results: list, filename: str = "") -> str:
    """Write results to a CSV file and return the file path."""
    path = os.path.join(REPORT_DIR, filename or f"report_{_ts()}.csv")
    if not results:
        logger.warning("generate_csv called with empty results list")
        return path

    all_keys: dict = {}
    for r in results:
        all_keys.update(r.to_dict())
    fieldnames = list(all_keys.keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in results:
            row = {k: "" for k in fieldnames}
            row.update(r.to_dict())
            writer.writerow(row)

    logger.info("CSV report written: %s", path)
    return path


def generate_html(results: list, suite_name: str = "HW Validation Suite") -> str:
    """Generate a styled HTML report and return the file path."""
    path = os.path.join(REPORT_DIR, f"report_{_ts()}.html")
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed
    pct = (passed / total * 100) if total else 0

    rows = ""
    for r in results:
        d = r.to_dict()
        status_cls = "pass" if r.passed else "fail"
        status_txt = "PASS" if r.passed else "FAIL"
        defect = d.get("defect_type", "—")
        rows += f"""
        <tr class="{status_cls}">
          <td>{d.get('component', d.get('test_name', ''))}</td>
          <td>{d.get('metric', d.get('test_name', ''))}</td>
          <td>{d['value']} {d['unit']}</td>
          <td>{d['threshold']} {d['unit']}</td>
          <td><span class="badge {status_cls}">{status_txt}</span></td>
          <td>{defect}</td>
          <td style="font-size:12px;color:#666">{d['message']}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{suite_name} — Report</title>
<style>
  body {{ font-family: monospace; margin: 32px; color: #222; background: #f9f9f9; }}
  h1 {{ font-size: 20px; margin-bottom: 4px; }}
  .summary {{ display:flex; gap:24px; margin:16px 0 24px; }}
  .stat {{ background:#fff; border:1px solid #ddd; border-radius:6px;
           padding:12px 20px; text-align:center; }}
  .stat span {{ display:block; font-size:24px; font-weight:700; }}
  .stat small {{ font-size:12px; color:#888; }}
  table {{ width:100%; border-collapse:collapse; background:#fff;
           border:1px solid #ddd; border-radius:6px; overflow:hidden; }}
  th {{ background:#333; color:#fff; padding:10px 12px; text-align:left;
        font-size:13px; }}
  td {{ padding:9px 12px; font-size:13px; border-bottom:1px solid #eee; }}
  tr.fail td {{ background:#fff5f5; }}
  .badge {{ padding:2px 10px; border-radius:4px; font-size:12px; font-weight:700; }}
  .badge.pass {{ background:#d4edda; color:#155724; }}
  .badge.fail {{ background:#f8d7da; color:#721c24; }}
</style>
</head>
<body>
<h1>{suite_name}</h1>
<p style="color:#666;font-size:13px">Generated: {datetime.now().isoformat(timespec='seconds')}</p>
<div class="summary">
  <div class="stat"><span>{total}</span><small>Total</small></div>
  <div class="stat"><span style="color:#155724">{passed}</span><small>Passed</small></div>
  <div class="stat"><span style="color:#721c24">{failed}</span><small>Failed</small></div>
  <div class="stat"><span>{pct:.0f}%</span><small>Pass rate</small></div>
</div>
<table>
<thead>
  <tr>
    <th>Component</th><th>Metric</th><th>Measured</th>
    <th>Threshold</th><th>Status</th><th>Defect Type</th><th>Message</th>
  </tr>
</thead>
<tbody>{rows}
</tbody>
</table>
</body>
</html>"""

    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    logger.info("HTML report written: %s", path)
    return path
