"""
test_database.py
----------------
Tests for SQLite persistence layer.
"""

import os
import time
import pytest
from unittest.mock import MagicMock, patch
from src import database


@pytest.fixture(autouse=True)
def temp_db(tmp_path):
    """Redirect DB to a temp path for every test."""
    db_file = str(tmp_path / "test_validation.db")
    with patch("src.database.DB_PATH", db_file):
        yield db_file


def _make_result(passed=True, defect_type="none", component="CPU"):
    r = MagicMock()
    r.to_dict.return_value = {
        "component": component,
        "metric": "utilisation",
        "test_name": None,
        "value": 50.0,
        "unit": "%",
        "threshold": 85.0,
        "passed": passed,
        "defect_type": defect_type,
        "source": "real",
        "message": "ok",
        "timestamp": time.time(),
    }
    return r


def _make_summary(passed=8, failed=0, results=None):
    total = passed + failed
    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "pass_rate_pct": round(passed / total * 100, 1) if total else 0,
        "elapsed_seconds": 1.0,
        "results": results or [_make_result() for _ in range(total)],
    }


class TestInitDB:
    def test_creates_tables(self, temp_db):
        database.init_db()
        assert os.path.exists(temp_db)

    def test_idempotent(self, temp_db):
        database.init_db()
        database.init_db()
        assert os.path.exists(temp_db)


class TestSaveRun:
    def test_save_returns_run_id(self, temp_db):
        summary = _make_summary()
        run_id = database.save_run(summary)
        assert isinstance(run_id, int)
        assert run_id >= 1

    def test_save_multiple_runs(self, temp_db):
        database.save_run(_make_summary())
        database.save_run(_make_summary())
        runs = database.get_recent_runs()
        assert len(runs) == 2

    def test_results_stored(self, temp_db):
        results = [_make_result(passed=True), _make_result(passed=False)]
        summary = _make_summary(passed=1, failed=1, results=results)
        run_id = database.save_run(summary)
        stored = database.get_run_results(run_id)
        assert len(stored) == 2


class TestGetRecentRuns:
    def test_returns_most_recent_first(self, temp_db):
        database.save_run(_make_summary(passed=6))
        database.save_run(_make_summary(passed=8))
        runs = database.get_recent_runs(limit=2)
        assert runs[0]["passed"] == 8

    def test_respects_limit(self, temp_db):
        for _ in range(5):
            database.save_run(_make_summary())
        runs = database.get_recent_runs(limit=3)
        assert len(runs) == 3


class TestGetTrend:
    def test_returns_trend_data(self, temp_db):
        r = _make_result(component="CPU")
        database.save_run(_make_summary(results=[r]))
        trend = database.get_trend("CPU", "utilisation")
        assert len(trend) == 1
        assert trend[0]["value"] == 50.0

    def test_empty_when_no_data(self, temp_db):
        database.init_db()
        trend = database.get_trend("CPU", "utilisation")
        assert trend == []


class TestDefectSummary:
    def test_counts_defect_types(self, temp_db):
        results = [
            _make_result(passed=False, defect_type="hardware_defect"),
            _make_result(passed=False, defect_type="hardware_defect"),
            _make_result(passed=False, defect_type="framework_issue"),
        ]
        database.save_run(_make_summary(passed=0, failed=3, results=results))
        summary = database.get_defect_summary()
        assert summary.get("hardware_defect") == 2
        assert summary.get("framework_issue") == 1

    def test_empty_when_all_pass(self, temp_db):
        database.save_run(_make_summary(passed=8, failed=0))
        summary = database.get_defect_summary()
        assert summary == {}
