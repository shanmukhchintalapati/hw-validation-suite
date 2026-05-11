# hw-validation-suite

A production-style Python automation framework for hardware and SSD validation, built as a portfolio project demonstrating skills for the **Python + Networking Engineer** role.

![CI](https://github.com/shanmukhchintalapati/hw-validation-suite/actions/workflows/ci.yml/badge.svg)

---

## What This Project Covers

| Job Requirement | Where It's Demonstrated |
|---|---|
| Maintain hardware validation automation framework | `framework_runner.py` — orchestrates all validators with retry logic |
| Design and execute automated test cases | `tests/` — 60 pytest tests with fixtures, mocks, parametrize |
| Enhance Python automation frameworks | `HardwareMonitor` + `SSDValidator` — modular, config-driven |
| Integrate automation with system-level hardware validation | Real `shutil.disk_usage`, `os.fsync`, `subprocess` for SMART |
| Debug and distinguish framework vs hardware defects | `defect_type` field in every SSD result (`framework_issue` / `hardware_defect`) |
| Automate validation for server systems including memory and storage | CPU, RAM, Disk, Network, SSD throughput, IOPS, latency, SMART |
| Create and maintain automation documentation and user guides | This README + `USERGUIDE.md` |
| Support continuous improvement of test coverage and reporting | HTML + CSV reports, GitHub Actions CI with coverage |
| PowerShell scripting (good to have) | `bootstrap.ps1` — cross-platform setup script |

---

## Project Structure

```
hw-validation-suite/
├── src/
│   ├── hardware_monitor.py    # CPU, RAM, Disk, Network validation
│   ├── ssd_validator.py       # SSD throughput, IOPS, latency, SMART
│   ├── framework_runner.py    # Orchestrator with retry + reporting
│   ├── logger.py              # Rotating file + console + JSON logging
│   └── report_generator.py   # HTML and CSV report output
├── tests/
│   ├── test_hardware_monitor.py   # 38 tests
│   ├── test_ssd_validator.py      # 17 tests
│   └── test_framework_runner.py   # 9 tests (integration + retry)
├── reports/                   # Auto-generated HTML/CSV reports
├── logs/                      # Rotating log files
├── .github/workflows/ci.yml   # GitHub Actions CI
├── config.yaml                # All thresholds, configurable
├── bootstrap.ps1              # PowerShell setup script
└── requirements.txt
```

---

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

Reports are written to `reports/` as HTML and CSV.

### Run tests

```bash
pytest tests/ -v
```

### Run tests with coverage

```bash
pytest tests/ --cov=src --cov-report=term-missing
```

---

## Configuration

Edit `config.yaml` to adjust thresholds without touching source code:

```yaml
cpu_threshold_percent: 85.0        # alert if CPU > 85%
min_memory_available_gb: 2.0       # alert if RAM available < 2 GB
min_disk_free_gb: 10.0             # alert if disk free < 10 GB
max_network_latency_ms: 100.0      # alert if latency > 100 ms
min_sequential_throughput_mbs: 200 # alert if SSD throughput < 200 MB/s
max_write_latency_us: 500          # alert if write latency > 500 µs
max_retries: 2                     # retry failed checks this many times
```

---

## Architecture

```
config.yaml
    │
    ▼
framework_runner.py  ──► HardwareMonitor  ──► CheckResult(s)
                     ──► SSDValidator     ──► SSDCheckResult(s)
                               │
                          logger.py  (rotating file + console)
                               │
                     report_generator.py  ──► reports/report_*.html
                                          ──► reports/report_*.csv
```

### Defect Classification

`SSDValidator` distinguishes between two failure categories:

| `defect_type` | Meaning | Example |
|---|---|---|
| `framework_issue` | Problem in the test environment or config | `smartctl` not installed, I/O permission error, moderate throughput drop |
| `hardware_defect` | Problem with the physical device | Very low throughput (<50 MB/s), SMART failure, extreme latency |
| `none` | Check passed | — |

---

## Logging

Logs are written to `logs/hw_validation.log` with automatic rotation (5 MB × 3 backups).

```
2025-01-15T14:32:01 | INFO     | src.hardware_monitor | [PASS] CPU — CPU at 62.3% — within limit
2025-01-15T14:32:01 | WARNING  | src.ssd_validator    | [FAIL] write_latency — 820 µs exceeds 500 µs (framework_issue)
```

To switch to JSON format (for log aggregation pipelines), update `logger.py`:

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
- Run 60 tests across Python 3.11 and 3.12
- Generate and upload coverage report

See `.github/workflows/ci.yml` for the full pipeline.
