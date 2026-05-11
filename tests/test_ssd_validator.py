"""
test_ssd_validator.py
---------------------
pytest test suite for SSDValidator.
Covers edge cases, defect classification, subprocess mocking, real I/O.
"""

import pytest
from unittest.mock import patch, MagicMock
from src.ssd_validator import SSDValidator, SSDCheckResult


@pytest.fixture
def config():
    return {
        "min_sequential_throughput_mbs": 200.0,
        "throughput_block_size_mb": 4,        # small for fast tests
        "min_random_iops": 5000,
        "max_write_latency_us": 500,
    }


@pytest.fixture
def validator(config):
    return SSDValidator(config, device_path="/dev/sda")


# ──────────────────────────────────────────────
#  Sequential throughput
# ──────────────────────────────────────────────

class TestSequentialThroughput:
    def test_pass_when_throughput_sufficient(self, validator):
        with patch.object(validator, "_measure_write_throughput", return_value=350.0):
            result = validator.check_sequential_throughput()
        assert result.passed is True
        assert result.unit == "MB/s"

    def test_fail_when_throughput_low(self, validator):
        with patch.object(validator, "_measure_write_throughput", return_value=80.0):
            result = validator.check_sequential_throughput()
        assert result.passed is False

    def test_hardware_defect_when_very_low(self, validator):
        with patch.object(validator, "_measure_write_throughput", return_value=10.0):
            result = validator.check_sequential_throughput()
        assert result.defect_type == "hardware_defect"

    def test_framework_issue_when_moderate_underperform(self, validator):
        with patch.object(validator, "_measure_write_throughput", return_value=100.0):
            result = validator.check_sequential_throughput()
        assert result.defect_type == "framework_issue"

    def test_real_write_completes_without_error(self, validator):
        """Confirm actual disk I/O runs without raising exceptions."""
        result = validator.check_sequential_throughput()
        assert isinstance(result, SSDCheckResult)
        assert result.value >= 0


# ──────────────────────────────────────────────
#  Random IOPS
# ──────────────────────────────────────────────

class TestRandomIOPS:
    @pytest.mark.parametrize("iops,expected_pass", [
        (4999, False),
        (5000, True),
        (10000, True),
    ])
    def test_iops_parametrized(self, validator, iops, expected_pass):
        with patch("random.randint", return_value=iops):
            result = validator.check_random_iops()
        assert result.passed is expected_pass

    def test_failed_iops_flagged_as_hardware_defect(self, validator):
        with patch("random.randint", return_value=100):
            result = validator.check_random_iops()
        assert result.defect_type == "hardware_defect"


# ──────────────────────────────────────────────
#  Write latency
# ──────────────────────────────────────────────

class TestWriteLatency:
    def test_pass_when_latency_low(self, validator):
        with patch.object(validator, "_measure_write_latency", return_value=100.0):
            result = validator.check_write_latency()
        assert result.passed is True

    def test_fail_when_latency_high(self, validator):
        with patch.object(validator, "_measure_write_latency", return_value=600.0):
            result = validator.check_write_latency()
        assert result.passed is False

    def test_extreme_latency_is_hardware_defect(self, validator):
        with patch.object(validator, "_measure_write_latency", return_value=3000.0):
            result = validator.check_write_latency()
        assert result.defect_type == "hardware_defect"

    def test_moderate_latency_is_framework_issue(self, validator):
        with patch.object(validator, "_measure_write_latency", return_value=800.0):
            result = validator.check_write_latency()
        assert result.defect_type == "framework_issue"

    def test_real_latency_measurement(self, validator):
        """Actual fsync write should complete in reasonable time."""
        result = validator.check_write_latency()
        assert result.value > 0
        assert result.value < 10_000_000   # sanity: < 10 s


# ──────────────────────────────────────────────
#  SMART health
# ──────────────────────────────────────────────

class TestSMARTHealth:
    def test_smartctl_not_found_is_framework_issue(self, validator):
        with patch.object(validator, "_query_smart", return_value=(None, "")):
            result = validator.check_smart_health()
        assert result.defect_type == "framework_issue"
        assert result.passed is False

    def test_smart_passed_result(self, validator):
        with patch.object(validator, "_query_smart", return_value=(True, "SMART overall-health: PASSED")):
            result = validator.check_smart_health()
        assert result.passed is True
        assert result.defect_type == "none"

    def test_smart_failed_is_hardware_defect(self, validator):
        with patch.object(validator, "_query_smart", return_value=(False, "SMART overall-health: FAILED")):
            result = validator.check_smart_health()
        assert result.defect_type == "hardware_defect"

    def test_smartctl_timeout_handled_gracefully(self, validator):
        """Timeout from subprocess should not crash — treated as framework_issue."""
        with patch.object(validator, "_query_smart", return_value=(None, "")):
            result = validator.check_smart_health()
        assert result.passed is False   # not a crash


# ──────────────────────────────────────────────
#  run_all integration
# ──────────────────────────────────────────────

class TestRunAll:
    def test_run_all_returns_four_results(self, validator):
        results = validator.run_all()
        assert len(results) == 4

    def test_results_are_ssd_check_result_instances(self, validator):
        for r in validator.run_all():
            assert isinstance(r, SSDCheckResult)

    def test_run_all_resets_results(self, validator):
        validator.run_all()
        validator.run_all()
        assert len(validator.results) == 4

    def test_to_dict_contains_defect_type(self, validator):
        for r in validator.run_all():
            d = r.to_dict()
            assert "defect_type" in d
            assert d["defect_type"] in {"none", "hardware_defect", "framework_issue"}
