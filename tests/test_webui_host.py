import logging
from unittest import TestCase, mock

import waitress

from icloudpd.cli import parse
from icloudpd.server import serve_app
from icloudpd.status import StatusExchange


class WebuiHostTestCase(TestCase):
    def test_default_keeps_listening_on_all_interfaces(self) -> None:
        global_config, _ = parse(["-d", "/x", "-u", "a@b.c"])
        self.assertEqual(global_config.webui_host, "0.0.0.0")

    def test_option_is_parsed(self) -> None:
        global_config, _ = parse(["--webui-host", "127.0.0.1", "-d", "/x", "-u", "a@b.c"])
        self.assertEqual(global_config.webui_host, "127.0.0.1")

    def test_server_listens_on_the_given_host(self) -> None:
        with mock.patch.object(waitress, "serve") as serve:
            serve_app(logging.getLogger("test"), StatusExchange(), "127.0.0.1")
        self.assertEqual(serve.call_args.kwargs["host"], "127.0.0.1")

    def test_server_default_host_is_unchanged(self) -> None:
        with mock.patch.object(waitress, "serve") as serve:
            serve_app(logging.getLogger("test"), StatusExchange())
        self.assertEqual(serve.call_args.kwargs["host"], "0.0.0.0")
