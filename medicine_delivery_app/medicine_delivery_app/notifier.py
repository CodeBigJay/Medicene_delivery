"""Sends SMS and email notifications.

SMS provider (SMS_PROVIDER):
  console (default)  prints the message to the server log (safe for development)
  twilio             real SMS; needs TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM
Email provider (EMAIL_PROVIDER):
  console (default)  prints the email to the server log
  smtp               real email; needs SMTP_HOST, SMTP_PORT (587), SMTP_USER, SMTP_PASSWORD, SMTP_FROM
Add another provider by writing one more small class with the same method.
"""
import os
import smtplib
from email.message import EmailMessage

import requests


def to_international(phone):
    """0821234567 -> +27821234567"""
    digits = (phone or "").replace(" ", "")
    if digits.startswith("0"):
        return "+27" + digits[1:]
    return digits if digits.startswith("+") else "+" + digits


# ---- SMS providers ------------------------------------------------------
class ConsoleSms:
    def send(self, phone, text):
        print(f"[SMS to {phone}] {text}")
        return True


class TwilioSms:
    def __init__(self):
        self.sid = os.environ["TWILIO_ACCOUNT_SID"]
        self.token = os.environ["TWILIO_AUTH_TOKEN"]
        self.sender = os.environ["TWILIO_FROM"]

    def send(self, phone, text):
        url = f"https://api.twilio.com/2010-04-01/Accounts/{self.sid}/Messages.json"
        try:
            response = requests.post(
                url, auth=(self.sid, self.token), timeout=10,
                data={"To": to_international(phone), "From": self.sender, "Body": text})
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as err:
            print(f"SMS failed: {err}")
            return False


# ---- Email providers ----------------------------------------------------
class ConsoleEmail:
    def send(self, to, subject, text):
        print(f"[EMAIL to {to}] {subject}\n{text}\n")
        return True


class SmtpEmail:
    def __init__(self):
        self.host = os.environ["SMTP_HOST"]
        self.port = int(os.environ.get("SMTP_PORT", "587"))
        self.user = os.environ.get("SMTP_USER", "")
        self.password = os.environ.get("SMTP_PASSWORD", "")
        self.sender = os.environ.get("SMTP_FROM", self.user)

    def send(self, to, subject, text):
        message = EmailMessage()
        message["From"], message["To"], message["Subject"] = self.sender, to, subject
        message.set_content(text)
        try:
            with smtplib.SMTP(self.host, self.port, timeout=10) as server:
                server.starttls()
                if self.user:
                    server.login(self.user, self.password)
                server.send_message(message)
            return True
        except (OSError, smtplib.SMTPException) as err:
            print(f"Email failed: {err}")
            return False


class Notifier:
    """One object the server uses for every kind of notification."""

    def __init__(self, sms=None, email=None):
        self.sms_provider = sms or ConsoleSms()
        self.email_provider = email or ConsoleEmail()

    def sms(self, phone, text):
        return bool(phone) and self.sms_provider.send(phone, text)

    def email(self, to, subject, text):
        return bool(to) and self.email_provider.send(to, subject, text)


def get_notifier():
    sms = TwilioSms() if os.environ.get("SMS_PROVIDER", "console").lower() == "twilio" else ConsoleSms()
    mail = SmtpEmail() if os.environ.get("EMAIL_PROVIDER", "console").lower() == "smtp" else ConsoleEmail()
    return Notifier(sms, mail)


def pin_message(patient_name, pin):
    return (f"Doorstep Meds: your medicine is on its way. Give this PIN to the messenger "
            f"when it arrives: {pin}. Do not share it with anyone else. ({patient_name})")
