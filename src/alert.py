"""
alert.py
--------
Email alert system for hw-validation-suite.
Sends alerts when hardware_defect failures are detected.

Covers: enterprise automation, real-time notification,
        team collaboration in server validation workflows.
"""

import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from src.logger import get_logger

logger = get_logger(__name__)


def should_alert(summary: dict) -> bool:
    """
    Return True if any result contains a hardware_defect.
    Framework issues don't trigger alerts — only real hardware problems do.
    """
    for r in summary.get("results", []):
        d = r.to_dict()
        if d.get("defect_type") == "hardware_defect":
            return True
    return False


def build_alert_body(summary: dict) -> str:
    """Build a plain-text alert email body from the summary."""
    lines = [
        "HW Validation Suite — ALERT",
        "=" * 40,
        f"Total checks : {summary['total']}",
        f"Passed       : {summary['passed']}",
        f"Failed       : {summary['failed']}",
        f"Pass rate    : {summary['pass_rate_pct']}%",
        f"Elapsed      : {summary['elapsed_seconds']} s",
        "",
        "FAILED CHECKS:",
        "-" * 40,
    ]

    for r in summary.get("results", []):
        d = r.to_dict()
        if not d.get("passed"):
            name = d.get("component") or d.get("test_name", "unknown")
            defect = d.get("defect_type", "—")
            lines.append(f"  [{defect.upper()}] {name}: {d.get('message', '')}")

    lines += [
        "",
        "Action required for hardware_defect failures.",
        "framework_issue failures indicate environment/config problems.",
        "",
        "See attached HTML report for full details.",
    ]
    return "\n".join(lines)


def send_alert(
    summary: dict,
    smtp_host: str,
    smtp_port: int,
    sender: str,
    recipients: list,
    password: str,
    html_report_path: str = "",
    use_tls: bool = True,
) -> bool:
    """
    Send an alert email with the validation summary.
    Attaches the HTML report if the path is provided.

    Returns True if sent successfully, False otherwise.

    In production: store credentials in environment variables, never hardcode.
    Example:
        smtp_host = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
        password  = os.environ.get('SMTP_PASSWORD', '')
    """
    if not should_alert(summary):
        logger.info("No hardware_defect failures — alert not needed")
        return False

    try:
        msg = MIMEMultipart()
        msg["From"] = sender
        msg["To"] = ", ".join(recipients)
        msg["Subject"] = (
            f"[HW-VALIDATION] ALERT — {summary['failed']} checks failed "
            f"({summary['pass_rate_pct']}% pass rate)"
        )

        # Plain text body
        body = build_alert_body(summary)
        msg.attach(MIMEText(body, "plain"))

        # Attach HTML report if available
        if html_report_path and os.path.exists(html_report_path):
            with open(html_report_path, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f"attachment; filename={os.path.basename(html_report_path)}",
            )
            msg.attach(part)

        # Send via SMTP
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            if use_tls:
                server.starttls()
            server.login(sender, password)
            server.sendmail(sender, recipients, msg.as_string())

        logger.info("Alert sent to %s", recipients)
        return True

    except smtplib.SMTPException as exc:
        logger.error("Failed to send alert email: %s", exc)
        return False
    except OSError as exc:
        logger.error("Alert I/O error: %s", exc)
        return False


def send_alert_from_config(summary: dict, config: dict) -> bool:
    """
    Convenience wrapper — reads SMTP settings from config dict.
    Add these keys to config.yaml to enable email alerts:

        alert_enabled: true
        alert_smtp_host: "smtp.gmail.com"
        alert_smtp_port: 587
        alert_sender: "your@email.com"
        alert_recipients: ["team@company.com"]
        alert_password: ""   # use env var SMTP_PASSWORD instead
    """
    if not config.get("alert_enabled", False):
        logger.info("Email alerts disabled in config")
        return False

    password = (
        os.environ.get("SMTP_PASSWORD")
        or config.get("alert_password", "")
    )

    return send_alert(
        summary=summary,
        smtp_host=config.get("alert_smtp_host", "smtp.gmail.com"),
        smtp_port=config.get("alert_smtp_port", 587),
        sender=config.get("alert_sender", ""),
        recipients=config.get("alert_recipients", []),
        password=password,
        html_report_path=summary.get("html_report", ""),
        use_tls=config.get("alert_use_tls", True),
    )
