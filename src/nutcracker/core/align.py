import io
from typing import IO

def assert_zero(pad: bytes) -> None:
    if pad and set(pad) != {0}:
        raise ValueError(f'non-zero padding between chunks: {pad}')
    return pad

def calc_align(offset: int, align: int) -> int:
    """Calculate difference from given offset to next aligned offset."""
    return (align - offset) % align

def align_read_stream(stream: IO[bytes], align: int = 1) -> None:
    """Align given read stream to next aligned position.
    Verify padding between chunks is zero.
    """
    pos = stream.tell()
    if pos % align == 0:
        return
    pad = stream.read(calc_align(pos, align))
    assert_zero(pad)

def align_write_stream(stream: IO[bytes], align: int = 1) -> None:
    """Align given write stream to next aligned position.
    Pad skipped bytes with zero.
    """
    pos = stream.tell()
    if pos % align == 0:
        return
    stream.write(calc_align(pos, align) * b'\00')

def align_any_stream(stream: IO[bytes], align: int = 1) -> None:
    """Align given stream to next aligned position
    by skipping to the next aligned position
    """
    stream.seek(calc_align(stream.tell(), align), io.SEEK_CUR)
