from unittest import TestCase, mock

from keyring.errors import KeyringLocked

from pyicloud_ipd import cmdline


class IcloudCmdlineKeyringTestCase(TestCase):
    def test_locked_keyring_asks_for_password(self) -> None:
        """A locked keyring (e.g. headless Linux) falls back to the password prompt instead of crashing"""
        with (
            mock.patch(
                "pyicloud_ipd.utils.keyring.get_password",
                side_effect=KeyringLocked("Keyring is locked"),
            ),
            mock.patch("pyicloud_ipd.cmdline.getpass.getpass", return_value="password1") as prompt,
            mock.patch("builtins.input", return_value="n"),
            mock.patch("pyicloud_ipd.cmdline.PyiCloudService") as service,
            mock.patch("sys.stderr") as stderr,
        ):
            service.return_value.requires_2fa = False
            service.return_value.requires_2sa = False
            with self.assertRaises(SystemExit) as exit:
                cmdline.main(["--username", "jdoe@gmail.com"])

        self.assertEqual(0, exit.exception.code)
        prompt.assert_called_once()
        self.assertEqual("password1", service.call_args.args[2]())
        written = "".join(call.args[0] for call in stderr.write.call_args_list)
        self.assertIn(
            "Could not read password from keyring: KeyringLocked: Keyring is locked", written
        )
