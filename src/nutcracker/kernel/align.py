import deal

from .buffer import BufferLike, splice


class NonZeroPaddingError(ValueError):
    def __init__(self, pad: BufferLike) -> None:
        super().__init__(f'non-zero padding between chunks: {str(pad)}')
        self.pad = pad


@deal.chain(
    deal.raises(NonZeroPaddingError),
    deal.reason(NonZeroPaddingError, lambda _: _.pad and set(_.pad) != {0}),
    deal.has(),
)
def assert_zero(pad: bytes) -> bytes:
    if pad and set(pad) != {0}:
        raise NonZeroPaddingError(pad)
    return pad


@deal.chain(
    deal.pre(lambda _: _.align >= 1),
    deal.pre(lambda _: _.offset >= 0),
    deal.ensure(lambda _: 0 <= _.result < _.align),
    deal.ensure(lambda _: (_.offset + _.result) % _.align == 0),
    deal.pure,
)
def calc_align(offset: int, align: int) -> int:
    """Calculate difference from given offset to next aligned offset."""
    return (align - offset) % align


@deal.chain(
    deal.pre(lambda _: _.align >= 1),
    deal.pre(lambda _: 0 <= _.pos <= len(_.buffer)),
    deal.ensure(lambda _: _.pos <= _.result < _.pos + _.align),
    deal.ensure(lambda _: _.result % _.align == 0),
    deal.raises(NonZeroPaddingError),
    deal.reason(
        NonZeroPaddingError,
        lambda _: set(splice(_.buffer, _.pos, calc_align(_.pos, _.align))) != {0},
    ),
    deal.has(),
)
def align_read(buffer: BufferLike, pos: int, align: int = 1) -> int:
    """Align given read stream to next aligned position.
    Verify padding between chunks is zero.
    """
    pad = assert_zero(splice(buffer, pos, calc_align(pos, align)))
    return pos + len(pad)


@deal.chain(
    deal.pre(lambda _: _.align >= 1),
    deal.ensure(lambda _: _.result.startswith(_.buffer)),
    deal.ensure(
        lambda _: len(_.buffer) % _.align == 0 or set(_.result[len(_.buffer) :]) == {0},
    ),
    deal.ensure(lambda _: len(_.buffer) <= len(_.result) < len(_.buffer) + _.align),
    deal.ensure(lambda _: len(_.result) % _.align == 0),
    deal.pure,
)
def align_write(buffer: BufferLike, align: int = 1) -> bytes:
    """Align given write stream to next aligned position.
    Pad skipped bytes with zero.
    """
    pos = len(buffer)
    return bytes(buffer) + bytes(calc_align(pos, align))
