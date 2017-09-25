from pyicloud import PyiCloudService
from notifications import send_two_step_expired_notification

def authenticate(username, password, smtp_username, smtp_password, notification_email):
    if password:
      icloud = PyiCloudService(username, password)
    else:
      icloud = PyiCloudService(username)

    # Fixes bug in pyicloud - https://github.com/picklepete/pyicloud/pull/149
    # Rename to requires_2sa (with fallback) after this is merged.
    if hasattr(icloud, 'requires_2sa'):
        icloud.requires_2fa = icloud.requires_2sa

    if icloud.requires_2fa:
        if smtp_username and smtp_password:
            # If running in the background, send a notification email.
            send_two_step_expired_notification(smtp_username, smtp_password, notification_email)
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

        print("Great, you're all set up. Now re-run the script to print out filenames.")
        sys.exit(1)

    return icloud
