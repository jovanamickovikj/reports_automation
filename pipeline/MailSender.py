"""Step 4 of the pipeline: send the automatic mails through Outlook.

Recipients come from .env (Settings). Four kinds of mail: alarm, pre-final, final, bulk.
"""
from datetime import date, timedelta

import win32com.client

from . import BusinessRules
from .Settings import Settings


class MailSender:

    def __init__(self, settings: Settings):
        self.settings = settings

    def send_alarm_mail(self, today: date) -> None:
        """The report did not arrive on time."""
        self.send_mail(
            to=self.settings.mail_alarm_to,
            subject=BusinessRules.ALARM_SUBJECT,
            body=f"Zdravo,\n\nDo {self.settings.alarm_time:%H:%M} casot na {today:%d.%m.%Y} ne e postaven "
                 f"fajlot ben_open (MAZ BAN Open Invoices) na Report Portal.\n\nPozdrav",
        )

    def send_pre_final_mail(self, activity_date: date, mail_text: str) -> None:
        """All counted activities, without the postponements."""
        self.send_mail(
            to=self.settings.mail_pre_final_to,
            subject=f"Collection activities {activity_date:%d.%m.%Y} pre-final",
            body=mail_text,
        )

    def send_final_mail(self, activity_date: date, mail_text: str) -> None:
        """The numbers after the postponements."""
        self.send_mail(
            to=self.settings.mail_final_to,
            cc=self.settings.mail_final_cc,
            subject=f"Collection activities {activity_date:%d.%m.%Y}",
            body=mail_text,
        )

    def send_bulk_mail(self, activity_date: date, msisdns: int) -> None:
        """Announces a bigger bulk of suspensions (night between the day before and the activity date)."""
        day_before = activity_date - timedelta(days=1)
        self.send_mail(
            to=self.settings.mail_bulk_to,
            cc=self.settings.mail_bulk_cc,
            subject=f"Sledni bulk-ovi na suspenzii (nokjta pomegju {day_before:%d.%m.%Y} i {activity_date:%d.%m.%Y})",
            body=f"Zdravo kolegi,\n\nDa najavime deka nokjta pomegju {day_before:%d.%m.%Y} i "
                 f"{activity_date:%d.%m.%Y} kje imame pogolem bulk za suspenzii (okolu {msisdns} MSISDN).\n\nPozdrav",
        )

    @staticmethod
    def send_mail(to: str, subject: str, body: str, cc: str = "") -> None:
        outlook = win32com.client.Dispatch("Outlook.Application")
        mail = outlook.CreateItem(0)
        mail.To = to
        if cc:
            mail.CC = cc
        mail.Subject = subject
        mail.Body = body
        mail.Send()
