import struct
from functools import partial
from typing import IO

UINT16LE = struct.Struct('<H')


def wrap(structure: struct.Struct, data: bytes) -> bytes:
    return structure.pack(len(data)) + data


def unwrap(structure: struct.Struct, stream: IO[bytes]) -> bytes:
    return stream.read(structure.unpack(stream.read(structure.size))[0])


wrap_uint16le = partial(wrap, UINT16LE)
unwrap_uint16le = partial(unwrap, UINT16LE)
