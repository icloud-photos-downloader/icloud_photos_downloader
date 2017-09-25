from smtplib import SMTP
import datetime

def send_two_step_expired_notification(smtp_email, smtp_password, to_addr):
	print("Sending two_step_expired notification via email...")
	smtp = SMTP()
	smtp.set_debuglevel(0)
	smtp.connect('smtp.gmail.com', 587)
	smtp.ehlo()
	smtp.starttls()
	smtp.login(smtp_email, smtp_password)

	subj = "icloud_photos_downloader: Two step authentication has expired"
	date = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

	message_text = """Hello,

Just letting you know that two-step authentication has expired for the icloud_photos_downloader script.
Please log in to your server and update two-step authentication.
"""

	from_addr = "iCloud Photos Downloader <" + smtp_email + ">"
	msg = "From: %s\nTo: %s\nSubject: %s\nDate: %s\n\n%s" % (
	from_addr, to_addr, subj, date, message_text)

	smtp.sendmail(smtp_email, to_addr, msg)
	smtp.quit()
