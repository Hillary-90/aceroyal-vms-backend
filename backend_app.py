"""
ACEROYAL ESTATES - Visitor Management System PRO : email backend (Flask)

DEPLOY ON RENDER.COM (GitHub user: Hillary-90)
 1. Create a GitHub repo (e.g. Hillary-90/aceroyal-vms-backend) containing, in the repo root:
        backend_app.py, requirements.txt, render.yaml
 2. Render dashboard -> New -> Blueprint -> connect that repo. Render reads render.yaml and
    creates the web service "aceroyal-vms-backend" (free plan).
    (Manual alternative: New -> Web Service, build "pip install -r requirements.txt",
     start "gunicorn backend_app:app".)
 3. When prompted, fill in the secret environment variables:
        SMTP_EMAIL      your sending mailbox, e.g. hillary@aceroyalestates.com
        SMTP_PASSWORD   password or app password (Gmail: create an App Password)
        FROM_EMAIL      address shown as sender (usually the same as SMTP_EMAIL)
    SMTP_HOST (smtp.gmail.com) and SMTP_PORT (587) are preset in render.yaml.
    Optional: ALLOWED_ORIGINS = https://your-site.netlify.app  (defaults to any origin)
    Optional: FEEDBACK_ALERT_EMAIL = HR / front desk address that receives low-rating alerts
              (defaults to SMTP_EMAIL);  FEEDBACK_ALERT_MAX = highest rating that triggers an alert (default 2)
 4. After deploy, open https://aceroyal-vms-backend.onrender.com/ - it should show status "running".
 5. In ACEROYAL_VMS_PRO.html -> Settings -> Backend URL, enter
        https://aceroyal-vms-backend.onrender.com
    (the app adds /send-email itself), set Mode to "backend" or "both", then click "Send test email".
 Note: the free tier sleeps when idle, so the first request can take about 30 seconds.

POST /feedback    JSON: visitorName, hostName, rating (1-5), staffRating, speedRating, comment, time
POST /send-email  JSON: hostEmail, hostName, visitorName, visitorCompany, visitorPhone, purpose, time (+ optional company, slogan)
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
<b style="font-size:18px">{escape(d.get("company") or "ACEROYAL ESTATES")}</b><div style="font-size:12px;margin-top:4px;font-style:italic">{escape(d.get("slogan") or "Building the future together...")}</div></div>
<div style="padding:20px"><p>Hello {escape(d.get("hostName") or "")},</p><p>You have a visitor waiting at the front desk:</p>
<table style="border-collapse:collapse;width:100%;font-size:14px">{trs}</table>
<p style="color:#666;font-size:12px;margin-top:20px">Sent automatically by the ACEROYAL Visitor Management System.</p></div></div>"""


@app.get("/")
def status():
    return jsonify(status="running", service="ACEROYAL VMS email backend",
                   smtp_configured=bool(os.getenv("SMTP_HOST") and os.getenv("SMTP_EMAIL") and os.getenv("SMTP_PASSWORD")))


def deliver(to, subject, html, text):
    host, user, pw = os.getenv("SMTP_HOST"), os.getenv("SMTP_EMAIL"), os.getenv("SMTP_PASSWORD")
    if not (host and user and pw):
        raise RuntimeError("SMTP environment variables are not set")
    port = int(os.getenv("SMTP_PORT", "587"))
    sender = os.getenv("FROM_EMAIL") or user
    msg = MIMEMultipart("alternative")
    msg["Subject"], msg["From"], msg["To"] = subject, f"ACEROYAL ESTATES <{sender}>", to
    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))
    ctx = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=ctx, timeout=20) as s:
            s.login(user, pw); s.sendmail(sender, [to], msg.as_string())
    else:
        with smtplib.SMTP(host, port, timeout=20) as s:
            s.starttls(context=ctx); s.login(user, pw); s.sendmail(sender, [to], msg.as_string())


def run(to, subject, html, text):
    try:
        deliver(to, subject, html, text)
    except RuntimeError as exc:
        return jsonify(success=False, error=str(exc)), 500
    except Exception as exc:  # noqa: BLE001
        app.logger.exception("send failed")
        return jsonify(success=False, error=str(exc)), 502
    return jsonify(success=True)


@app.post("/send-email")
def send_email():
    d = request.get_json(silent=True) or {}
    missing = [k for k in ("hostEmail", "visitorName", "purpose") if not d.get(k)]
    if missing:
        return jsonify(success=False, error="Missing: " + ", ".join(missing)), 400
    return run(d["hostEmail"], f"Visitor arrived: {d['visitorName']}", build_html(d),
               f"{d['visitorName']} ({d.get('visitorCompany') or '-'}) is here to see you. Purpose: {d['purpose']}")


@app.post("/feedback")
def feedback():
    d = request.get_json(silent=True) or {}
    try:
        rating = int(d.get("rating", 0))
    except (TypeError, ValueError):
        rating = 0
    if not 1 <= rating <= 5:
        return jsonify(success=False, error="rating must be 1 to 5"), 400
    if rating > int(os.getenv("FEEDBACK_ALERT_MAX", "2")):
        return jsonify(success=True, alerted=False)
    to = os.getenv("FEEDBACK_ALERT_EMAIL") or os.getenv("SMTP_EMAIL")
    stars = lambda n: ("\u2605" * int(n or 0)) or "-"
    rows = [("Visitor", d.get("visitorName") or "-"), ("Host", d.get("hostName") or "-"),
            ("Overall", stars(rating)), ("Staff", stars(d.get("staffRating"))),
            ("Speed", stars(d.get("speedRating"))), ("Comment", d.get("comment") or "-"), ("Time", d.get("time") or "-")]
    trs = "".join(f'<tr><td style="padding:8px 12px;border:1px solid #eee;background:#fafafa;width:30%"><b>{escape(k)}</b></td>'
                  f'<td style="padding:8px 12px;border:1px solid #eee">{escape(str(v))}</td></tr>' for k, v in rows)
    html = (f'<div style="font-family:Arial,sans-serif;max-width:560px;margin:auto;border:1px solid #ddd"><div style="background:{RED};color:#fff;padding:18px 20px">'
            f'<b style="font-size:18px">Low visitor rating</b></div><div style="padding:20px"><p>A visitor left a low rating and may need follow-up:</p>'
            f'<table style="border-collapse:collapse;width:100%;font-size:14px">{trs}</table></div></div>')
    resp = run(to, f"Low rating ({rating}/5): {d.get('visitorName') or 'visitor'}", html,
               f"Low rating {rating}/5 from {d.get('visitorName') or '-'}. Comment: {d.get('comment') or '-'}")
    return resp if isinstance(resp, tuple) else jsonify(success=True, alerted=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
