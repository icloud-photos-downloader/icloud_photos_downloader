import datetime
import logging
from io import StringIO
from unittest import TestCase
from unittest.mock import MagicMock

from freezegun import freeze_time

from icloudpd.logger import IPDLogger, setup_logger


class LoggerTestCase(TestCase):
    # Tests the formatter that is set up in setup_logger()
    @freeze_time("2018-01-01 00:00:00-0000")
    def test_logger_output(self) -> None:
        logger = setup_logger()
        test_logger = logging.getLogger("icloudpd-test")
        string_io = StringIO()
        string_handler = logging.StreamHandler(stream=string_io)
        string_handler.setFormatter(logger.handlers[0].formatter)
        test_logger.addHandler(string_handler)
        test_logger.setLevel(logging.DEBUG)
        test_logger.info("Test info output")
        test_logger.debug("Test debug output")
        test_logger.error("Test error output")
        output = string_io.getvalue().strip()
        # 2018:01:01 00:00:00 utc
        expectedDatetime = (
            datetime.datetime(2018, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
            .astimezone()
            .strftime("%Y-%m-%d %H:%M:%S")
        )
        self.assertIn(expectedDatetime, output)
        self.assertIn("INFO     Test info output", output)
        self.assertIn("DEBUG    Test debug output", output)
        self.assertIn("ERROR    Test error output", output)

    def test_logger_tqdm_fallback(self) -> None:
        logging.setLoggerClass(IPDLogger)
        logger = logging.getLogger("icloudpd-test")
        logger.log = MagicMock()  # type: ignore[method-assign]
        logger.set_tqdm_description("foo")  # type: ignore[attr-defined]
        logger.log.assert_called_once_with(logging.INFO, "foo")

        logger.log = MagicMock()  # type: ignore[method-assign]
        logger.tqdm_write("bar")  # type: ignore[attr-defined]
        logger.log.assert_called_once_with(logging.INFO, "bar")

        logger.set_tqdm(MagicMock())  # type: ignore[attr-defined]
        logger.tqdm.write = MagicMock()  # type: ignore[attr-defined]
        logger.tqdm.set_description = MagicMock()  # type: ignore[attr-defined]
        logger.log = MagicMock()  # type: ignore[method-assign]
        logger.set_tqdm_description("baz")  # type: ignore[attr-defined]
        logger.tqdm.set_description.assert_called_once_with("baz")  # type: ignore[attr-defined]
        logger.tqdm_write("qux")  # type: ignore[attr-defined]
        logger.tqdm.write.assert_called_once_with("qux")  # type: ignore[attr-defined]
        logger.log.assert_not_called()

        logger.set_tqdm(None)  # type: ignore[attr-defined]
