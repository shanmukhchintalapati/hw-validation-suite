"""
test_dashboard.py
-----------------
Tests for the HTML dashboard generator.
"""

import os
from unittest.mock import patch
from src import dashboard


class TestGenerateDashboard:
    def test_creates_html_file(self, tmp_path):
        dash_path = str(tmp_path / "dashboard.html")
        with patch("src.dashboard.DASHBOARD_PATH", dash_path), \
             patch("src.database.get_recent_runs", return_value=[]), \
             patch("src.database.get_defect_summary", return_value={}), \
             patch("src.database.init_db"):
            result = dashboard.generate_dashboard()
        assert os.path.exists(dash_path)
        assert result == dash_path

    def test_html_contains_key_sections(self, tmp_path):
        dash_path = str(tmp_path / "dashboard.html")
        with patch("src.dashboard.DASHBOARD_PATH", dash_path), \
             patch("src.database.get_recent_runs", return_value=[]), \
             patch("src.database.get_defect_summary", return_value={}), \
             patch("src.database.init_db"):
            dashboard.generate_dashboard()
        with open(dash_path, encoding="utf-8") as f:
            content = f.read()
        assert "HW Validation Dashboard" in content
        assert "Run History" in content
        assert "Hardware Defects" in content
        assert "Framework Issues" in content

    def test_shows_run_data(self, tmp_path):
        dash_path = str(tmp_path / "dashboard.html")
        runs = [{"id": 1, "run_time": 1700000000.0, "total": 8,
                 "passed": 6, "failed": 2, "pass_rate": 75.0, "elapsed_s": 1.5}]
        with patch("src.dashboard.DASHBOARD_PATH", dash_path), \
             patch("src.database.get_recent_runs", return_value=runs), \
             patch("src.database.get_run_results", return_value=[]), \
             patch("src.database.get_defect_summary", return_value={}), \
             patch("src.database.init_db"):
            dashboard.generate_dashboard()
        with open(dash_path, encoding="utf-8") as f:
            content = f.read()
        assert "75.0%" in content

    def test_auto_refresh_tag_present(self, tmp_path):
        dash_path = str(tmp_path / "dashboard.html")
        with patch("src.dashboard.DASHBOARD_PATH", dash_path), \
             patch("src.database.get_recent_runs", return_value=[]), \
             patch("src.database.get_defect_summary", return_value={}), \
             patch("src.database.init_db"):
            dashboard.generate_dashboard()
        with open(dash_path, encoding="utf-8") as f:
            content = f.read()
        assert 'http-equiv="refresh"' in content
