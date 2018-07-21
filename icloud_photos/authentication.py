import sys
import getpass
import click
import pyicloud
from notifications import send_two_step_expired_notification

def authenticate(username, password, \
    smtp_username, smtp_password, smtp_host, smtp_port, smtp_no_tls, \
    notification_email):
    try:
      # If password not provided on command line variable will be set to None
      # and PyiCloud will attempt to retrieve from it's keyring
      icloud = pyicloud.PyiCloudService(username, password)
    except pyicloud.exceptions.NoStoredPasswordAvailable:
      # Prompt for password if not stored in PyiCloud's keyring
      password = getpass.getpass()
      icloud = pyicloud.PyiCloudService(username, password)

    if icloud.requires_2sa:
        if smtp_username and smtp_password:
            # If running in the background, send a notification email.
            send_two_step_expired_notification(smtp_username, smtp_password, \
                smtp_host, smtp_port, smtp_no_tls, notification_email)
            exit()

        print("Two-step/two-factor authentication is required.")

        devices = icloud.trusted_devices
        devices_count = len(devices)
        if devices_count == 0:
            device_index = 0
        else:
            for i, device in enumerate(devices):
                print("  %s: %s" % (i, device.get('deviceName',
                    "SMS to %s" % device.get('phoneNumber'))))
            print("  %s: Enter two-factor authentication code" % devices_count)
            device_index = click.prompt('Please choose an option:', default=0, type=click.IntRange(0, devices_count))

        if device_index == devices_count:
            # We're using the 2FA code that was automatically sent to the user's device,
            # so can just use an empty dict()
            device = dict()
        else:
            device = devices[device_index]
            if not icloud.send_verification_code(device):
                print("Failed to send two-factor authentication code")
                sys.exit(1)

        code = click.prompt('Please enter two-factor authentication code')
        if not icloud.validate_verification_code(device, code):
            print("Failed to verify two-factor authentication code")
            sys.exit(1)

        print("Great, you're all set up. The script can now be run without user interaction.")
        print("You can also set up email notifications for when the two-step authentication expires.")
        print("(Use --help to view information about SMTP options.)")

    return icloud
