"""
test_hardware_monitor.py
------------------------
pytest test suite for HardwareMonitor — covers all 7 checks:
CPU, RAM, Disk, Network latency, Network bandwidth, Packet loss, Temperature.
"""

import pytest
from unittest.mock import patch, MagicMock
from src.hardware_monitor import HardwareMonitor, CheckResult


@pytest.fixture
def default_config():
    return {
        "cpu_threshold_percent": 85.0,
        "min_memory_available_gb": 2.0,
        "min_disk_free_gb": 10.0,
        "max_network_latency_ms": 100.0,
        "min_network_bandwidth_mbs": 0.1,
        "max_packet_loss_pct": 5.0,
        "max_cpu_temp_celsius": 80.0,
        "ping_host": "8.8.8.8",
        "ping_count": 4,
        "bandwidth_sample_seconds": 0,
    }


@pytest.fixture
def monitor(default_config):
    return HardwareMonitor(default_config)


# ──────────────────────────────────────────────
#  CPU tests
# ──────────────────────────────────────────────

class TestCPUCheck:
    def test_cpu_pass_when_below_threshold(self, monitor):
        with patch("src.hardware_monitor.PSUTIL_AVAILABLE", True), \
             patch("src.hardware_monitor.psutil") as mock_psutil:
            mock_psutil.cpu_percent.return_value = 50.0
            result = monitor.check_cpu()
        assert result.passed is True
        assert result.source == "real"

    def test_cpu_fail_when_above_threshold(self, monitor):
        with patch("src.hardware_monitor.PSUTIL_AVAILABLE", True), \
             patch("src.hardware_monitor.psutil") as mock_psutil:
            mock_psutil.cpu_percent.return_value = 90.0
            result = monitor.check_cpu()
        assert result.passed is False

    def test_cpu_falls_back_to_simulation(self, monitor):
        with patch("src.hardware_monitor.PSUTIL_AVAILABLE", False), \
             patch.object(monitor, "_simulate_cpu_usage", return_value=40.0):
            result = monitor.check_cpu()
        assert result.source == "simulated"

    @pytest.mark.parametrize("cpu_val,expected_pass", [
        (0.0, True), (84.9, True), (85.0, False), (100.0, False)
    ])
    def test_cpu_parametrized(self, monitor, cpu_val, expected_pass):
        with patch("src.hardware_monitor.PSUTIL_AVAILABLE", True), \
             patch("src.hardware_monitor.psutil") as mock_psutil:
            mock_psutil.cpu_percent.return_value = cpu_val
            result = monitor.check_cpu()
        assert result.passed is expected_pass


# ──────────────────────────────────────────────
#  Memory tests
# ──────────────────────────────────────────────

class TestMemoryCheck:
    def _mock_mem(self, available_gb, total_gb=16.0, percent=50.0):
        mem = MagicMock()
        mem.available = available_gb * (1024 ** 3)
        mem.total = total_gb * (1024 ** 3)
        mem.percent = percent
        return mem

    def test_memory_pass_when_sufficient(self, monitor):
        with patch("src.hardware_monitor.PSUTIL_AVAILABLE", True), \
             patch("src.hardware_monitor.psutil") as mock_psutil:
            mock_psutil.virtual_memory.return_value = self._mock_mem(8.0)
            result = monitor.check_memory()
        assert result.passed is True
        assert result.source == "real"

    def test_memory_fail_when_low(self, monitor):
        with patch("src.hardware_monitor.PSUTIL_AVAILABLE", True), \
             patch("src.hardware_monitor.psutil") as mock_psutil:
            mock_psutil.virtual_memory.return_value = self._mock_mem(0.5)
            result = monitor.check_memory()
        assert result.passed is False

    def test_memory_falls_back_to_simulation(self, monitor):
        with patch("src.hardware_monitor.PSUTIL_AVAILABLE", False), \
             patch.object(monitor, "_simulate_memory_available", return_value=4.0):
            result = monitor.check_memory()
        assert result.source == "simulated"

    @pytest.mark.parametrize("avail_gb,expected_pass", [
        (0.0, False), (1.9, False), (2.0, True), (16.0, True)
    ])
    def test_memory_parametrized(self, monitor, avail_gb, expected_pass):
        with patch("src.hardware_monitor.PSUTIL_AVAILABLE", True), \
             patch("src.hardware_monitor.psutil") as mock_psutil:
            mock_psutil.virtual_memory.return_value = self._mock_mem(avail_gb)
            result = monitor.check_memory()
        assert result.passed is expected_pass


