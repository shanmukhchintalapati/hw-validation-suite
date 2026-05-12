"""
test_alert.py
-------------
Tests for the email alert system.
"""

from unittest.mock import patch, MagicMock
from src.alert import should_alert, build_alert_body, send_alert_from_config


def _make_result(defect_type="none", passed=True):
    r = MagicMock()
    r.to_dict.return_value = {
        "component": "CPU",
        "metric": "utilisation",
        "value": 50.0,
        "unit": "%",
        "passed": passed,
        "defect_type": defect_type,
        "message": "test message",
    }
    return r


def _make_summary(results):
    total = len(results)
    passed = sum(1 for r in results if r.to_dict().get("passed"))
    failed = total - passed
    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "pass_rate_pct": round(passed / total * 100, 1) if total else 0,
        "elapsed_seconds": 1.0,
        "results": results,
        "html_report": "",
    }


class TestShouldAlert:
    def test_true_when_hardware_defect(self):
        summary = _make_summary([_make_result("hardware_defect", False)])
        assert should_alert(summary) is True

    def test_false_when_only_framework_issue(self):
        summary = _make_summary([_make_result("framework_issue", False)])
        assert should_alert(summary) is False

    def test_false_when_all_pass(self):
        summary = _make_summary([_make_result("none", True)])
        assert should_alert(summary) is False

    def test_true_when_mixed_defects(self):
        summary = _make_summary([
            _make_result("none", True),
            _make_result("hardware_defect", False),
        ])
        assert should_alert(summary) is True


class TestBuildAlertBody:
    def test_contains_summary_fields(self):
        summary = _make_summary([_make_result("hardware_defect", False)])
        body = build_alert_body(summary)
        assert "Total checks" in body
        assert "Passed" in body
        assert "Failed" in body

    def test_lists_failed_checks(self):
        summary = _make_summary([_make_result("hardware_defect", False)])
        body = build_alert_body(summary)
        assert "HARDWARE_DEFECT" in body

    def test_no_failed_section_when_all_pass(self):
        summary = _make_summary([_make_result("none", True)])
        body = build_alert_body(summary)
        assert "HARDWARE_DEFECT" not in body


class TestSendAlertFromConfig:
    def test_disabled_when_alert_enabled_false(self):
        summary = _make_summary([_make_result("hardware_defect", False)])
        config = {"alert_enabled": False}
        result = send_alert_from_config(summary, config)
        assert result is False

    def test_disabled_when_no_hardware_defect(self):
        summary = _make_summary([_make_result("framework_issue", False)])
        config = {"alert_enabled": True, "alert_sender": "a@b.com",
                  "alert_recipients": ["c@d.com"], "alert_smtp_host": "smtp.test.com",
                  "alert_smtp_port": 587}
        result = send_alert_from_config(summary, config)
        assert result is False

    def test_attempts_smtp_when_hardware_defect(self):
        summary = _make_summary([_make_result("hardware_defect", False)])
        config = {
            "alert_enabled": True,
            "alert_sender": "a@b.com",
            "alert_recipients": ["c@d.com"],
            "alert_smtp_host": "smtp.test.com",
            "alert_smtp_port": 587,
            "alert_password": "testpass",
        }
        with patch("src.alert.smtplib.SMTP") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server
            send_alert_from_config(summary, config)
            mock_smtp.assert_called_once()
