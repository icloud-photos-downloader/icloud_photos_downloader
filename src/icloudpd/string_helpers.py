"""String helper functions"""

import datetime
import re


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


def parse_timedelta(
    formatted: str,
) -> datetime.timedelta | None:
    m = re.match(r"(\d+)([dD]{1})", formatted)
    if m is not None and m.lastindex is not None and m.lastindex == 2:
        return datetime.timedelta(days=float(m.group(1)))
    return None


def parse_timestamp(
    formatted: str,
) -> datetime.datetime | None:
    try:
        dt = datetime.datetime.fromisoformat(formatted)
        return dt
    except Exception:
        return None


def parse_timestamp_or_timedelta(
    formatted: str,
) -> datetime.datetime | datetime.timedelta | None:
    p1 = parse_timedelta(formatted)
    if p1 is None:
        return parse_timestamp(formatted)
    return p1
