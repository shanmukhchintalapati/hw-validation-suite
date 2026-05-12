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
| Test coverage and continuous reporting | HTML + CSV reports, GitHub Actions CI wi
