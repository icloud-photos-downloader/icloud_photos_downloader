"""String helper functions"""

import datetime
import re
from typing import Union


def truncate_middle(string: str, length: int) -> str:
    """Truncates a string to a maximum length, inserting "..." in the middle"""
    if len(string) <= length:
        return string
    if length < 0:
        raise ValueError("n must be greater than or equal to 1")
    if length <= 3:
        return "..."[0:length]
    end_length = int(length) // 2 - 2
    start_length = length - end_length - 4
    end_length = max(end_length, 1)
    return f"{string[:start_length]}...{string[-end_length:]}"


def parse_timestamp_or_timedelta(
    formatted: str,
) -> Union[datetime.datetime, datetime.timedelta, ValueError]:
    m = re.match(r"(\d+)([dD]{1})", formatted)
    if m is not None and m.lastindex is not None and m.lastindex == 2:
        return datetime.timedelta(days=float(m.group(1)))

    # try timestamp
    try:
        dt = datetime.datetime.fromisoformat(formatted)
        return dt
    except Exception as e:
        return ValueError(f"{formatted} did not parse timedelta and ISO format successfully: {e}")
