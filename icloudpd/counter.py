"""Atomic counter"""
# pylint: skip-file
from multiprocessing import RawValue, Lock


class Counter(object):
    def __init__(self, value=0):
        self.initial_value = value
        self.val = RawValue('i', value)
        self.lock = Lock()

    def increment(self):
        with self.lock:
            self.val.value += 1

    def reset(self):
        with self.lock:
            self.val = RawValue('i', self.initial_value)

    def value(self):
        with self.lock:
            return self.val.value
