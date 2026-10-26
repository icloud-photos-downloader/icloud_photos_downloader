# Experimental Mode

Goal is to try new things and get feedback from users without breaking existing behavior.

Anything in this section can change without backward compatibility or even completely removed.

DANGER ZONE: Code may not work as expected.

## Advanced Data Protection (`--adp-web-access`)

Opt-in support for accounts with Advanced Data Protection (ADP). After signing in, icloudpd replays the consent sequence icloud.com uses to unlock protected photos. See [ADP](docs/authentication.md#adp) for setup.

- Requires `Access iCloud Data on the Web` to be enabled on the account
- The first run sends an approval request to your Apple devices; icloudpd waits up to 2 minutes for it
- Tested by its author on a real ADP account; the test suite only covers simulated responses. Please report how it works for you in [#687](https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/687)
- It is not yet known how long Apple keeps the approval valid; when it expires, the next run asks for approval again