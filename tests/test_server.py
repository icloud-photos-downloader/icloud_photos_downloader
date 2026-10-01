from unittest import TestCase, mock

from flask import Flask
from flask.testing import FlaskClient

from icloudpd.cli import parse
from icloudpd.logger import setup_logger
from icloudpd.server import serve_app
from icloudpd.status import Status, StatusExchange


def create_client(status_exchange: StatusExchange) -> FlaskClient:
    with mock.patch("waitress.serve") as serve:
        serve_app(setup_logger(), status_exchange)
    app: Flask = serve.call_args.args[0]
    return app.test_client()


class ServerTestCase(TestCase):
    def setUp(self) -> None:
        self.status_exchange = StatusExchange()
        self.status_exchange.set_current_user("jdoe@gmail.com")
        self.client = create_client(self.status_exchange)

    def test_status_need_login_confirmation(self) -> None:
        self.status_exchange.replace_status(Status.NO_INPUT_NEEDED, Status.NEED_LOGIN_CONFIRMATION)

        response = self.client.get("/status")

        self.assertEqual(200, response.status_code)
        page = response.get_data(as_text=True)
        self.assertIn('hx-post="/login/confirm"', page)
        self.assertIn("Session for jdoe@gmail.com expired. Start sign-in?", page)
        self.assertIn(">Start</button>", page)

    def test_status_need_login_confirmation_with_error(self) -> None:
        # previous sign-in attempt failed and was retried
        self.status_exchange.replace_status(Status.NO_INPUT_NEEDED, Status.CHECKING_PASSWORD)
        self.status_exchange.set_error("Invalid email/password combination.")
        self.status_exchange.replace_status(Status.NO_INPUT_NEEDED, Status.NEED_LOGIN_CONFIRMATION)

        response = self.client.get("/status")

        self.assertEqual(200, response.status_code)
        self.assertIn("Invalid email/password combination.", response.get_data(as_text=True))

    def test_confirm_login(self) -> None:
        self.status_exchange.replace_status(Status.NO_INPUT_NEEDED, Status.NEED_LOGIN_CONFIRMATION)

        response = self.client.post("/login/confirm")

        self.assertEqual(200, response.status_code)
        self.assertIn("Sign-in started for jdoe@gmail.com", response.get_data(as_text=True))
        self.assertEqual(Status.LOGIN_CONFIRMED, self.status_exchange.get_status())

    def test_confirm_login_when_not_waiting(self) -> None:
        response = self.client.post("/login/confirm")

        self.assertEqual(409, response.status_code)
        self.assertEqual(Status.NO_INPUT_NEEDED, self.status_exchange.get_status())

    def test_status_shows_login_confirmation_setting(self) -> None:
        global_config, _ = parse(["--login-confirmation", "webui"])
        self.status_exchange.set_global_config(global_config)

        response = self.client.get("/status")

        self.assertEqual(200, response.status_code)
        page = response.get_data(as_text=True)
        self.assertIn("login_confirmation", page)
        self.assertIn("WEBUI", page)
