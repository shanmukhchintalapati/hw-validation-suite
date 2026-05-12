"""
dashboard.py
------------
Live HTML dashboard for hw-validation-suite.
Shows real-time validation status, historical trends, and defect summary.
Run with: python -m src.dashboard

Covers: monitoring UI, continuous improvement, enterprise reporting.
"""

import os
import json
from datetime import datetime
from src.logger import get_logger
from src import database

logger = get_logger(__name__)

DASHBOARD_PATH = os.path.join(
    os.path.dirname(__file__), "..", "reports", "dashboard.html"
)


def _status_color(passed: bool) -> str:
    return "#28a745" if passed else "#dc3545"


def _build_dashboard_html(runs: list, defect_summary: dict) -> str:
    """Generate a full standalone HTML dashboard page."""

    # Build run rows
    run_rows = ""
    for run in runs:
        dt = datetime.fromtimestamp(run["run_time"]).strftime("%Y-%m-%d %H:%M:%S")
        rate = run["pass_rate"]
        color = "#28a745" if rate == 100 else "#ffc107" if rate >= 60 else "#dc3545"
        run_rows += f"""
        <tr>
          <td>{run['id']}</td>
          <td>{dt}</td>
          <td>{run['total']}</td>
          <td style="color:#28a745;font-weight:600">{run['passed']}</td>
          <td style="color:#dc3545;font-weight:600">{run['failed']}</td>
          <td><span style="background:{color};color:#fff;padding:2px 10px;
              border-radius:4px;font-size:12px">{rate:.1f}%</span></td>
          <td>{run['elapsed_s']:.2f}s</td>
        </tr>"""

    # Build defect summary cards
    hw_defects = defect_summary.get("hardware_defect", 0)
    fw_issues = defect_summary.get("framework_issue", 0)
    total_runs = len(runs)
    avg_rate = (
        sum(r["pass_rate"] for r in runs) / total_runs if total_runs else 0
    )

    # Build trend data for latest run
    trend_labels = []
    trend_values = []
    if runs:
        latest_results = database.get_run_results(runs[0]["id"])
        for r in latest_results:
            name = r.get("component") or r.get("test_name") or "unknown"
            metric = r.get("metric") or ""
            trend_labels.append(f"{name} {metric}".strip())
            trend_values.append(r["value"])

    chart_data = json.dumps({
        "labels": trend_labels,
        "values": trend_values,
    })

    generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta http-equiv="refresh" content="30">
<title>HW Validation Dashboard</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #0d1117;
         color: #c9d1d9; padding: 24px; }}
  h1 {{ font-size: 22px; color: #58a6ff; margin-bottom: 4px; }}
  .subtitle {{ font-size: 13px; color: #8b949e; margin-bottom: 24px; }}
  .cards {{ display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 28px; }}
  .card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px;
           padding: 16px 24px; min-width: 160px; text-align: center; }}
  .card .num {{ font-size: 32px; font-weight: 700; }}
  .card .lbl {{ font-size: 12px; color: #8b949e; margin-top: 4px; }}
  .green {{ color: #3fb950; }}
  .red   {{ color: #f85149; }}
  .yellow{{ color: #d29922; }}
  .blue  {{ color: #58a6ff; }}
  h2 {{ font-size: 16px; color: #e6edf3; margin: 24px 0 12px; }}
  table {{ width: 100%; border-collapse: collapse; background: #161b22;
           border: 1px solid #30363d; border-radius: 8px; overflow: hidden; }}
  th {{ background: #21262d; color: #8b949e; padding: 10px 14px;
        text-align: left; font-size: 12px; text-transform: uppercase; }}
  td {{ padding: 10px 14px; font-size: 13px; border-bottom: 1px solid #21262d; }}
  tr:last-child td {{ border-bottom: none; }}
  .badge {{ display:inline-block; padding:2px 10px; border-radius:4px;
            font-size:11px; font-weight:600; }}
  canvas {{ background: #161b22; border: 1px solid #30363d;
            border-radius: 8px; padding: 16px; width: 100%; max-width: 800px; }}
  .footer {{ margin-top: 32px; font-size: 12px; color: #8b949e; }}
  .refresh {{ font-size:11px; color:#388bfd; }}
</style>
</head>
<body>
<h1>⚡ HW Validation Dashboard</h1>
<p class="subtitle">Generated: {generated} &nbsp;|&nbsp;
   <span class="refresh">Auto-refreshes every 30 seconds</span></p>

<div class="cards">
  <div class="card">
    <div class="num blue">{total_runs}</div>
    <div class="lbl">Total Runs</div>
  </div>
  <div class="card">
    <div class="num green">{avg_rate:.1f}%</div>
    <div class="lbl">Avg Pass Rate</div>
  </div>
  <div class="card">
    <div class="num red">{hw_defects}</div>
    <div class="lbl">Hardware Defects</div>
  </div>
  <div class="card">
    <div class="num yellow">{fw_issues}</div>
    <div class="lbl">Framework Issues</div>
  </div>
</div>

<h2>📊 Latest Run — Check Values</h2>
<canvas id="chart" height="120"></canvas>

<h2>📋 Run History</h2>
<table>
  <thead>
    <tr>
      <th>Run #</th><th>Timestamp</th><th>Total</th>
      <th>Passed</th><th>Failed</th><th>Pass Rate</th><th>Duration</th>
    </tr>
  </thead>
  <tbody>{run_rows or '<tr><td colspan="7" style="text-align:center;color:#8b949e">No runs yet</td></tr>'}
  </tbody>
</table>

<div class="footer">
  hw-validation-suite &nbsp;|&nbsp;
  Database: {database.DB_PATH} &nbsp;|&nbsp;
  Hardware defects require immediate action.
  Framework issues indicate environment/config problems.
</div>

<script>
const data = {chart_data};
const canvas = document.getElementById('chart');
const ctx = canvas.getContext('2d');
const W = canvas.offsetWidth || 760;
canvas.width = W;
canvas.height = 160;
const n = data.labels.length;
if (n > 0) {{
  const barW = Math.floor((W - 80) / n) - 8;
  const maxV = Math.max(...data.values, 1);
  data.labels.forEach((lbl, i) => {{
    const x = 40 + i * (barW + 8);
    const barH = Math.max(4, Math.floor((data.values[i] / maxV) * 100));
    const y = 130 - barH;
    ctx.fillStyle = '#388bfd';
    ctx.fillRect(x, y, barW, barH);
    ctx.fillStyle = '#8b949e';
    ctx.font = '9px sans-serif';
    ctx.fillText(lbl.substring(0, 10), x, 148);
    ctx.fillStyle = '#e6edf3';
    ctx.fillText(data.values[i].toFixed(1), x, y - 4);
  }});
}}
</script>
</body>
</html>"""


def generate_dashboard() -> str:
    """
    Generate the dashboard HTML from database and write to reports/.
    Returns the path to the generated file.
    """
    database.init_db()
    runs = database.get_recent_runs(limit=20)
    defect_summary = database.get_defect_summary()
    html = _build_dashboard_html(runs, defect_summary)

    os.makedirs(os.path.dirname(DASHBOARD_PATH), exist_ok=True)
    with open(DASHBOARD_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    logger.info("Dashboard written to %s", DASHBOARD_PATH)
    return DASHBOARD_PATH


if __name__ == "__main__":
    path = generate_dashboard()
    print(f"\nDashboard generated: {path}")
    print("Open this file in your browser to view.\n")
