"""Step 4 of the pipeline: send the automatic mail through Outlook."""
import win32com.client


def send_mail(to: str, subject: str, body: str, cc: str = "") -> None:
    outlook = win32com.client.Dispatch("Outlook.Application")
    mail = outlook.CreateItem(0)
    mail.To = to
    if cc:
        mail.CC = cc
    mail.Subject = subject
    mail.Body = body
    mail.Send()