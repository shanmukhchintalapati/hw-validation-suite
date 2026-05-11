"""
test_framework_runner.py
------------------------
Integration tests for the framework orchestration layer.
Covers: retry logic, config loading, report generation, summary accuracy.
"""

from unittest.mock import patch
from src.framework_runner import run_suite, load_config, DEFAULT_CONFIG
from src.hardware_monitor import CheckResult
from src.ssd_validator import SSDCheckResult


# ──────────────────────────────────────────────
#  Config loading
# ──────────────────────────────────────────────

class TestLoadConfig:
    def test_returns_defaults_when_no_file(self, tmp_path):
        cfg = load_config(str(tmp_path / "nonexistent.yaml"))
        assert cfg["cpu_threshold_percent"] == DEFAULT_CONFIG["cpu_threshold_percent"]

    def test_user_values_override_defaults(self, tmp_path):
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("cpu_threshold_percent: 50.0\n")
        cfg = load_config(str(cfg_file))
        assert cfg["cpu_threshold_percent"] == 50.0
        assert cfg["min_memory_available_gb"] == DEFAULT_CONFIG["min_memory_available_gb"]

    def test_bad_yaml_falls_back_to_defaults(self, tmp_path):
        cfg_file = tmp_path / "bad.yaml"
        cfg_file.write_text(":::invalid yaml:::\n")
        cfg = load_config(str(cfg_file))
        # On bad YAML, all required default keys must be present
        for key in DEFAULT_CONFIG:
            assert key in cfg


# ──────────────────────────────────────────────
#  run_suite summary
# ──────────────────────────────────────────────

def _make_fake_hw_results(passed: bool):
    import time as _time
    return [
        CheckResult("CPU", "utilisation", 50.0, "%", 85.0, passed, "ok", _time.time()),
        CheckResult("RAM", "available", 4.0, "GB", 2.0, passed, "ok", _time.time()),
        CheckResult("Disk", "free_space", 20.0, "GB", 10.0, passed, "ok", _time.time()),
        CheckResult("Network", "latency", 30.0, "ms", 100.0, passed, "ok", _time.time()),
    ]


def _make_fake_ssd_results(passed: bool):
    import time as _time
    return [
        SSDCheckResult("sequential_throughput", 300.0, "MB/s", 200.0, passed, "none", "ok", _time.time()),
        SSDCheckResult("random_4k_iops", 8000.0, "IOPS", 5000.0, passed, "none", "ok", _time.time()),
        SSDCheckResult("write_latency", 100.0, "µs", 500.0, passed, "none", "ok", _time.time()),
        SSDCheckResult("smart_health", 1.0, "status", 1.0, passed, "none", "ok", _time.time()),
    ]


class TestRunSuite:
    def test_all_pass_returns_zero_failed(self):
        with patch("src.framework_runner.HardwareMonitor") as MockHW, \
             patch("src.framework_runner.SSDValidator") as MockSSD, \
             patch("src.report_generator.generate_csv", return_value="/tmp/r.csv"), \
             patch("src.report_generator.generate_html", return_value="/tmp/r.html"):

            MockHW.return_value.run_all.return_value = _make_fake_hw_results(True)
            MockSSD.return_value.run_all.return_value = _make_fake_ssd_results(True)

            summary = run_suite({**DEFAULT_CONFIG})

        assert summary["failed"] == 0
        assert summary["passed"] == 8
        assert summary["pass_rate_pct"] == 100.0

    def test_all_fail_returns_correct_counts(self):
        with patch("src.framework_runner.HardwareMonitor") as MockHW, \
             patch("src.framework_runner.SSDValidator") as MockSSD, \
             patch("src.report_generator.generate_csv", return_value="/tmp/r.csv"), \
             patch("src.report_generator.generate_html", return_value="/tmp/r.html"):

            MockHW.return_value.run_all.return_value = _make_fake_hw_results(False)
            MockSSD.return_value.run_all.return_value = _make_fake_ssd_results(False)

            summary = run_suite({**DEFAULT_CONFIG})

        assert summary["passed"] == 0
        assert summary["failed"] == 8

    def test_summary_contains_required_keys(self):
        with patch("src.framework_runner.HardwareMonitor") as MockHW, \
             patch("src.framework_runner.SSDValidator") as MockSSD, \
             patch("src.report_generator.generate_csv", return_value="/tmp/r.csv"), \
             patch("src.report_generator.generate_html", return_value="/tmp/r.html"):

            MockHW.return_value.run_all.return_value = _make_fake_hw_results(True)
            MockSSD.return_value.run_all.return_value = _make_fake_ssd_results(True)
            summary = run_suite({**DEFAULT_CONFIG})

        required = {"total", "passed", "failed", "elapsed_seconds", "pass_rate_pct",
                    "csv_report", "html_report", "results"}
        assert required.issubset(summary.keys())

    def test_elapsed_time_is_non_negative(self):
        with patch("src.framework_runner.HardwareMonitor") as MockHW, \
             patch("src.framework_runner.SSDValidator") as MockSSD, \
             patch("src.report_generator.generate_csv", return_value="/tmp/r.csv"), \
             patch("src.report_generator.generate_html", return_value="/tmp/r.html"):

            MockHW.return_value.run_all.return_value = _make_fake_hw_results(True)
            MockSSD.return_value.run_all.return_value = _make_fake_ssd_results(True)
            summary = run_suite({**DEFAULT_CONFIG})

        assert summary["elapsed_seconds"] >= 0


# ──────────────────────────────────────────────
#  Retry logic
# ──────────────────────────────────────────────

class TestRetryLogic:
    def test_retry_recovers_on_second_attempt(self):
        """Validator fails once then succeeds — result should not be empty."""
        call_count = {"n": 0}

        def flaky_run():
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise RuntimeError("transient error")
            return _make_fake_hw_results(True)

        with patch("src.framework_runner.HardwareMonitor") as MockHW, \
             patch("src.framework_runner.SSDValidator") as MockSSD, \
             patch("src.report_generator.generate_csv", return_value="/tmp/r.csv"), \
             patch("src.report_generator.generate_html", return_value="/tmp/r.html"), \
             patch("time.sleep"):   # speed up delay

            MockHW.return_value.run_all.side_effect = flaky_run
            MockSSD.return_value.run_all.return_value = _make_fake_ssd_results(True)

            run_suite({**DEFAULT_CONFIG, "max_retries": 2, "retry_delay_seconds": 0})

        assert call_count["n"] == 2

    def test_exhausted_retries_returns_empty_for_component(self):
        """All retries fail → that component contributes 0 results."""
        with patch("src.framework_runner.HardwareMonitor") as MockHW, \
             patch("src.framework_runner.SSDValidator") as MockSSD, \
             patch("src.report_generator.generate_csv", return_value="/tmp/r.csv"), \
             patch("src.report_generator.generate_html", return_value="/tmp/r.html"), \
             patch("time.sleep"):

            MockHW.return_value.run_all.side_effect = RuntimeError("always fails")
            MockSSD.return_value.run_all.return_value = _make_fake_ssd_results(True)

            summary = run_suite({**DEFAULT_CONFIG, "max_retries": 1, "retry_delay_seconds": 0})

        # Only SSD results (4) should be present
        assert summary["total"] == 4
