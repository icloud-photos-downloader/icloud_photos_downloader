import datetime
import smtplib

from icloudpd.notifier import Notifier


class EmailNotifier(Notifier):
    def __init__(self,
                 smtp_host: str,
                 smtp_port: int = 587,
                 smtp_no_tls: bool = False,
                 smtp_email: str | None = None,
                 smtp_password: str | None = None,
                 to_addr: str | None = None,
                 from_addr: str | None = None) -> None:
        self.smtp_email = smtp_email
        self.smtp_password = smtp_password
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_no_tls = smtp_no_tls
        self.to_addr = to_addr or smtp_email
        self.from_addr = from_addr or (f"iCloud Photos Downloader <{smtp_email}>" if smtp_email else to_addr)


    def send_notification(self,
                          message: str,
                          title: str | None = None) -> None:
        smtp = smtplib.SMTP(self.smtp_host, self.smtp_port)
        smtp.set_debuglevel(0)
        # leaving explicit call of connect to not break unit tests, even though it is
        # called implicitly via constructor parameters
        smtp.connect(self.smtp_host, self.smtp_port)
        if not self.smtp_no_tls:
            smtp.starttls()

        if self.smtp_email is not None and self.smtp_password is not None:
            smtp.login(self.smtp_email, self.smtp_password)

        date = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

        msg = f"From: {self.from_addr}\n" + f"To: {self.to_addr}\nSubject: {title}\nDate: {date}\n\n{message}"

        smtp.sendmail(self.from_addr, self.to_addr, msg)
        smtp.quit()