# ──────────────────────────────────────────────
#  Disk tests
# ──────────────────────────────────────────────

class TestDiskCheck:
    def test_disk_uses_real_shutil(self, monitor):
        result = monitor.check_disk()
        assert isinstance(result, CheckResult)
        assert result.source == "real"
        assert result.value >= 0

    def test_disk_fail_when_below_threshold(self, monitor):
        free_bytes = int(2 * 1024 ** 3)
        with patch("shutil.disk_usage", return_value=(100 * 1024**3, 98 * 1024**3, free_bytes)):
            result = monitor.check_disk()
        assert result.passed is False


# ──────────────────────────────────────────────
#  Network latency tests
# ──────────────────────────────────────────────

class TestNetworkLatency:
    def test_pass_when_low_latency(self, monitor):
        with patch.object(monitor, "_measure_tcp_latency", return_value=(20.0, "real")):
            result = monitor.check_network_latency()
        assert result.passed is True
        assert result.source == "real"

    def test_fail_when_high_latency(self, monitor):
        with patch.object(monitor, "_measure_tcp_latency", return_value=(200.0, "real")):
            result = monitor.check_network_latency()
        assert result.passed is False

    def test_falls_back_to_simulated_on_error(self, monitor):
        with patch.object(monitor, "_measure_tcp_latency", return_value=(30.0, "simulated")):
            result = monitor.check_network_latency()
        assert result.source == "simulated"

    @pytest.mark.parametrize("latency,expected_pass", [
        (10.0, True), (100.0, True), (100.1, False), (500.0, False)
    ])
    def test_latency_parametrized(self, monitor, latency, expected_pass):
        with patch.object(monitor, "_measure_tcp_latency", return_value=(latency, "real")):
            result = monitor.check_network_latency()
        assert result.passed is expected_pass


# ──────────────────────────────────────────────
#  Network bandwidth tests
# ──────────────────────────────────────────────

class TestNetworkBandwidth:
    def _mock_counters(self, sent, recv):
        c = MagicMock()
        c.bytes_sent = sent
        c.bytes_recv = recv
        return c

    def test_pass_when_bandwidth_sufficient(self, monitor):
        before = self._mock_counters(0, 0)
        after = self._mock_counters(5 * 1024 * 1024, 5 * 1024 * 1024)
        with patch("src.hardware_monitor.PSUTIL_AVAILABLE", True), \
             patch("src.hardware_monitor.psutil") as mock_psutil, \
             patch("time.sleep"):
            mock_psutil.net_io_counters.side_effect = [before, after]
            result = monitor.check_network_bandwidth()
        assert result.passed is True
        assert result.source == "real"

    def test_falls_back_to_simulation(self, monitor):
        with patch("src.hardware_monitor.PSUTIL_AVAILABLE", False):
            result = monitor.check_network_bandwidth()
        assert result.source == "simulated"


# ──────────────────────────────────────────────
#  Packet loss tests
# ──────────────────────────────────────────────

class TestPacketLoss:
    def test_pass_when_no_loss(self, monitor):
        with patch.object(monitor, "_measure_packet_loss", return_value=(0.0, "real")):
            result = monitor.check_packet_loss()
        assert result.passed is True

    def test_fail_when_high_loss(self, monitor):
        with patch.object(monitor, "_measure_packet_loss", return_value=(20.0, "real")):
            result = monitor.check_packet_loss()
        assert result.passed is False

    @pytest.mark.parametrize("loss,expected_pass", [
        (0.0, True), (5.0, True), (5.1, False), (100.0, False)
    ])
    def test_packet_loss_parametrized(self, monitor, loss, expected_pass):
        with patch.object(monitor, "_measure_packet_loss", return_value=(loss, "real")):
            result = monitor.check_packet_loss()
        assert result.passed is expected_pass


