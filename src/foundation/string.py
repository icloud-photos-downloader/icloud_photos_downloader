import binascii
from functools import singledispatch
from typing import Any


@singledispatch
def obfuscate(_input: Any) -> str:
    raise NotImplementedError()


@obfuscate.register(str)
def _(input: str) -> str:
    return f"OBFUSCATED-{binascii.crc32(input.encode('utf-8'))}"
