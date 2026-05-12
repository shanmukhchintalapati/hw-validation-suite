"""
database.py
-----------
SQLite persistence layer for hw-validation-suite.
Stores every validation run and all check results for trend analysis.

Covers: enterprise thinking, historical data, detecting gradual degradation.
"""

import sqlite3
import os
import time
from src.logger import get_logger

logger = get_logger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "reports", "validation_history.db")


def get_connection() -> sqlite3.Connection:
    """Return a connection to the SQLite database, creating it if needed."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they don't exist."""
    conn = get_connection()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS runs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                run_time    REAL    NOT NULL,
                total       INTEGER NOT NULL,
                passed      INTEGER NOT NULL,
                failed      INTEGER NOT NULL,
                pass_rate   REAL    NOT NULL,
                elapsed_s   REAL    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS results (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id       INTEGER NOT NULL REFERENCES runs(id),
                component    TEXT,
                metric       TEXT,
                test_name    TEXT,
                value        REAL    NOT NULL,
                unit         TEXT    NOT NULL,
                threshold    REAL    NOT NULL,
                passed       INTEGER NOT NULL,
                defect_type  TEXT,
                source       TEXT,
                message      TEXT,
                checked_at   REAL    NOT NULL
            );
        """)
        conn.commit()
        logger.info("Database initialised at %s", DB_PATH)
    finally:
        conn.close()


def save_run(summary: dict) -> int:
    """
    Persist a full suite run and all its results.
    Returns the run_id for reference.
    """
    init_db()
    conn = get_connection()
    try:
        cur = conn.execute(
            """INSERT INTO runs
               (run_time, total, passed, failed, pass_rate, elapsed_s)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                time.time(),
                summary["total"],
                summary["passed"],
                summary["failed"],
                summary["pass_rate_pct"],
                summary["elapsed_seconds"],
            ),
        )
        run_id = cur.lastrowid

        for r in summary["results"]:
            d = r.to_dict()
            conn.execute(
                """INSERT INTO results
                   (run_id, component, metric, test_name, value, unit,
                    threshold, passed, defect_type, source, message, checked_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    run_id,
                    d.get("component"),
                    d.get("metric"),
                    d.get("test_name"),
                    d.get("value", 0),
                    d.get("unit", ""),
                    d.get("threshold", 0),
                    1 if d.get("passed") else 0,
                    d.get("defect_type"),
                    d.get("source"),
                    d.get("message"),
                    d.get("timestamp", time.time()),
                ),
            )

        conn.commit()
        logger.info("Run #%d saved to database (%d results)", run_id, len(summary["results"]))
        return run_id
    finally:
        conn.close()


def get_recent_runs(limit: int = 10) -> list:
    """Return the most recent N runs."""
    init_db()
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM runs ORDER BY run_time DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_run_results(run_id: int) -> list:
    """Return all check results for a specific run."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM results WHERE run_id = ?", (run_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_trend(component: str, metric: str, limit: int = 20) -> list:
    """
    Return the last N measurements for a specific component+metric.
    Used to detect gradual degradation over time.
    Example: get_trend('CPU', 'utilisation') shows if CPU load is rising.
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT r.run_time, res.value, res.passed
               FROM results res
               JOIN runs r ON r.id = res.run_id
               WHERE res.component = ? AND res.metric = ?
               ORDER BY r.run_time DESC LIMIT ?""",
            (component, metric, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_defect_summary() -> dict:
    """
    Count hardware_defect vs framework_issue failures across all runs.
    Useful for reporting to engineering leadership.
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT defect_type, COUNT(*) as count
               FROM results
               WHERE passed = 0 AND defect_type IS NOT NULL
               GROUP BY defect_type"""
        ).fetchall()
        return {r["defect_type"]: r["count"] for r in rows}
    finally:
        conn.close()