# ──────────────────────────────────────────────
#  Temperature tests
# ──────────────────────────────────────────────

class TestTemperature:
    def test_pass_when_temp_normal(self, monitor):
        with patch.object(monitor, "_read_cpu_temperature", return_value=(55.0, "real")):
            result = monitor.check_temperature()
        assert result.passed is True
        assert result.source == "real"

    def test_fail_when_overheating(self, monitor):
        with patch.object(monitor, "_read_cpu_temperature", return_value=(90.0, "real")):
            result = monitor.check_temperature()
        assert result.passed is False
        assert "hardware_defect" in result.message

    def test_sensors_unavailable_is_framework_issue(self, monitor):
        with patch.object(monitor, "_read_cpu_temperature", return_value=(None, "unavailable")):
            result = monitor.check_temperature()
        assert result.passed is False
        assert "framework_issue" in result.message
        assert result.source == "unavailable"

    @pytest.mark.parametrize("temp,expected_pass", [
        (40.0, True), (79.9, True), (80.0, False), (95.0, False)
    ])
    def test_temperature_parametrized(self, monitor, temp, expected_pass):
        with patch.object(monitor, "_read_cpu_temperature", return_value=(temp, "real")):
            result = monitor.check_temperature()
        assert result.passed is expected_pass


# ──────────────────────────────────────────────
#  run_all integration
# ──────────────────────────────────────────────

class TestRunAll:
    def test_run_all_returns_seven_results(self, monitor):
        with patch.object(monitor, "_measure_tcp_latency", return_value=(20.0, "real")), \
             patch.object(monitor, "_measure_packet_loss", return_value=(0.0, "real")), \
             patch.object(monitor, "_read_cpu_temperature", return_value=(55.0, "real")), \
             patch("src.hardware_monitor.PSUTIL_AVAILABLE", True), \
             patch("src.hardware_monitor.psutil") as mock_psutil, \
             patch("time.sleep"):
            mock_psutil.cpu_percent.return_value = 50.0
            mem = MagicMock()
            mem.available = 8 * 1024 ** 3
            mem.total = 16 * 1024 ** 3
            mem.percent = 50.0
            mock_psutil.virtual_memory.return_value = mem
            c = MagicMock()
            c.bytes_sent = 0
            c.bytes_recv = 0
            mock_psutil.net_io_counters.return_value = c
            results = monitor.run_all()
        assert len(results) == 7

    def test_run_all_clears_previous_results(self, monitor):
        with patch.object(monitor, "_measure_tcp_latency", return_value=(20.0, "real")), \
             patch.object(monitor, "_measure_packet_loss", return_value=(0.0, "real")), \
             patch.object(monitor, "_read_cpu_temperature", return_value=(55.0, "real")), \
             patch("src.hardware_monitor.PSUTIL_AVAILABLE", False), \
             patch("time.sleep"):
            monitor.run_all()
            monitor.run_all()
        assert len(monitor.results) == 7

    def test_all_results_are_check_result_instances(self, monitor):
        with patch.object(monitor, "_measure_tcp_latency", return_value=(20.0, "real")), \
             patch.object(monitor, "_measure_packet_loss", return_value=(0.0, "real")), \
             patch.object(monitor, "_read_cpu_temperature", return_value=(None, "unavailable")), \
             patch("src.hardware_monitor.PSUTIL_AVAILABLE", False), \
             patch("time.sleep"):
            results = monitor.run_all()
        for r in results:
            assert isinstance(r, CheckResult)

    def test_result_has_source_field(self, monitor):
        with patch.object(monitor, "_measure_tcp_latency", return_value=(20.0, "real")), \
             patch.object(monitor, "_measure_packet_loss", return_value=(0.0, "real")), \
             patch.object(monitor, "_read_cpu_temperature", return_value=(None, "unavailable")), \
             patch("src.hardware_monitor.PSUTIL_AVAILABLE", False), \
             patch("time.sleep"):
            results = monitor.run_all()
        for r in results:
            assert "source" in r.to_dict()
            assert r.source in ("real", "simulated", "unavailable")
