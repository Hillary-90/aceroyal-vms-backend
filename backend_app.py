"""
ACEROYAL ESTATES - Visitor Management System PRO : email backend (Flask)

DEPLOY ON RENDER.COM
 1. Put backend_app.py and requirements.txt in a GitHub repo.
    requirements.txt:
        flask
        flask-cors
        gunicorn
 2. Render dashboard -> New -> Web Service -> connect the repo.
 3. Runtime: Python 3.  Build command: pip install -r requirements.txt
    Start command: gunicorn backend_app:app
 4. Environment variables:
        SMTP_HOST      e.g. smtp.gmail.com
        SMTP_PORT      587 (STARTTLS) or 465 (SSL)
        SMTP_EMAIL     login email
        SMTP_PASSWORD  password or app password (Gmail: use an App Password)
        FROM_EMAIL     optional, defaults to SMTP_EMAIL
        ALLOWED_ORIGINS optional, comma-separated, e.g. https://your-site.netlify.app
 5. Deploy, then paste the https://....onrender.com URL into
    Settings -> Backend URL in the VMS app and click "Send test email".
 Note: Render's free tier sleeps when idle; the first request can take ~30s.
"""
import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape

from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app, origins=[o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",")])

RED = "#B22222"


def build_html(d):
    rows = [("Visitor", d["visitorName"]), ("Company", d.get("visitorCompany") or "-"),
            ("Phone", d.get("visitorPhone") or "-"), ("Purpose", d["purpose"]),
            ("Arrival time", d.get("time") or "-")]
    trs = "".join(
        f'<tr><td style="padding:8px 12px;border:1px solid #eee;background:#fafafa;width:35%"><b>{escape(k)}</b></td>'
        f'<td style="padding:8px 12px;border:1px solid #eee">{escape(str(v))}</td></tr>' for k, v in rows)
    return f"""<div style="font-family:Arial,sans-serif;max-width:560px;margin:auto;border:1px solid #ddd">
<div style="background:{RED};color:#fff;padding:18px 20px"><span style="display:inline-block;background:#fff;color:{RED};
font-weight:bold;width:30px;height:30px;line-height:30px;text-align:center;margin-right:10px">A</span>
<b style="font-size:18px">ACEROYAL ESTATES</b><div style="font-size:12px;margin-top:4px;font-style:italic">Building the future together...</div></div>
<div style="padding:20px"><p>Hello {escape(d.get("hostName") or "")},</p><p>You have a visitor waiting at the front desk:</p>
<table style="border-collapse:collapse;width:100%;font-size:14px">{trs}</table>
<p style="color:#666;font-size:12px;margin-top:20px">Sent automatically by the ACEROYAL Visitor Management System.</p></div></div>"""


@app.get("/")
def status():
    return jsonify(status="running", service="ACEROYAL VMS email backend",
                   smtp_configured=bool(os.getenv("SMTP_HOST") and os.getenv("SMTP_EMAIL") and os.getenv("SMTP_PASSWORD")))


@app.post("/send-email")
def send_email():
    d = request.get_json(silent=True) or {}
    missing = [k for k in ("hostEmail", "visitorName", "purpose") if not d.get(k)]
    if missing:
        return jsonify(success=False, error="Missing: " + ", ".join(missing)), 400
    host, user, pw = os.getenv("SMTP_HOST"), os.getenv("SMTP_EMAIL"), os.getenv("SMTP_PASSWORD")
    if not (host and user and pw):
        return jsonify(success=False, error="SMTP environment variables are not set"), 500
    port = int(os.getenv("SMTP_PORT", "587"))
    sender = os.getenv("FROM_EMAIL") or user
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Visitor arrived: {d['visitorName']}"
    msg["From"], msg["To"] = f"ACEROYAL ESTATES <{sender}>", d["hostEmail"]
    msg.attach(MIMEText(f"{d['visitorName']} ({d.get('visitorCompany') or '-'}) is here to see you. Purpose: {d['purpose']}", "plain"))
    msg.attach(MIMEText(build_html(d), "html"))
    try:
        ctx = ssl.create_default_context()
        if port == 465:
            with smtplib.SMTP_SSL(host, port, context=ctx, timeout=20) as s:
                s.login(user, pw); s.sendmail(sender, [d["hostEmail"]], msg.as_string())
        else:
            with smtplib.SMTP(host, port, timeout=20) as s:
                s.starttls(context=ctx); s.login(user, pw); s.sendmail(sender, [d["hostEmail"]], msg.as_string())
    except Exception as exc:  # noqa: BLE001
        app.logger.exception("send failed")
        return jsonify(success=False, error=str(exc)), 502
    return jsonify(success=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
