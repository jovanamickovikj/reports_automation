"""Step 4 of the pipeline: prepare the automatic mail in Outlook. The mail is NOT sent."""
from datetime import date

import win32com.client

from .Settings import Settings


class MailSender:

    def __init__(self, settings: Settings):
        self.mail_to = settings.mail_to
        self.mail_cc = settings.mail_cc

    def create_draft_mail(self, activity_date: date, mail_text: str) -> None:
        """Opens the mail with the scheduled activities in Outlook as a draft, so someone can check it and send it."""
        self.show_draft(
            to=self.mail_to,
            cc=self.mail_cc,
            subject=f"Zakazani aktivnosti za {activity_date:%d.%m.%Y} se sledni:",
            body=mail_text,
        )

    @staticmethod
    def show_draft(to: str, subject: str, body: str, cc: str = "") -> None:
        outlook = win32com.client.Dispatch("Outlook.Application")
        mail = outlook.CreateItem(0)
        mail.To = to
        if cc:
            mail.CC = cc
        mail.Subject = subject
        mail.Body = body
        mail.Display()   # opens the mail window; nothing is sent until the person presses Send
