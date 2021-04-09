import deal

from .buffer import BufferLike, splice


class NonZeroPaddingError(ValueError):
    def __init__(self, pad: BufferLike) -> None:
        super().__init__(
            f'non-zero padding between chunks: {str(pad)}')
        self.pad = pad


@deal.raises(NonZeroPaddingError)
@deal.reason(NonZeroPaddingError, lambda _: _.pad and set(_.pad) != {0})
@deal.has()
def assert_zero(pad: bytes) -> bytes:
    if pad and set(pad) != {0}:
        raise NonZeroPaddingError(pad)
    return pad


@deal.pre(lambda _: _.align >= 1)
@deal.pre(lambda _: _.offset >= 0)
@deal.ensure(lambda _: 0 <= _.result < _.align)
@deal.ensure(lambda _: (_.offset + _.result) % _.align == 0)
@deal.pure
def calc_align(offset: int, align: int) -> int:
    """Calculate difference from given offset to next aligned offset."""
    return (align - offset) % align


@deal.pre(lambda _: _.align >= 1)
@deal.pre(lambda _: 0 <= _.pos <= len(_.data))
@deal.ensure(lambda _: _.pos <= _.result < _.pos + _.align)
@deal.ensure(lambda _: _.result % _.align == 0)
@deal.raises(NonZeroPaddingError)
@deal.reason(NonZeroPaddingError, lambda _: set(_.data[_.pos:][:calc_align(_.pos, _.align)]) != {0})
@deal.has()
def align_read(data: BufferLike, pos: int, align: int = 1) -> int:
    """Align given read stream to next aligned position.
    Verify padding between chunks is zero.
    """
    pad = assert_zero(splice(data, pos, calc_align(pos, align)))
    return pos + len(pad)


@deal.pre(lambda _: _.align >= 1)
@deal.ensure(lambda _: _.result.startswith(_.data))
@deal.ensure(lambda _: len(_.result) == len(_.data) or set(_.result[len(_.data):]) == {0})
@deal.ensure(lambda _: len(_.data) <= len(_.result) < len(_.data) + _.align)
@deal.ensure(lambda _: len(_.result) % _.align == 0)
@deal.pure
def align_write(data: BufferLike, align: int = 1) -> bytes:
    """Align given write stream to next aligned position.
    Pad skipped bytes with zero.
    """
    pos = len(data)
    return bytes(data) + bytes(calc_align(pos, align))
