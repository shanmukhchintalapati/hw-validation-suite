# hw-validation-suite

A production-style Python automation framework for real hardware and SSD validation,
built as a portfolio project demonstrating skills for hardware validation engineering roles.

![CI](https://github.com/shanmukhchintalapati/hw-validation-suite/actions/workflows/ci.yml/badge.svg)

---

## What This Project Covers

| Industry Validation Standard | Where It's Demonstrated |
|---|---|
| Hardware validation automation framework | `framework_runner.py` — orchestrates all validators with retry logic |
| Real hardware metrics via psutil | `hardware_monitor.py` — real CPU, RAM, network readings (not simulated) |
| Automated test case design and execution | `tests/` — 98 pytest tests with fixtures, mocks, parametrize |
| Python automation framework development | `HardwareMonitor` + `SSDValidator` — modular, config-driven |
| System-level hardware integration | Real `psutil`, `shutil.disk_usage`, `os.fsync`, `subprocess` for SMART |
| Debug and defect classification | `defect_type` field in every SSD result (`framework_issue` / `hardware_defect`) |
| Server memory, storage and network validation | CPU, RAM, Disk, Network latency, Bandwidth, Packet loss, SSD throughput, IOPS, latency, SMART, Temperature |
| Enterprise persistence and trend analysis | `database.py` — SQLite stores every run, enables degradation detection |
| Real-time alerting | `alert.py` — email alerts when `hardware_defect` is detected |
| Live monitoring dashboard | `dashboard.py` — auto-refreshing HTML dashboard with run history |
| Automation documentation and user guides | This README + inline docstrings |
| Test coverage and continuous reporting | HTML + CSV reports, GitHub Actions CI with coverage |
| Cross-platform scripting | `bootstrap.ps1` — PowerShell setup script |

---

## Project Structure
```
hw-validation-suite/
├── src/
│   ├── hardware_monitor.py    # CPU, RAM, Disk, Network latency, Bandwidth, Packet loss, Temperature
│   ├── ssd_validator.py       # SSD throughput, IOPS, write latency, SMART health
│   ├── framework_runner.py    # Orchestrator with retry, DB save, alerts, dashboard
│   ├── logger.py              # Rotating file + console + JSON logging
│   ├── report_generator.py    # HTML and CSV report output
│   ├── database.py            # SQLite persistence — run history and trend analysis
│   ├── alert.py               # Email alert system for hardware_defect failures
│   └── dashboard.py           # Live auto-refreshing HTML monitoring dashboard
├── tests/
│   ├── test_hardware_monitor.py   # 73 tests — all 7 hardware checks
│   ├── test_ssd_validator.py      # 17 tests — SSD validation
│   ├── test_framework_runner.py   # 9 tests — orchestration and retry logic
│   ├── test_database.py           # 12 tests — SQLite persistence
│   ├── test_alert.py              # 9 tests — email alert logic
│   └── test_dashboard.py          # 4 tests — dashboard generation
├── reports/                   # Auto-generated HTML/CSV reports + dashboard
├── logs/                      # Rotating log files
├── .github/workflows/ci.yml   # GitHub Actions CI
├── config.yaml                # All thresholds, configurable
├── bootstrap.ps1              # PowerShell setup script
└── requirements.txt
```

## Quick Start

### Prerequisites
- Python 3.11+
- pip

### Install
```bash
git clone https://github.com/shanmukhchintalapati/hw-validation-suite.git
cd hw-validation-suite
pip install -r requirements.txt
```

### Run the full validation suite
```bash
python -m src.framework_runner
```

This runs all 11 checks, saves results to the SQLite database, generates HTML + CSV reports,
updates the live dashboard, and sends email alerts if any hardware defects are found.

### Run tests
```bash
pytest tests/ -v
```

### Run tests with coverage
```bash
pytest tests/ --cov=src --cov-report=term-missing
```

### View live dashboard
After running the suite, open `reports/dashboard.html` in any browser.
The dashboard auto-refreshes every 30 seconds and shows run history, pass rates,
hardware defect counts, and a bar chart of the latest check values.

---

## What Gets Checked — 11 Checks Total

### Hardware Monitor (7 checks)
| Check | What It Measures | Data Source |
|---|---|---|
| CPU utilisation | Is the processor overloaded? | `psutil.cpu_percent()` — real |
| RAM available | Is there enough free memory? | `psutil.virtual_memory()` — real |
| Disk free space | Is the drive about to fill up? | `shutil.disk_usage()` — real |
| Network latency | TCP round-trip time to 8.8.8.8 | `socket.create_connection()` — real |
| Network bandwidth | Combined send + receive throughput | `psutil.net_io_counters()` — real |
| Packet loss | ICMP ping packet loss % | `subprocess ping` — real |
| CPU temperature | Thermal sensor reading | `psutil.sensors_temperatures()` — real |

### SSD Validator (4 checks)
| Check | What It Measures | Data Source |
|---|---|---|
| Sequential throughput | Write speed in MB/s | Real temp file write + timer |
| Random IOPS | 4K random I/O operations/sec | Simulated (replace with `fio` in production) |
| Write latency | Single write latency in µs | Real `os.fsync()` measurement |
| SMART health | Drive health status | `smartctl` subprocess — real |

---

## Configuration

Edit `config.yaml` to adjust all thresholds without touching source code:

```yaml
# CPU
cpu_threshold_percent: 85.0        # alert if CPU > 85%
max_cpu_temp_celsius: 80.0         # alert if CPU temp > 80°C

# Memory
min_memory_available_gb: 2.0       # alert if RAM available < 2 GB

# Disk
min_disk_free_gb: 10.0             # alert if disk free < 10 GB

# Network
max_network_latency_ms: 100.0      # alert if TCP latency > 100 ms
min_network_bandwidth_mbs: 0.1     # alert if bandwidth < 0.1 MB/s
max_packet_loss_pct: 5.0           # alert if packet loss > 5%

# SSD
min_sequential_throughput_mbs: 200 # alert if SSD throughput < 200 MB/s
max_write_latency_us: 500          # alert if write latency > 500 µs

# Retry
max_retries: 2                     # retry failed checks this many times

# Email alerts (optional)
alert_enabled: false               # set to true to enable email alerts
alert_smtp_host: "smtp.gmail.com"
alert_sender: "your@email.com"
alert_recipients: ["team@company.com"]
```

---

## Architecture
```
config.yaml
│
▼
framework_runner.py
├──► HardwareMonitor  ──► CheckResult(s)       [7 checks]
│         └── psutil / socket / subprocess
├──► SSDValidator     ──► SSDCheckResult(s)    [4 checks]
│         └── real I/O + smartctl
│
├──► logger.py              (rotating file + console)
├──► report_generator.py   ──► reports/report_*.html + .csv
├──► database.py           ──► reports/validation_history.db
├──► alert.py              ──► email (if hardware_defect found)
└──► dashboard.py          ──► reports/dashboard.html
```
---

## Defect Classification

`SSDValidator` distinguishes between two failure categories:

| `defect_type` | Meaning | Example |
|---|---|---|
| `framework_issue` | Problem in the test environment or config | `smartctl` not installed, I/O permission error, moderate throughput drop |
| `hardware_defect` | Problem with the physical device | Very low throughput (<50 MB/s), SMART failure, extreme latency |
| `none` | Check passed | — |

`HardwareMonitor` also classifies temperature sensor unavailability as `framework_issue`
rather than a hardware problem, and falls back gracefully to simulation when `psutil`
is unavailable.

---

## SQLite Database — Trend Analysis

Every run is persisted to `reports/validation_history.db`. This enables:

- **Degradation detection** — is SSD throughput gradually declining?
- **Defect reporting** — how many `hardware_defect` vs `framework_issue` failures total?
- **Historical comparison** — compare this run's pass rate against the last 20 runs

```python
from src.database import get_trend, get_defect_summary

# See if CPU load has been rising over the last 20 runs
trend = get_trend("CPU", "utilisation", limit=20)

# Count hardware defects vs framework issues across all runs
summary = get_defect_summary()
```

---

## Email Alerts

When `alert_enabled: true` in `config.yaml`, the framework automatically sends an email
alert when any `hardware_defect` is detected. Framework issues do not trigger alerts —
only real hardware problems do.

The alert includes:
- Full pass/fail summary in the email body
- HTML report attached for detailed analysis
- Defect type classification for each failed check

Set `SMTP_PASSWORD` as an environment variable — never hardcode credentials.

---

## Logging

Logs are written to `logs/hw_validation.log` with automatic rotation (5 MB × 3 backups).
```
2026-05-12T10:22:01 | INFO     | src.hardware_monitor | [PASS] CPU.utilisation — CPU at 37.8% [real] — within limit
2026-05-12T10:22:02 | WARNING  | src.ssd_validator    | [FAIL] write_latency — 1161 µs exceeds 500 µs (hardware_defect)
2026-05-12T10:22:02 | WARNING  | src.ssd_validator    | smartctl unavailable — marking as framework_issue
```
To switch to JSON format for log aggregation pipelines:
```python
get_logger(__name__, use_json=True)
```

---

## Extending the Framework

To add a new validation check:

1. Add a method to `HardwareMonitor` or `SSDValidator` returning a `CheckResult`
2. Call it inside `run_all()`
3. Add pytest tests in `tests/`
4. Update `config.yaml` with the new threshold key

---

## CI / CD

GitHub Actions runs on every push to `main` or `dev`:

- Lint with `flake8`
- Run 98 tests across Python 3.11 and 3.12
- Generate and upload coverage report

See `.github/workflows/ci.yml` for the full pipeline.
