import sys
import click
from pyicloud import PyiCloudService
from notifications import send_two_step_expired_notification

def authenticate(username, password, \
    smtp_username, smtp_password, smtp_host, smtp_port, smtp_no_tls, \
    notification_email):
    if password:
      icloud = PyiCloudService(username, password)
    else:
      icloud = PyiCloudService(username)

    if icloud.requires_2sa:
        if smtp_username and smtp_password:
            # If running in the background, send a notification email.
            send_two_step_expired_notification(smtp_username, smtp_password, \
                smtp_host, smtp_port, smtp_no_tls, notification_email)
            exit()

        print("Two-factor authentication required. Your trusted devices are:")

        devices = icloud.trusted_devices
        for i, device in enumerate(devices):
            print("  %s: %s" % (i, device.get('deviceName',
                "SMS to %s" % device.get('phoneNumber'))))

        device = click.prompt('Which device would you like to use?', default=0)
        device = devices[device]
        if not icloud.send_verification_code(device):
            print("Failed to send verification code")
            sys.exit(1)

        code = click.prompt('Please enter validation code')
        if not icloud.validate_verification_code(device, code):
            print("Failed to verify verification code")
            sys.exit(1)

        print("Great, you're all set up. The script can now be run without user interaction.")
        print("You can set up email notifications to receive a notification when two-step authentication expires.")
        print("Use --help to view information about SMTP options.")
        sys.exit(1)

    return icloud
