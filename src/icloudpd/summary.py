"""Tracks and prints a summary of actions performed"""

import time
from datetime import timedelta


class SummaryTracker:
    """Tracks and prints a summary of actions performed"""

    def __init__(self) -> None:
        self.start_time = 0.0
        self.end_time = 0.0

    def start_timer(self) -> None:
        """Start the timer"""
        self.start_time = time.time()

    def stop_timer(self) -> None:
        """Stop the timer"""
        self.end_time = time.time()

    def print_summary(self) -> None:
        """Print the summary"""
        elapsed = self.end_time - self.start_time
        print(f"\nExecution Summary")
        print(f"=================")
        print(f"Overall time: {timedelta(seconds=round(elapsed))}")