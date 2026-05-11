"""
test_hardware_monitor.py
------------------------
pytest test suite for HardwareMonitor.
Demonstrates: fixture usage, parametrize, mocking, edge-case coverage.
"""

import pytest
from unittest.mock import patch, MagicMock
from src.hardware_monitor import HardwareMonitor, CheckResult


# ──────────────────────────────────────────────
#  Fixtures
# ──────────────────────────────────────────────

@pytest.fixture
def default_config():
    return {
        "cpu_threshold_percent": 85.0,
        "min_memory_available_gb": 2.0,
        "min_disk_free_gb": 10.0,
        "max_network_latency_ms": 100.0,
    }


@pytest.fixture
def monitor(default_config):
    return HardwareMonitor(default_config)


# ──────────────────────────────────────────────
#  CPU tests
# ──────────────────────────────────────────────

class TestCPUCheck:
    def test_cpu_pass_when_below_threshold(self, monitor):
        with patch.object(monitor, "_simulate_cpu_usage", return_value=50.0):
            result = monitor.check_cpu()
        assert result.passed is True
        assert result.component == "CPU"
        assert result.value == 50.0

    def test_cpu_fail_when_above_threshold(self, monitor):
        with patch.object(monitor, "_simulate_cpu_usage", return_value=90.0):
            result = monitor.check_cpu()
        assert result.passed is False
        assert "exceeds" in result.message

    def test_cpu_exact_threshold_is_failing(self, monitor):
        """Value equal to threshold should fail (strictly less-than check)."""
        with patch.object(monitor, "_simulate_cpu_usage", return_value=85.0):
            result = monitor.check_cpu()
        assert result.passed is False

    @pytest.mark.parametrize("cpu_val,expected_pass", [
        (0.0, True),
        (84.9, True),
        (85.0, False),
        (100.0, False),
    ])
    def test_cpu_parametrized(self, monitor, cpu_val, expected_pass):
        with patch.object(monitor, "_simulate_cpu_usage", return_value=cpu_val):
            result = monitor.check_cpu()
        assert result.passed is expected_pass


# ──────────────────────────────────────────────
#  Memory tests
# ──────────────────────────────────────────────

class TestMemoryCheck:
    def test_memory_pass_when_sufficient(self, monitor):
        with patch.object(monitor, "_simulate_memory_available", return_value=8.0):
            result = monitor.check_memory()
        assert result.passed is True
        assert result.unit == "GB"

    def test_memory_fail_when_low(self, monitor):
        with patch.object(monitor, "_simulate_memory_available", return_value=0.5):
            result = monitor.check_memory()
        assert result.passed is False
        assert "below" in result.message

    @pytest.mark.parametrize("avail_gb,expected_pass", [
        (0.0, False),
        (1.9, False),
        (2.0, True),
        (16.0, True),
    ])
    def test_memory_parametrized(self, monitor, avail_gb, expected_pass):
        with patch.object(monitor, "_simulate_memory_available", return_value=avail_gb):
            result = monitor.check_memory()
        assert result.passed is expected_pass


# ──────────────────────────────────────────────
#  Disk tests
# ──────────────────────────────────────────────

class TestDiskCheck:
    def test_disk_uses_real_shutil(self, monitor):
        """check_disk should work without mocking (real filesystem)."""
        result = monitor.check_disk("/")
        assert isinstance(result, CheckResult)
        assert result.component == "Disk"
        assert result.value >= 0

    def test_disk_fail_when_below_threshold(self, monitor):
        # Simulate tiny disk: 2 GB free
        free_bytes = int(2 * 1024 ** 3)
        with patch("shutil.disk_usage", return_value=(100 * 1024**3, 98 * 1024**3, free_bytes)):
            result = monitor.check_disk("/")
        assert result.passed is False


# ──────────────────────────────────────────────
#  Network tests
# ──────────────────────────────────────────────

class TestNetworkCheck:
    def test_network_pass_when_low_latency(self, monitor):
        with patch.object(monitor, "_simulate_network_latency", return_value=20.0):
            result = monitor.check_network_latency()
        assert result.passed is True

    def test_network_fail_when_high_latency(self, monitor):
        with patch.object(monitor, "_simulate_network_latency", return_value=200.0):
            result = monitor.check_network_latency()
        assert result.passed is False

    @pytest.mark.parametrize("latency,expected_pass", [
        (10.0, True),
        (99.9, True),
        (100.0, True),   # equal to threshold → passes (<=)
        (100.1, False),
        (500.0, False),
    ])
    def test_network_latency_parametrized(self, monitor, latency, expected_pass):
        with patch.object(monitor, "_simulate_network_latency", return_value=latency):
            result = monitor.check_network_latency()
        assert result.passed is expected_pass


# ──────────────────────────────────────────────
#  run_all integration
# ──────────────────────────────────────────────

class TestRunAll:
    def test_run_all_returns_four_results(self, monitor):
        results = monitor.run_all()
        assert len(results) == 4

    def test_run_all_stores_in_results_list(self, monitor):
        monitor.run_all()
        assert len(monitor.results) == 4

    def test_run_all_clears_previous_results(self, monitor):
        monitor.run_all()
        monitor.run_all()
        assert len(monitor.results) == 4   # not 8

    def test_all_results_are_check_result_instances(self, monitor):
        results = monitor.run_all()
        for r in results:
            assert isinstance(r, CheckResult)

    def test_result_to_dict_has_required_keys(self, monitor):
        results = monitor.run_all()
        required = {"component", "metric", "value", "unit", "threshold", "passed", "message", "timestamp"}
        for r in results:
            assert required.issubset(r.to_dict().keys())


# ──────────────────────────────────────────────
#  Custom threshold config
# ──────────────────────────────────────────────

class TestCustomConfig:
    def test_strict_cpu_threshold(self):
        monitor = HardwareMonitor({"cpu_threshold_percent": 10.0})
        with patch.object(monitor, "_simulate_cpu_usage", return_value=15.0):
            result = monitor.check_cpu()
        assert result.passed is False

    def test_lenient_memory_threshold(self):
        monitor = HardwareMonitor({"min_memory_available_gb": 0.1})
        with patch.object(monitor, "_simulate_memory_available", return_value=0.5):
            result = monitor.check_memory()
        assert result.passed is True
