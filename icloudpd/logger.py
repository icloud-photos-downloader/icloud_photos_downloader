import sys
import logging
from logging import DEBUG, INFO, ERROR, NOTSET

class iCloudPDLogger(logging.Logger):
    def __init__(self, name, level=INFO):
        logging.Logger.__init__(self, name, level)
        self.tqdm = None

    # If tdqm progress bar is not set, we just write regular log messages
    def set_tqdm(self, tdqm):
        self.tqdm = tdqm

    def set_tqdm_description(self, desc):
        if self.tqdm is None:
            self.info(desc)
        else:
            self.tqdm.set_description(desc)

    def tqdm_write(self, message):
        if self.tqdm is None:
            self.info(message)
        else:
            self.tqdm.write(message)

def setup_logger(loglevel=DEBUG):
    logging.setLoggerClass(iCloudPDLogger)
    formatter = logging.Formatter(fmt='%(asctime)s %(levelname)-8s %(message)s',
                                  datefmt='%Y-%m-%d %H:%M:%S')
    stdout_handler = logging.StreamHandler(stream=sys.stdout)
    stdout_handler.setFormatter(formatter)
    logger = logging.getLogger('icloudpd')
    logger.setLevel(loglevel)
    logger.addHandler(stdout_handler)
    return logger
