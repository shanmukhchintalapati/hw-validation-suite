"""
hardware_monitor.py
-------------------
Simulates hardware validation checks for CPU, RAM, Disk, and Network.
Covers: server-level automation, system-level hardware validation workflows,
        Python automation frameworks, and debug logging.
"""

import time
import random
import shutil
from dataclasses import dataclass, field
from src.logger import get_logger

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
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return self.__dict__


class HardwareMonitor:
    """
    Validates core hardware metrics against configurable thresholds.
    In a real deployment, replace simulated values with psutil calls.
    """

    def __init__(self, config: dict):
        self.config = config
        self.results: list[CheckResult] = []
        logger.info("HardwareMonitor initialised with config: %s", config)

    # ------------------------------------------------------------------ #
    #  CPU                                                                 #
    # ------------------------------------------------------------------ #
    def check_cpu(self) -> CheckResult:
        """Validate CPU utilisation is below the configured threshold."""
        threshold = self.config.get("cpu_threshold_percent", 85.0)

        # Simulate: replace with psutil.cpu_percent(interval=1) in production
        cpu_usage = self._simulate_cpu_usage()

        passed = cpu_usage < threshold
        result = CheckResult(
            component="CPU",
            metric="utilisation",
            value=round(cpu_usage, 2),
            unit="%",
            threshold=threshold,
            passed=passed,
            message=(
                f"CPU at {cpu_usage:.1f}% — within limit"
                if passed
                else f"CPU at {cpu_usage:.1f}% — exceeds {threshold}% threshold"
            ),
        )
        self._log_and_store(result)
        return result

    # ------------------------------------------------------------------ #
    #  RAM                                                                 #
    # ------------------------------------------------------------------ #
    def check_memory(self) -> CheckResult:
        """Validate available RAM is above the minimum threshold."""
        min_available_gb = self.config.get("min_memory_available_gb", 2.0)

        # Simulate: replace with psutil.virtual_memory().available in production
        available_gb = self._simulate_memory_available()

        passed = available_gb >= min_available_gb
        result = CheckResult(
            component="RAM",
            metric="available",
            value=round(available_gb, 2),
            unit="GB",
            threshold=min_available_gb,
            passed=passed,
            message=(
                f"{available_gb:.1f} GB available — sufficient"
                if passed
                else f"Only {available_gb:.1f} GB available — below {min_available_gb} GB minimum"
            ),
        )
        self._log_and_store(result)
        return result

    # ------------------------------------------------------------------ #
    #  Disk / Storage                                                      #
    # ------------------------------------------------------------------ #
    def check_disk(self, path: str = "/") -> CheckResult:
        """Validate disk free space is above the configured minimum."""
        min_free_gb = self.config.get("min_disk_free_gb", 10.0)

        total, used, free = shutil.disk_usage(path)
        free_gb = free / (1024 ** 3)

        passed = free_gb >= min_free_gb
        result = CheckResult(
            component="Disk",
            metric="free_space",
            value=round(free_gb, 2),
            unit="GB",
            threshold=min_free_gb,
            passed=passed,
            message=(
                f"{free_gb:.1f} GB free on '{path}' — OK"
                if passed
                else f"Only {free_gb:.1f} GB free on '{path}' — below {min_free_gb} GB"
            ),
        )
        self._log_and_store(result)
        return result

    # ------------------------------------------------------------------ #
    #  Network                                                             #
    # ------------------------------------------------------------------ #
    def check_network_latency(self) -> CheckResult:
        """Validate simulated network round-trip latency."""
        max_latency_ms = self.config.get("max_network_latency_ms", 100.0)

        latency_ms = self._simulate_network_latency()

        passed = latency_ms <= max_latency_ms
        result = CheckResult(
            component="Network",
            metric="latency",
            value=round(latency_ms, 2),
            unit="ms",
            threshold=max_latency_ms,
            passed=passed,
            message=(
                f"Latency {latency_ms:.1f} ms — acceptable"
                if passed
                else f"Latency {latency_ms:.1f} ms — exceeds {max_latency_ms} ms limit"
            ),
        )
        self._log_and_store(result)
        return result

    # ------------------------------------------------------------------ #
    #  Run all checks                                                      #
    # ------------------------------------------------------------------ #
    def run_all(self) -> list[CheckResult]:
        """Execute every validation check and return results."""
        logger.info("Starting full hardware validation sweep")
        self.results.clear()
        self.check_cpu()
        self.check_memory()
        self.check_disk()
        self.check_network_latency()
        passed = sum(1 for r in self.results if r.passed)
        logger.info("Validation complete: %d/%d checks passed", passed, len(self.results))
        return self.results

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                    #
    # ------------------------------------------------------------------ #
    def _log_and_store(self, result: CheckResult) -> None:
        if result.passed:
            logger.info("[PASS] %s — %s", result.component, result.message)
        else:
            logger.warning("[FAIL] %s — %s", result.component, result.message)
        self.results.append(result)

    # Simulation stubs — swap for real psutil calls in production
    def _simulate_cpu_usage(self) -> float:
        return random.uniform(10.0, 95.0)

    def _simulate_memory_available(self) -> float:
        return random.uniform(0.5, 16.0)

    def _simulate_network_latency(self) -> float:
        return random.uniform(5.0, 150.0)
