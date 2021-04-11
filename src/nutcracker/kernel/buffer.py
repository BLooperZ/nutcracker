from dataclasses import dataclass
from typing import Optional, Union

import deal

BufferLike = Union[bytes, bytearray, memoryview]


class UnexpectedBufferSize(EOFError):
    def __init__(self, expected: int, given: int, buffer: BufferLike) -> None:
        super().__init__(f'Expected buffer of size {expected} but got size {given}')
        self.expected = expected
        self.given = given
        self.buffer = buffer


class NegativeSliceError(ValueError):
    def __init__(self, offset: int, size: int) -> None:
        super().__init__(
            f'Expected non-negative slice values, got offset={offset} size={size}',
        )
        self.size = size
        self.offset = offset


@deal.chain(
    deal.pre(lambda _: _.size >= 0),
    deal.raises(UnexpectedBufferSize),
    deal.reason(UnexpectedBufferSize, lambda _: _.size != len(_.buffer)),
)
def validate_buffer_size(buffer: BufferLike, size: Optional[int] = None) -> BufferLike:
    if size and len(buffer) != size:
        raise UnexpectedBufferSize(size, len(buffer), buffer)
    return buffer


@deal.chain(
    deal.pre(lambda _: _.size >= 0),
    deal.pre(lambda _: 0 <= _.offset <= len(_.buffer)),
    deal.raises(UnexpectedBufferSize),
    deal.reason(UnexpectedBufferSize, lambda _: _.offset + _.size > len(_.buffer)),
    deal.has(),
)
def splice(buffer: BufferLike, offset: int, size: int) -> BufferLike:
    return validate_buffer_size(buffer[offset : offset + size], size)


@dataclass(frozen=True)
class Splicer(object):
    offset: int
    size: int

    def __call__(self, buffer: BufferLike) -> BufferLike:
        return splice(buffer, self.offset, self.size)

    def __post_init__(self) -> None:
        if self.offset < 0 or self.size < 0:
            raise NegativeSliceError(self.offset, self.size)
