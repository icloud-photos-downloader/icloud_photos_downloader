"""Send an email notification when 2SA is expired"""

import smtplib
import datetime
from icloudpd.logger import setup_logger

# pylint: disable-msg=too-many-arguments


def send_2sa_notification(
        smtp_email, smtp_password, smtp_host, smtp_port, smtp_no_tls, to_addr
):
    """Send an email notification when 2SA is expired"""
    to_addr = to_addr if to_addr else smtp_email
    from_addr = smtp_email if smtp_email else to_addr
    logger = setup_logger()
    logger.info("Sending 'two-step expired' notification via email...")
    smtp = smtplib.SMTP()
    smtp.set_debuglevel(0)
    smtp.connect(smtp_host, smtp_port)
    if not smtp_no_tls:
        smtp.starttls()

    if smtp_email is not None or smtp_password is not None:
        smtp.login(smtp_email, smtp_password)

    subj = "icloud_photos_downloader: Two step authentication has expired"
    date = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

    message_text = """Hello,

Two-step authentication has expired for the icloud_photos_downloader script.
Please log in to your server and run the script manually to update two-step authentication."""

    msg = "From: %s\nTo: %s\nSubject: %s\nDate: %s\n\n%s" % (
        "iCloud Photos Downloader <" + from_addr + ">",
        to_addr,
        subj,
        date,
        message_text,
    )

    smtp.sendmail(from_addr, to_addr, msg)
    smtp.quit()
