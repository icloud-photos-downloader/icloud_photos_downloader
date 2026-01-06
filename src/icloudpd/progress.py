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
        self.total_photos_in_icloud = 0  # Total photos in iCloud
        self.photos_to_download = 0  # Photos not in cache that need download
        self.last_progress_message_time = 0.0  # Timestamp of last progress message
        self.watch_interval = 0  # Watch interval in seconds (0 = no watch mode)
        self.last_sync_time = 0.0  # Timestamp of last sync completion
        self.photos_checked = 0  # Photos checked during filtering (for progress tracking)
        self.processing_start_time = 0.0  # Timestamp when processing started (for rate calculation)

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
        # Save resume flag before resetting (it should persist across resets)
        resume_flag = self.resume
        self._photos_count = 0
        self._photos_counter = 0
        self.photos_percent = 0
        self._waiting = 0
        self.waiting_readable = ""
        self.cancel = False
        self.total_photos_in_icloud = 0
        self.photos_to_download = 0
        self.last_progress_message_time = 0.0
        self.photos_checked = 0
        # Don't reset processing_start_time - it should persist until processing completes
        # Restore resume flag and don't reset watch_interval and last_sync_time - they persist across resets
        self.resume = resume_flag
