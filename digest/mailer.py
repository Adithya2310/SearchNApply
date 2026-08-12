import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def send_email(subject, text_body, html_body=None, to_addr=None, from_addr=None, app_password=None):
    """SMTP + Gmail App Password, per BUILD_PLAN.md ("not OAuth, keep it
    simple"). App Password is displayed with spaces for readability but the
    actual credential has none — strip them so a copy-paste with spaces
    still authenticates.
    """
    from_addr = from_addr or os.environ["GMAIL_ADDRESS"]
    to_addr = to_addr or from_addr
    app_password = (app_password or os.environ["GMAIL_APP_PASSWORD"]).replace(" ", "")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg.attach(MIMEText(text_body, "plain"))
    if html_body:
        msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(from_addr, app_password)
        server.sendmail(from_addr, [to_addr], msg.as_string())
