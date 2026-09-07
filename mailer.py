"""
mailer.py — Email delivery for the Ekhaya FC Fan Hub.

Reads SMTP / provider settings from site_settings (configured at runtime via
the admin settings page) and falls back to environment variables. When no
working SMTP config is present the mailer runs in DEV mode: emails are logged
to the server console so the OTP flow can be tested locally without an inbox.

Settings keys (site_settings / env):
    mailer_from_email    - sender address (env MAILER_FROM_EMAIL)
    mailer_from_name     - friendly sender name (default 'Ekhaya FC')
    mailer_host          - SMTP host, e.g. sandbox.smtp.mailtrap.io
                            (env MAILER_HOST)
    mailer_port          - SMTP port (default 587, env MAILER_PORT)
    mailer_username      - SMTP username (env MAILER_USERNAME)
    mailer_password      - SMTP password/app key (env MAILER_PASSWORD)
    mailer_use_tls       - '1' to STARTTLS (default), '0' to skip.

You can point it at Mailtrap (dev), or any real SMTP provider. Just create a
free Mailtrap inbox and paste its credentials into the admin settings page.
"""

import os
import re
import smtplib
import sys
from email.message import EmailMessage

from membership_db import get_setting

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _cfg(key, env, default=None):
    val = get_setting(key, None)
    if val is None or str(val).strip() == "":
        val = os.environ.get(env)
    return val if val is not None else default


def is_configured():
    """True when SMTP host + credentials are present (real sending enabled)."""
    return bool(_cfg("mailer_host", "MAILER_HOST"))


def configured_mode():
    """Return a human-readable description of the current delivery mode."""
    if is_configured():
        return "SMTP (%s)" % _cfg("mailer_host", "MAILER_HOST")
    return "DEV (console logging — no real emails sent)"


def valid_email(address):
    return bool(address and _EMAIL_RE.match(address.strip()))


def send_email(to_email, subject, body_text, body_html=None):
    """Send one message. Returns (ok, message_or_payload)."""
    to_email = (to_email or "").strip()
    if not valid_email(to_email):
        return False, "Invalid recipient address: %r" % to_email

    from_email = _cfg("mailer_from_email", "MAILER_FROM_EMAIL",
                      "no-reply@ekhaya-fc.local")
    from_name = _cfg("mailer_from_name", "MAILER_FROM_NAME", "Ekhaya FC")

    if not is_configured():
        # ---- DEV mode: log so the flow is testable without an inbox ----
        # stdout is block-buffered when redirected to a file, so flush
        # immediately or the OTP never reaches the console / log.
        print("\n[mailer:DEV] ==================================================")
        print("[mailer:DEV] To:      %s" % to_email)
        print("[mailer:DEV] Subject: %s" % subject)
        print("[mailer:DEV] Body:    %s" % body_text)
        print("[mailer:DEV] ==================================================\n")
        sys.stdout.flush()
        return True, "logged-to-console (no SMTP configured)"

    host = _cfg("mailer_host", "MAILER_HOST")
    port = int(_cfg("mailer_port", "MAILER_PORT", 587))
    username = _cfg("mailer_username", "MAILER_USERNAME", "")
    password = _cfg("mailer_password", "MAILER_PASSWORD", "")
    use_tls = str(_cfg("mailer_use_tls", "MAILER_USE_TLS", "1")) == "1"

    msg = EmailMessage()
    msg["From"] = ("%s <%s>" % (from_name, from_email)) if from_name \
        else from_email
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body_text or "")
    if body_html:
        msg.add_alternative(body_html, subtype="html")

    try:
        if use_tls:
            server = smtplib.SMTP(host, port, timeout=30)
            server.starttls()
        else:
            server = smtplib.SMTP(host, port, timeout=30)
        if username:
            server.login(username, password)
        server.send_message(msg)
        server.quit()
        return True, "sent-via-smtp"
    except Exception as exc:  # noqa: BLE001
        return False, "SMTP error: %s" % exc


def send_otp(to_email, otp_code, purpose="verify your email"):
    """Compose and send the OTP message."""
    subject = "Your Ekhaya FC verification code"
    body = ("Hello from Ekhaya FC!\n\n"
            "Your one-time password to %s is:  %s\n\n"
            "It expires in 10 minutes. If you did not request this, "
            "you can ignore this email.\n\n— Ekhaya FC Family" %
            (purpose, otp_code))
    html = ("<div style='font-family:Arial,sans-serif;max-width:480px;"
            "margin:auto;border:1px solid #e9e3d4;border-radius:12px;"
            "overflow:hidden'>"
            "<div style='background:#c4a64c;color:#fff;padding:16px;"
            "text-align:center;font-size:18px;font-weight:bold'>EKHAYA FC</div>"
            "<div style='padding:24px'>"
            "<p>Hello from Ekhaya FC!</p>"
            "<p>Your one-time password to <b>%s</b> is:</p>"
            "<p style='text-align:center;font-size:34px;letter-spacing:6px;"
            "font-weight:bold;color:#8f7433'>%s</p>"
            "<p>It expires in <b>10 minutes</b>. If you did not request "
            "this, you can ignore this email.</p>"
            "</div></div>" % (purpose, otp_code))
    return send_email(to_email, subject, body, html)