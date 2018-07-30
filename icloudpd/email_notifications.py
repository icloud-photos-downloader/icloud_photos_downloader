import smtplib
import datetime
import logging

def send_two_step_expired_notification(
    smtp_email, smtp_password, smtp_host, smtp_port, smtp_no_tls, to_addr):
    to_addr = to_addr if to_addr else smtp_email
    logger = logging.getLogger('icloudpd')
    logger.info("Sending 'two-step expired' notification via email...")
    smtp = smtplib.SMTP()
    smtp.set_debuglevel(0)
    smtp.connect(smtp_host, smtp_port)
    if not smtp_no_tls:
        smtp.starttls()
    smtp.login(smtp_email, smtp_password)

    subj = "icloud_photos_downloader: Two step authentication has expired"
    date = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

    message_text = """Hello,

Two-step authentication has expired for the icloud_photos_downloader script.
Please log in to your server and run the script manually to update two-step authentication."""

    from_addr = "iCloud Photos Downloader <" + smtp_email + ">"
    msg = "From: %s\nTo: %s\nSubject: %s\nDate: %s\n\n%s" % (
    from_addr, to_addr, subj, date, message_text)

    smtp.sendmail(smtp_email, to_addr, msg)
    smtp.quit()
