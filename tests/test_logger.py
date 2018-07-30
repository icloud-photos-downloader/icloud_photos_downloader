from unittest import TestCase
from mock import MagicMock
import logging
from icloudpd.logger import setup_logger, iCloudPDLogger

class LoggerTestCase(TestCase):
    def test_logger_tqdm_fallback(self):
        setup_logger()
        # Other tests might run before this, and setup_logger() hasn't been called,
        # so the 'icloudpd' logger will be the wrong class (Logger)
        logger = logging.getLogger('icloudpd2')

        logger.info = MagicMock()
        logger.set_tqdm_description('foo')
        logger.info.assert_called_once_with('foo')

        logger.info = MagicMock()
        logger.tqdm_write('foo')
        logger.info.assert_called_once_with('foo')

        logger.set_tqdm(MagicMock())
        logger.tqdm.write = MagicMock()
        logger.tqdm.set_description = MagicMock()
        logger.set_tqdm_description('bar')
        logger.tqdm.set_description.assert_called_once_with('bar')
        logger.tqdm_write('bar')
        logger.tqdm.write.assert_called_once_with('bar')
