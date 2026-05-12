"""
framework_runner.py
-------------------
Orchestrates HardwareMonitor and SSDValidator, applies retry logic,
saves results to SQLite database, generates reports, sends alerts,
and updates the live dashboard.

Covers: maintain/enhance automation framework, test coverage,
        execution time reporting, enterprise integration.
"""

import time
import yaml
import os
import sys
from src.hardware_monitor import HardwareMonitor
from src.ssd_validator import SSDValidator
from src import report_generator
from src import database
from src import alert
from src import dashboard
from src.logger import get_logger

logger = get_logger(__name__)

DEFAULT_CONFIG = {
    "cpu_threshold_percent": 85.0,
    "min_memory_available_gb": 2.0,
    "min_disk_free_gb": 10.0,
    "max_network_latency_ms": 100.0,
    "min_network_bandwidth_mbs": 0.1,
    "max_packet_loss_pct": 5.0,
    "max_cpu_temp_celsius": 80.0,
    "latency_check_host": "8.8.8.8",
    "latency_check_port": 53,
    "ping_host": "8.8.8.8",
    "ping_count": 10,
    "bandwidth_sample_seconds": 1,
    "min_sequential_throughput_mbs": 200.0,
    "throughput_block_size_mb": 16,
    "min_random_iops": 5000,
    "max_write_latency_us": 500,
    "max_retries": 2,
    "retry_delay_seconds": 1,
    "alert_enabled": False,
    "save_to_db": True,
    "generate_dashboard": True,
}


def load_config(path: str = "config.yaml") -> dict:
    """Load YAML config; fall back to defaults on any error."""
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                user_cfg = yaml.safe_load(f) or {}
            merged = {**DEFAULT_CONFIG, **user_cfg}
            logger.info("Config loaded from %s", path)
            return merged
        except yaml.YAMLError as exc:
            logger.error("YAML parse error in %s: %s — using defaults", path, exc)
    else:
        logger.warning("Config file not found at '%s' — using defaults", path)
    return DEFAULT_CONFIG.copy()


def run_suite(config: dict | None = None) -> dict:
    """
    Execute the full validation suite with retry logic.
    Saves results to DB, generates reports, sends alerts, updates dashboard.
    Returns a summary dict with all results and timing.
    """
    config = config or load_config()
    max_retries = config.get("max_retries", 2)
    retry_delay = config.get("retry_delay_seconds", 1)

    suite_start = time.perf_counter()
    logger.info("=" * 60)
    logger.info("HW-Validation-Suite starting")
    logger.info("=" * 60)

    all_results = []

    # ── Hardware Monitor ──────────────────────────────────────────────
    hw_monitor = HardwareMonitor(config)
    hw_results = _run_with_retry(
        hw_monitor.run_all, max_retries, retry_delay, "HardwareMonitor"
    )
    all_results.extend(hw_results)

    # ── SSD Validator ─────────────────────────────────────────────────
    ssd_validator = SSDValidator(config)
    ssd_results = _run_with_retry(
        ssd_validator.run_all, max_retries, retry_delay, "SSDValidator"
    )
    all_results.extend(ssd_results)

    elapsed = time.perf_counter() - suite_start
    passed = sum(1 for r in all_results if r.passed)
    failed = len(all_results) - passed

    logger.info(
        "Suite finished in %.2f s | %d passed | %d failed", elapsed, passed, failed
    )

    # ── Reports ───────────────────────────────────────────────────────
    csv_path = report_generator.generate_csv(all_results)
    html_path = report_generator.generate_html(all_results)

    summary = {
        "total": len(all_results),
        "passed": passed,
        "failed": failed,
        "elapsed_seconds": round(elapsed, 3),
        "pass_rate_pct": round(passed / len(all_results) * 100, 1) if all_results else 0,
        "csv_report": csv_path,
        "html_report": html_path,
        "results": all_results,
    }

    # ── Save to SQLite database ───────────────────────────────────────
    if config.get("save_to_db", True):
        try:
            run_id = database.save_run(summary)
            summary["run_id"] = run_id
            logger.info("Results saved to database (run_id=%d)", run_id)
        except Exception as exc:
            logger.error("Database save failed: %s", exc)

    # ── Send email alert if hardware_defect found ─────────────────────
    if config.get("alert_enabled", False):
        try:
            alert.send_alert_from_config(summary, config)
        except Exception as exc:
            logger.error("Alert send failed: %s", exc)

    # ── Regenerate live dashboard ─────────────────────────────────────
    if config.get("generate_dashboard", True):
        try:
            dash_path = dashboard.generate_dashboard()
            summary["dashboard"] = dash_path
            logger.info("Dashboard updated: %s", dash_path)
        except Exception as exc:
            logger.error("Dashboard generation failed: %s", exc)

    _print_summary(summary)
    return summary


def _run_with_retry(fn, max_retries: int, delay: float, label: str) -> list:
    """Run fn(); on exception retry up to max_retries times."""
    for attempt in range(1, max_retries + 2):
        try:
            logger.info("Running %s (attempt %d)", label, attempt)
            return fn()
        except Exception as exc:
            logger.error(
                "%s attempt %d failed: %s", label, attempt, exc, exc_info=True
            )
            if attempt <= max_retries:
                logger.info("Retrying in %s s…", delay)
                time.sleep(delay)
            else:
                logger.critical("%s exhausted all retries — skipping", label)
                return []


def _print_summary(summary: dict) -> None:
    print("\n" + "=" * 50)
    print("  HW VALIDATION SUITE — RESULTS")
    print("=" * 50)
    print(f"  Total checks : {summary['total']}")
    print(f"  Passed       : {summary['passed']}")
    print(f"  Failed       : {summary['failed']}")
    print(f"  Pass rate    : {summary['pass_rate_pct']}%")
    print(f"  Elapsed      : {summary['elapsed_seconds']} s")
    print(f"  CSV report   : {summary['csv_report']}")
    print(f"  HTML report  : {summary['html_report']}")
    if "dashboard" in summary:
        print(f"  Dashboard    : {summary['dashboard']}")
    if "run_id" in summary:
        print(f"  DB run ID    : {summary['run_id']}")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    result = run_suite()
    sys.exit(0 if result["failed"] == 0 else 1)
