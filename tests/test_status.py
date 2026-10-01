from unittest import TestCase

from icloudpd.status import Status, StatusExchange


class StatusExchangeTestCase(TestCase):
    def test_confirm_login_when_waiting_for_confirmation(self) -> None:
        status_exchange = StatusExchange()
        self.assertTrue(
            status_exchange.replace_status(Status.NO_INPUT_NEEDED, Status.NEED_LOGIN_CONFIRMATION)
        )

        self.assertTrue(status_exchange.confirm_login())
        self.assertEqual(Status.LOGIN_CONFIRMED, status_exchange.get_status())

        # repeated confirmation (e.g. double click) is rejected
        self.assertFalse(status_exchange.confirm_login())
        self.assertEqual(Status.LOGIN_CONFIRMED, status_exchange.get_status())

    def test_confirm_login_when_not_waiting_for_confirmation(self) -> None:
        for status in Status:
            if status == Status.NEED_LOGIN_CONFIRMATION:
                continue
            with self.subTest(status=status):
                status_exchange = StatusExchange()
                status_exchange.replace_status(Status.NO_INPUT_NEEDED, status)

                self.assertFalse(status_exchange.confirm_login())
                self.assertEqual(status, status_exchange.get_status())

    def test_error_is_visible_while_waiting_for_confirmation(self) -> None:
        status_exchange = StatusExchange()
        status_exchange.replace_status(Status.NO_INPUT_NEEDED, Status.CHECKING_PASSWORD)
        status_exchange.set_error("Invalid email/password combination.")
        status_exchange.replace_status(Status.NO_INPUT_NEEDED, Status.NEED_LOGIN_CONFIRMATION)

        self.assertEqual("Invalid email/password combination.", status_exchange.get_error())
