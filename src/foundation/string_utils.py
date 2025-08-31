"""Point-free string utility functions for functional composition"""

from typing import Callable

from foundation.core import compose


def strip(s: str) -> str:
    """Point-free version of str.strip()

    >>> strip("  hello  ")
    'hello'
    """
    return s.strip()


def lower(s: str) -> str:
    """Point-free version of str.lower()

    >>> lower("HELLO")
    'hello'
    """
    return s.lower()


def upper(s: str) -> str:
    """Point-free version of str.upper()

    >>> upper("hello")
    'HELLO'
    """
    return s.upper()


def endswith(suffix: str | tuple[str, ...]) -> Callable[[str], bool]:
    """Curried version of str.endswith()

    >>> ends_with_txt = endswith(".txt")
    >>> ends_with_txt("file.txt")
    True
    >>> ends_with_txt("file.pdf")
    False
    >>> ends_with_images = endswith((".jpg", ".png"))
    >>> ends_with_images("file.jpg")
    True
    """
    return lambda s: s.endswith(suffix)


def startswith(prefix: str) -> Callable[[str], bool]:
    """Curried version of str.startswith()

    >>> starts_with_img = startswith("IMG_")
    >>> starts_with_img("IMG_1234.jpg")
    True
    >>> starts_with_img("DSC_5678.jpg")
    False
    """
    return lambda s: s.startswith(prefix)


def contains(substring: str) -> Callable[[str], bool]:
    """Check if string contains substring

    >>> has_hevc = contains("HEVC")
    >>> has_hevc("IMG_1234_HEVC.MOV")
    True
    >>> has_hevc("IMG_1234.MOV")
    False
    """
    return lambda s: substring in s


def eq(expected: str) -> Callable[[str], bool]:
    """String equality predicate

    >>> is_none = eq("none")
    >>> is_none("none")
    True
    >>> is_none("other")
    False
    """
    return lambda actual: actual == expected


def replace(old: str, new: str) -> Callable[[str], str]:
    """Curried version of str.replace()

    >>> replace_heic = replace(".HEIC", ".MOV")
    >>> replace_heic("IMG_1234.HEIC")
    'IMG_1234.MOV'
    """
    return lambda s: s.replace(old, new)


def split(separator: str) -> Callable[[str], list[str]]:
    """Curried version of str.split()

    >>> split_lines = split("\\n")
    >>> split_lines("line1\\nline2\\nline3")
    ['line1', 'line2', 'line3']
    """
    return lambda s: s.split(separator)


def join(separator: str) -> Callable[[list[str]], str]:
    """Curried version of str.join()

    >>> join_with_dot = join(".")
    >>> join_with_dot(["filename", "txt"])
    'filename.txt'
    """
    return lambda parts: separator.join(parts)


def is_empty(s: str) -> bool:
    """Check if string is empty

    >>> is_empty("")
    True
    >>> is_empty("hello")
    False
    """
    return len(s) == 0


def is_not_empty(s: str) -> bool:
    """Check if string is not empty

    >>> is_not_empty("hello")
    True
    >>> is_not_empty("")
    False
    """
    return len(s) > 0


# Composed utilities for common patterns
strip_and_lower: Callable[[str], str] = compose(lower, strip)
"""Strip whitespace and convert to lowercase

>>> strip_and_lower('  HELLO  ')
'hello'
"""


def replace_extension(new_ext: str) -> Callable[[str], str]:
    """Replace file extension with new extension

    >>> replace_with_mov = replace_extension(".MOV")
    >>> replace_with_mov("IMG_1234.HEIC")
    'IMG_1234.MOV'
    >>> replace_with_mov("no_extension")
    'no_extension'
    """
    import os

    def _replace_extension(filename: str) -> str:
        name, ext = os.path.splitext(filename)
        if not ext:
            return filename
        return name + new_ext

    return _replace_extension
