"""
hardware_monitor.py
-------------------
Real hardware validation checks using psutil for CPU, RAM, Disk,
Network latency, Network bandwidth, Packet loss, and CPU Temperature.

Additions over v1:
  - psutil replaces all simulation stubs for CPU, RAM, Network
  - Temperature monitoring (psutil.sensors_temperatures)
  - Network bandwidth measurement (bytes sent/received per second)
  - Packet loss detection via ICMP ping subprocess
  - Graceful fallback when sensors are unavailable (Windows/VM)

Covers: server-level automation, system-level hardware validation,
        Python automation frameworks, networking engineering,
        debug logging, framework vs hardware defect distinction.
"""

import time
import random
import shutil
import socket
import subprocess
import platform
from dataclasses import dataclass, field
from src.logger import get_logger

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

logger = get_logger(__name__)


@dataclass
class CheckResult:
    """Represents the outcome of a single hardware validation check."""
    component: str
    metric: str
    value: float
    unit: str
    threshold: float
    passed: bool
    message: str
    source: str = "real"
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return self.__dict__


class HardwareMonitor:
    """
    Validates core hardware metrics against configurable thresholds.
    Uses psutil for real hardware readings where available,
    falls back to simulation stubs on unsupported platforms.
    """

    def __init__(self, config: dict):
        self.config = config
        self.results: list[CheckResult] = []
        self._os = platform.system()
        logger.info(
            "HardwareMonitor initialised | OS=%s | psutil=%s",
            self._os, PSUTIL_AVAILABLE
        )

    def check_cpu(self) -> CheckResult:
        """Validate real CPU utilisation via psutil."""
        threshold = self.config.get("cpu_threshold_percent", 85.0)
        if PSUTIL_AVAILABLE:
            cpu_usage = psutil.cpu_percent(interval=1)
            source = "real"
        else:
            cpu_usage = self._simulate_cpu_usage()
            source = "simulated"
            logger.warning("psutil unavailable — using simulated CPU value")
        passed = cpu_usage < threshold
        result = CheckResult(
            component="CPU", metric="utilisation",
            value=round(cpu_usage, 2), unit="%",
            threshold=threshold, passed=passed, source=source,
            message=(
                f"CPU at {cpu_usage:.1f}% [{source}] — within limit"
                if passed
                else f"CPU at {cpu_usage:.1f}% [{source}] — exceeds {threshold}% threshold"
            ),
        )
        self._log_and_store(result)
        return result

    def check_memory(self) -> CheckResult:
        """Validate real available RAM via psutil."""
        min_available_gb = self.config.get("min_memory_available_gb", 2.0)
        if PSUTIL_AVAILABLE:
            mem = psutil.virtual_memory()
            available_gb = mem.available / (1024 ** 3)
            total_gb = mem.total / (1024 ** 3)
            used_pct = mem.percent
            source = "real"
        else:
            available_gb = self._simulate_memory_available()
            total_gb = 16.0
            used_pct = 50.0
            source = "simulated"
        passed = available_gb >= min_available_gb
        result = CheckResult(
            component="RAM", metric="available",
            value=round(available_gb, 2), unit="GB",
            threshold=min_available_gb, passed=passed, source=source,
            message=(
                f"{available_gb:.1f}/{total_gb:.1f} GB available "
                f"({used_pct:.1f}% used) [{source}] — sufficient"
                if passed
                else f"Only {available_gb:.1f}/{total_gb:.1f} GB available "
                f"({used_pct:.1f}% used) [{source}] — below {min_available_gb} GB"
            ),
        )
        self._log_and_store(result)
        return result

    def check_disk(self, path: str = "/") -> CheckResult:
        """Validate real disk free space via shutil."""
        min_free_gb = self.config.get("min_disk_free_gb", 10.0)
        if self._os == "Windows" and path == "/":
            path = "C:\\"
        total, used, free = shutil.disk_usage(path)
        free_gb = free / (1024 ** 3)
        total_gb = total / (1024 ** 3)
        used_pct = round((used / total) * 100, 1)
        passed = free_gb >= min_free_gb
        result = CheckResult(
            component="Disk", metric="free_space",
            value=round(free_gb, 2), unit="GB",
            threshold=min_free_gb, passed=passed, source="real",
            message=(
                f"{free_gb:.1f}/{total_gb:.1f} GB free on '{path}' "
                f"({used_pct}% used) — OK"
                if passed
                else f"Only {free_gb:.1f}/{total_gb:.1f} GB free on '{path}' "
                f"({used_pct}% used) — below {min_free_gb} GB"
            ),
        )
        self._log_and_store(result)
        return result

    def check_network_latency(self) -> CheckResult:
        """Validate real network latency via TCP socket connect."""
        max_latency_ms = self.config.get("max_network_latency_ms", 100.0)
        host = self.config.get("latency_check_host", "8.8.8.8")
        port = self.config.get("latency_check_port", 53)
        latency_ms, source = self._measure_tcp_latency(host, port)
        passed = latency_ms <= max_latency_ms
        result = CheckResult(
            component="Network", metric="latency",
            value=round(latency_ms, 2), unit="ms",
            threshold=max_latency_ms, passed=passed, source=source,
            message=(
                f"Latency {latency_ms:.1f} ms to {host} [{source}] — acceptable"
                if passed
                else f"Latency {latency_ms:.1f} ms to {host} [{source}] "
                f"— exceeds {max_latency_ms} ms limit"
            ),
        )
        self._log_and_store(result)
        return result

    def check_network_bandwidth(self) -> CheckResult:
        """Measure real network throughput via psutil counter sampling."""
        min_bandwidth_mbs = self.config.get("min_network_bandwidth_mbs", 0.1)
        sample_interval = self.config.get("bandwidth_sample_seconds", 1)
        if PSUTIL_AVAILABLE:
            before = psutil.net_io_counters()
            time.sleep(sample_interval)
            after = psutil.net_io_counters()
            bytes_delta = (
                (after.bytes_sent - before.bytes_sent) +
                (after.bytes_recv - before.bytes_recv)
            )
            bandwidth_mbs = round((bytes_delta / (1024 ** 2)) / max(sample_interval, 0.001), 3)
            source = "real"
        else:
            bandwidth_mbs = round(random.uniform(0.05, 50.0), 3)
            source = "simulated"
        passed = bandwidth_mbs >= min_bandwidth_mbs
        result = CheckResult(
            component="Network", metric="bandwidth",
            value=bandwidth_mbs, unit="MB/s",
            threshold=min_bandwidth_mbs, passed=passed, source=source,
            message=(
                f"Bandwidth {bandwidth_mbs} MB/s [{source}] — sufficient"
                if passed
                else f"Bandwidth only {bandwidth_mbs} MB/s [{source}] "
                f"— below {min_bandwidth_mbs} MB/s minimum"
            ),
        )
        self._log_and_store(result)
        return result

    def check_packet_loss(self) -> CheckResult:
        """Measure real packet loss via system ping command."""
        max_loss_pct = self.config.get("max_packet_loss_pct", 5.0)
        host = self.config.get("ping_host", "8.8.8.8")
        count = self.config.get("ping_count", 10)
        loss_pct, source = self._measure_packet_loss(host, count)
        passed = loss_pct <= max_loss_pct
        result = CheckResult(
            component="Network", metric="packet_loss",
            value=round(loss_pct, 1), unit="%",
            threshold=max_loss_pct, passed=passed, source=source,
            message=(
                f"Packet loss {loss_pct:.1f}% to {host} [{source}] — acceptable"
                if passed
                else f"Packet loss {loss_pct:.1f}% to {host} [{source}] "
                f"— exceeds {max_loss_pct}% threshold"
            ),
        )
        self._log_and_store(result)
        return result

    def check_temperature(self) -> CheckResult:
        """Validate CPU temperature via psutil sensors."""
        max_temp_c = self.config.get("max_cpu_temp_celsius", 80.0)
        temp_c, source = self._read_cpu_temperature()
        if temp_c is None:
            result = CheckResult(
                component="CPU", metric="temperature",
                value=0.0, unit="°C",
                threshold=max_temp_c, passed=False, source="unavailable",
                message=(
                    "Temperature sensors unavailable on this platform "
                    "(framework_issue — not a hardware defect)"
                ),
            )
            logger.warning(
                "Temperature sensors not available on %s — framework_issue", self._os
            )
        else:
            passed = temp_c < max_temp_c
            result = CheckResult(
                component="CPU", metric="temperature",
                value=round(temp_c, 1), unit="°C",
                threshold=max_temp_c, passed=passed, source=source,
                message=(
                    f"CPU temp {temp_c:.1f}°C [{source}] — within safe range"
                    if passed
                    else f"CPU temp {temp_c:.1f}°C [{source}] "
                    f"— exceeds {max_temp_c}°C threshold (hardware_defect risk)"
                ),
            )
        self._log_and_store(result)
        return result

    def run_all(self) -> list[CheckResult]:
        """Execute all validation checks and return results."""
        logger.info("Starting full hardware validation sweep")
        self.results.clear()
        self.check_cpu()
        self.check_memory()
        self.check_disk()
        self.check_network_latency()
        self.check_network_bandwidth()
        self.check_packet_loss()
        self.check_temperature()
        passed = sum(1 for r in self.results if r.passed)
        logger.info("Validation complete: %d/%d checks passed", passed, len(self.results))
        return self.results

    def _log_and_store(self, result: CheckResult) -> None:
        if result.passed:
            logger.info("[PASS] %s.%s — %s", result.component, result.metric, result.message)
        else:
            logger.warning("[FAIL] %s.%s — %s", result.component, result.metric, result.message)
        self.results.append(result)

    def _measure_tcp_latency(self, host: str, port: int):
        try:
            start = time.perf_counter()
            sock = socket.create_connection((host, port), timeout=5)
            elapsed_ms = (time.perf_counter() - start) * 1000
            sock.close()
            return round(elapsed_ms, 2), "real"
        except (socket.timeout, OSError) as exc:
            logger.warning("TCP latency check failed: %s — using simulation", exc)
            return self._simulate_network_latency(), "simulated"

    def _measure_packet_loss(self, host: str, count: int):
        try:
            if self._os == "Windows":
                cmd = ["ping", "-n", str(count), host]
            else:
                cmd = ["ping", "-c", str(count), "-W", "2", host]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            output = proc.stdout + proc.stderr
            if self._os == "Windows":
                for line in output.splitlines():
                    if "Lost" in line:
                        parts = line.split()
                        for i, p in enumerate(parts):
                            if p == "Lost":
                                lost = int(parts[i + 2].strip(","))
                                return round((lost / count) * 100, 1), "real"
            else:
                for line in output.splitlines():
                    if "packet loss" in line:
                        pct = float(line.split("%")[0].split()[-1])
                        return pct, "real"
            return 0.0, "real"
        except (subprocess.TimeoutExpired, OSError, ValueError) as exc:
            logger.warning("Packet loss check failed: %s — using simulation", exc)
            return random.uniform(0.0, 10.0), "simulated"

    def _read_cpu_temperature(self):
        if not PSUTIL_AVAILABLE:
            return None, "unavailable"
        try:
            temps = psutil.sensors_temperatures()
            if not temps:
                return None, "unavailable"
            for key in ("coretemp", "cpu_thermal", "acpitz", "k10temp"):
                if key in temps and temps[key]:
                    avg = sum(r.current for r in temps[key]) / len(temps[key])
                    return avg, "real"
            first_key = next(iter(temps))
            if temps[first_key]:
                return temps[first_key][0].current, "real"
        except (AttributeError, OSError) as exc:
            logger.warning("Temperature read failed: %s", exc)
        return None, "unavailable"

    def _simulate_cpu_usage(self) -> float:
        return random.uniform(10.0, 95.0)

    def _simulate_memory_available(self) -> float:
        return random.uniform(0.5, 16.0)

    def _simulate_network_latency(self) -> float:
        return random.uniform(5.0, 150.0)
