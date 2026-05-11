"""
ssd_validator.py
----------------
Simulates SSD / NVMe validation: sequential throughput, random IOPS,
latency, and a SMART-style health check.

Covers: SSD validation (mandatory skill), server storage subsystems,
        debugging framework vs hardware defects, subprocess usage.
"""

import os
import time
import random
import subprocess
import tempfile
from dataclasses import dataclass, field
from src.logger import get_logger

logger = get_logger(__name__)

SMART_ATTRIBUTES = [
    "Reallocated_Sector_Ct",
    "Power_On_Hours",
    "Wear_Leveling_Count",
    "Media_Wearout_Indicator",
    "Total_LBAs_Written",
]


@dataclass
class SSDCheckResult:
    """Result from a single SSD validation test."""
    test_name: str
    value: float
    unit: str
    threshold: float
    passed: bool
    defect_type: str          # "framework_issue" | "hardware_defect" | "none"
    message: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return self.__dict__


class SSDValidator:
    """
    Runs a battery of SSD validation tests.
    Distinguishes between framework issues (environment/config errors)
    and hardware firmware defects — a key skill in the job description.
    """

    def __init__(self, config: dict, device_path: str = "/dev/sda"):
        self.config = config
        self.device_path = device_path
        self.results: list[SSDCheckResult] = []
        logger.info("SSDValidator initialised for device: %s", device_path)

    # ------------------------------------------------------------------ #
    #  Sequential read/write throughput                                   #
    # ------------------------------------------------------------------ #
    def check_sequential_throughput(self) -> SSDCheckResult:
        """
        Validate sequential read throughput against minimum MB/s threshold.
        Uses a real temp-file write to measure actual disk speed.
        """
        min_throughput_mbs = self.config.get("min_sequential_throughput_mbs", 200.0)
        block_size = self.config.get("throughput_block_size_mb", 64)

        logger.debug("Running sequential throughput test (block=%d MB)", block_size)
        measured_mbs = self._measure_write_throughput(block_size)

        passed = measured_mbs >= min_throughput_mbs
        defect = "none" if passed else self._classify_throughput_defect(measured_mbs)

        result = SSDCheckResult(
            test_name="sequential_throughput",
            value=round(measured_mbs, 1),
            unit="MB/s",
            threshold=min_throughput_mbs,
            passed=passed,
            defect_type=defect,
            message=(
                f"Throughput {measured_mbs:.1f} MB/s — meets {min_throughput_mbs} MB/s minimum"
                if passed
                else f"Throughput {measured_mbs:.1f} MB/s — below minimum ({defect})"
            ),
        )
        self._log_and_store(result)
        return result

    # ------------------------------------------------------------------ #
    #  Random IOPS                                                        #
    # ------------------------------------------------------------------ #
    def check_random_iops(self) -> SSDCheckResult:
        """Validate random 4K IOPS (simulated for portability)."""
        min_iops = self.config.get("min_random_iops", 5000)
        measured_iops = random.randint(1000, 15000)   # sim: replace with fio in prod

        passed = measured_iops >= min_iops
        defect = "none" if passed else "hardware_defect"

        result = SSDCheckResult(
            test_name="random_4k_iops",
            value=float(measured_iops),
            unit="IOPS",
            threshold=float(min_iops),
            passed=passed,
            defect_type=defect,
            message=(
                f"{measured_iops} IOPS — meets {min_iops} minimum"
                if passed
                else f"{measured_iops} IOPS — below {min_iops} (likely {defect})"
            ),
        )
        self._log_and_store(result)
        return result

    # ------------------------------------------------------------------ #
    #  Write latency                                                       #
    # ------------------------------------------------------------------ #
    def check_write_latency(self) -> SSDCheckResult:
        """Validate average write latency (µs) is within spec."""
        max_latency_us = self.config.get("max_write_latency_us", 500)
        latency_us = self._measure_write_latency()

        passed = latency_us <= max_latency_us
        defect = "none" if passed else self._classify_latency_defect(latency_us)

        result = SSDCheckResult(
            test_name="write_latency",
            value=round(latency_us, 1),
            unit="µs",
            threshold=float(max_latency_us),
            passed=passed,
            defect_type=defect,
            message=(
                f"Write latency {latency_us:.0f} µs — within spec"
                if passed
                else f"Write latency {latency_us:.0f} µs — exceeds {max_latency_us} µs ({defect})"
            ),
        )
        self._log_and_store(result)
        return result

    # ------------------------------------------------------------------ #
    #  SMART health check                                                  #
    # ------------------------------------------------------------------ #
    def check_smart_health(self) -> SSDCheckResult:
        """
        Attempt a real SMART query via smartctl; fall back to simulation.
        Demonstrates subprocess usage and framework vs hardware defect logic.
        """
        logger.debug("Querying SMART health for %s", self.device_path)
        smart_ok, raw_output = self._query_smart()

        if smart_ok is None:
            # smartctl not available — framework issue, not a hardware defect
            logger.warning("smartctl unavailable — marking as framework_issue")
            result = SSDCheckResult(
                test_name="smart_health",
                value=0.0,
                unit="status",
                threshold=1.0,
                passed=False,
                defect_type="framework_issue",
                message="smartctl not found — install smartmontools to enable SMART checks",
            )
        else:
            result = SSDCheckResult(
                test_name="smart_health",
                value=1.0 if smart_ok else 0.0,
                unit="status",
                threshold=1.0,
                passed=smart_ok,
                defect_type="none" if smart_ok else "hardware_defect",
                message="SMART reports PASSED" if smart_ok else "SMART reports FAILED — hardware defect",
            )
        self._log_and_store(result)
        return result

    # ------------------------------------------------------------------ #
    #  Run all                                                             #
    # ------------------------------------------------------------------ #
    def run_all(self) -> list[SSDCheckResult]:
        logger.info("Starting SSD validation suite")
        self.results.clear()
        self.check_sequential_throughput()
        self.check_random_iops()
        self.check_write_latency()
        self.check_smart_health()
        passed = sum(1 for r in self.results if r.passed)
        logger.info("SSD validation complete: %d/%d checks passed", passed, len(self.results))
        return self.results

    # ------------------------------------------------------------------ #
    #  Helpers                                                             #
    # ------------------------------------------------------------------ #
    def _measure_write_throughput(self, block_size_mb: int) -> float:
        """Write a temp file and measure actual throughput."""
        data = b"x" * (block_size_mb * 1024 * 1024)
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name
        try:
            start = time.perf_counter()
            with open(tmp_path, "wb") as f:
                f.write(data)
            elapsed = time.perf_counter() - start
            return (block_size_mb / elapsed) if elapsed > 0 else 999.0
        except OSError as exc:
            logger.error("Throughput test I/O error: %s — framework_issue", exc)
            return 0.0
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def _measure_write_latency(self) -> float:
        """Measure latency of a small synchronous write in microseconds."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name
        try:
            start = time.perf_counter()
            with open(tmp_path, "wb") as f:
                f.write(b"latency_probe")
                f.flush()
                os.fsync(f.fileno())
            return (time.perf_counter() - start) * 1_000_000
        except OSError as exc:
            logger.error("Latency probe I/O error: %s", exc)
            return 9999.0
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def _query_smart(self):
        """Run smartctl and return (health_ok: bool | None, raw_output: str)."""
        try:
            proc = subprocess.run(
                ["smartctl", "-H", self.device_path],
                capture_output=True, text=True, timeout=10,
            )
            raw = proc.stdout + proc.stderr
            return ("PASSED" in raw or "OK" in raw), raw
        except FileNotFoundError:
            return None, ""
        except subprocess.TimeoutExpired:
            logger.error("smartctl timed out — likely framework_issue")
            return None, ""

    def _classify_throughput_defect(self, mbs: float) -> str:
        """Heuristic: very low throughput → hardware defect; moderate → framework issue."""
        return "hardware_defect" if mbs < 50 else "framework_issue"

    def _classify_latency_defect(self, latency_us: float) -> str:
        return "hardware_defect" if latency_us > 2000 else "framework_issue"

    def _log_and_store(self, result: SSDCheckResult) -> None:
        if result.passed:
            logger.info("[PASS] %s — %s", result.test_name, result.message)
        else:
            logger.warning("[FAIL] %s — %s | defect_type=%s",
                           result.test_name, result.message, result.defect_type)
        self.results.append(result)
