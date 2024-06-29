"""Send an email notification when 2SA is expired"""

import datetime
import logging
import smtplib
from typing import Optional, cast


def send_2sa_notification(
    logger: logging.Logger,
    smtp_email: Optional[str],
    smtp_password: Optional[str],
    smtp_host: str,
    smtp_port: int,
    smtp_no_tls: bool,
    to_addr: Optional[str],
    from_addr: Optional[str] = None,
) -> None:
    """Send an email notification when 2SA is expired"""
    to_addr = cast(str, to_addr if to_addr is not None else smtp_email)
    from_addr = (
        from_addr
        if from_addr is not None
        else (f"iCloud Photos Downloader <{smtp_email}>" if smtp_email else to_addr)
    )
    logger.info("Sending 'two-step expired' notification via email...")
    smtp = smtplib.SMTP(smtp_host, smtp_port)
    smtp.set_debuglevel(0)
    # leaving explicit call of connect to not break unit tests, even though it is
    # called implicitly via constructor parameters
    smtp.connect(smtp_host, smtp_port)
    if not smtp_no_tls:
        smtp.starttls()

    if smtp_email is not None and smtp_password is not None:
        smtp.login(smtp_email, smtp_password)

    subj = "icloud_photos_downloader: Two step authentication has expired"
    date = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

    message_text = """Hello,

Two-step authentication has expired for the icloud_photos_downloader script.
Please log in to your server and run the script manually to update two-step authentication."""

    msg = f"From: {from_addr}\n" + f"To: {to_addr}\nSubject: {subj}\nDate: {date}\n\n{message_text}"

    smtp.sendmail(from_addr, to_addr, msg)
    smtp.quit()
