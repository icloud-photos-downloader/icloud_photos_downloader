"""Custom logging class and setup function"""

import logging
import sys
from logging import INFO
from typing import Any


class IPDLogger(logging.Logger):
    """Custom logger class with support for tqdm progress bar"""

    def __init__(self, name: str, level: int = INFO):
        logging.Logger.__init__(self, name, level)
        self.tqdm = None

    # If tdqm progress bar is not set, we just write regular log messages
    def set_tqdm(self, tdqm: Any) -> None:
        """Sets the tqdm progress bar"""
        self.tqdm = tdqm

    def set_tqdm_description(self, desc: str, loglevel: int = INFO) -> None:
        """Set tqdm progress bar description, fallback to logging"""
        if self.tqdm is None:
            self.log(loglevel, desc)
        else:
            self.tqdm.set_description(desc)

    def tqdm_write(self, message: str, loglevel: int = INFO) -> None:
        """Write to tqdm progress bar, fallback to logging"""
        if self.tqdm is None:
            self.log(loglevel, message)
        else:
            self.tqdm.write(message)


def setup_logger() -> logging.Logger:
    """Set up logger and add stdout handler"""
    logging.setLoggerClass(IPDLogger)
    logger = logging.getLogger("icloudpd")
    has_stdout_handler = False
    for handler in logger.handlers:
        if handler.name == "stdoutLogger":
            has_stdout_handler = True
    if not has_stdout_handler:
        formatter = logging.Formatter(
            fmt="%(asctime)s %(levelname)-8s %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
        stdout_handler = logging.StreamHandler(stream=sys.stdout)
        stdout_handler.setFormatter(formatter)
        stdout_handler.name = "stdoutLogger"
        logger.addHandler(stdout_handler)
    return logger
