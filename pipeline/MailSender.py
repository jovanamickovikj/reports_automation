"""Step 4 of the pipeline: send the automatic mail through Outlook."""
import win32com.client

from .ProcessingResult import ProcessingResult
from .Settings import Settings


class MailSender:

    def __init__(self, settings: Settings):
        self.mail_to = settings.mail_to
        self.mail_cc = settings.mail_cc

    def send_report_mail(self, result: ProcessingResult) -> None:
        """Sends the mail with the scheduled activities for the activity date."""
        self.send_mail(
            to=self.mail_to,
            cc=self.mail_cc,
            subject=f"Zakazani aktivnosti za {result.activity_date:%d.%m.%Y} se sledni:",
            body=result.mail_text,
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
