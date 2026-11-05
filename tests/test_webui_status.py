import logging
from unittest import TestCase

from icloudpd.cli import parse
from icloudpd.server import create_app, without_secrets
from icloudpd.status import StatusExchange


class WebUIStatusTestCase(TestCase):
    def test_status_page_hides_passwords(self) -> None:
        global_config, user_configs = parse(
            [
                "--password-provider",
                "parameter",
                "-d",
                "photos",
                "--username",
                "user@example.com",
                "--password",
                "icloud-secret-1",
                "--smtp-username",
                "mail@example.com",
                "--smtp-password",
                "smtp-secret-2",
            ]
        )
        status_exchange = StatusExchange()
        status_exchange.set_global_config(global_config)
        status_exchange.set_user_configs(user_configs)

        app = create_app(logging.getLogger("test"), status_exchange)
        response = app.test_client().get("/status")

        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn("user@example.com", page)
        self.assertIn("mail@example.com", page)
        self.assertIn("password_providers", page)
        self.assertNotIn("icloud-secret-1", page)
        self.assertNotIn("smtp-secret-2", page)

    def test_without_secrets(self) -> None:
        self.assertEqual(
            without_secrets(
                {
                    "username": "u",
                    "password": "p",
                    "smtp_password": "s",
                    "password_providers": ["parameter"],
                }
            ),
            {"username": "u", "password_providers": ["parameter"]},
        )
