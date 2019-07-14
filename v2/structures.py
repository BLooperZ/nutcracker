import struct

from functools import partial, reduce

from operator import itemgetter

from typing import AnyStr, IO, Iterator, Optional, overload, Sequence, Tuple, Union

def compose(*functions):
    return reduce(lambda f, g: lambda x: f(g(x)), functions, lambda x: x)

def read_struct(st: struct.Struct, f: Union[IO[bytes], bytes]) -> Sequence[int]:
    if isinstance(f, bytes):
        return st.unpack(f[:st.size])
    return st.unpack(f.read(st.size))

def write_struct(st: struct.Struct, num: int) -> bytes:
    return st.pack(num)

uint32be = struct.Struct('>I')
read_uint32be = compose(itemgetter(0), partial(read_struct, uint32be))
write_uint32be = partial(read_struct, uint32be)

uint16le = struct.Struct('<H')
read_uint16le = compose(itemgetter(0), partial(read_struct, uint16le))
