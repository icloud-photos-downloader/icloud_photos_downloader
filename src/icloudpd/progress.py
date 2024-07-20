import datetime


class Progress:
    def __init__(self) -> None:
        self._photos_count = 0
        self._photos_counter = 0
        self.photos_percent = 0
        self.photos_last_message = ""
        self.waiting_readable = ""
        self.resume = False
        self.cancel = False
        self._waiting = 0

    @property
    def waiting(self) -> int:
        return self._waiting

    @waiting.setter
    def waiting(self, waiting: int) -> None:
        self._waiting = waiting
        self.waiting_readable = str(datetime.timedelta(seconds=waiting))

    @property
    def photos_count(self) -> int:
        return self._photos_count

    @photos_count.setter
    def photos_count(self, photos_count: int) -> None:
        self._photos_count = photos_count
        if self.photos_count != 0:
            self.photos_percent = round(100 / self.photos_count * self.photos_counter)
        else:
            self.photos_percent = 0

    @property
    def photos_counter(self) -> int:
        return self._photos_counter

    @photos_counter.setter
    def photos_counter(self, photos_counter: int) -> None:
        self._photos_counter = photos_counter
        if self.photos_count != 0:
            self.photos_percent = round(100 / self.photos_count * self.photos_counter)
        else:
            self.photos_percent = 0

    def reset(self) -> None:
        self._photos_count = 0
        self._photos_counter = 0
        self.photos_percent = 0
        self._waiting = 0
        self.waiting_readable = ""
        self.resume = False
        self.cancel = False
