"""Atomic counter"""

from multiprocessing import Lock, RawValue


class Counter:
    def __init__(self, value: int = 0):
        self.initial_value = value
        self.val = RawValue("i", value)
        self.lock = Lock()

    def increment(self) -> None:
        with self.lock:
            self.val.value += 1

    def reset(self) -> None:
        with self.lock:
            self.val = RawValue("i", self.initial_value)

    def value(self) -> int:
        with self.lock:
            return int(self.val.value)
