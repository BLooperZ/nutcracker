from typing import Optional, Union

import deal

BufferLike = Union[bytes, bytearray, memoryview]

class UnexpectedBufferSize(EOFError):
    def __init__(self, expected: int, given: int, buffer: BufferLike) -> None:
        super().__init__(
            f'Expected buffer of size {expected} but got size {given}')
        self.expected = expected
        self.given = given
        self.buffer = buffer


@deal.pre(lambda _: _.size >= 0)
@deal.raises(UnexpectedBufferSize)
@deal.reason(UnexpectedBufferSize, lambda _: _.size != len(_.buffer))
def validate_buffer_size(buffer: BufferLike, size: Optional[int] = None) -> BufferLike:
    if size and len(buffer) != size:
        raise UnexpectedBufferSize(size, len(buffer), buffer)
    return buffer


@deal.pre(lambda _: _.size >= 0)
@deal.pre(lambda _: 0 <= _.offset <= len(_.data))
@deal.raises(UnexpectedBufferSize)
@deal.reason(UnexpectedBufferSize, lambda _: _.offset + _.size > len(_.data))
@deal.has()
def splice(data: BufferLike, offset: int, size: int) -> BufferLike:
    return validate_buffer_size(data[offset:offset + size], size)
