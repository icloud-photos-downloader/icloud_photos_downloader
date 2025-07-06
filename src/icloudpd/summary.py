"""Tracks and prints a summary of actions performed"""

import logging
import time
from datetime import timedelta


class SummaryTracker:
    """Tracks and prints a summary of actions performed"""

    def __init__(self, logger: logging.Logger) -> None:
        self.start_time = 0.0
        self.end_time = 0.0
        self.logger = logger

    def start_timer(self) -> None:
        """Start the timer"""
        self.start_time = time.time()

    def stop_timer(self) -> None:
        """Stop the timer"""
        self.end_time = time.time()

    def print_summary(self) -> None:
        """Print the summary"""
        elapsed = self.end_time - self.start_time
        self.logger.info("\nExecution Summary")
        self.logger.info("=================")
        self.logger.info("Overall time: %s", timedelta(seconds=round(elapsed)))
