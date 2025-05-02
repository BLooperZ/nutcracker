import logging
from abc import ABC
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, replace
from operator import attrgetter
from typing import (
    ClassVar,
    Generic,
    Literal,
    Protocol,
    Self,
    TypedDict,
    TypeVar,
    cast,
    overload,
)

import numpy as np
from numpy.typing import NDArray

ArrayBuffer = NDArray[np.uint8] | memoryview


class HeaderDType(Protocol):
    itemsize: ClassVar[int]
    names: ClassVar[tuple[str, str]]

    def tobytes(self) -> bytes: ...


T = TypeVar('T')


class ChunkHeaderDict(TypedDict):
    tag: bytes
    size: int


@dataclass(frozen=True, slots=True)
class ChunkHeaderData:
    tag: bytes
    size: int


class StructuredTuple(ABC, Generic[T]):
    __slots__ = ('_header',)
    dtype: ClassVar[type[HeaderDType]]

    def __init__(self, header: HeaderDType) -> None:
        self._header = header

    @classmethod
    def itemsize(cls) -> int:
        return cls.dtype.itemsize

    @classmethod
    def from_buffer(cls, buffer: ArrayBuffer) -> Self:
        chunk_header = np.frombuffer(buffer, dtype=cls.dtype, count=1)[0]
        return cls(chunk_header)

    def __bytes__(self) -> bytes:
        return self._header.tobytes()

    @classmethod
    def create(cls, data: T) -> Self:
        assert cls.dtype.names
        assert set(cls.dtype.names) == set(data.__class__.__annotations__)
        htuple = attrgetter(*cls.dtype.names)(data)
        header = np.array([htuple], dtype=cls.dtype)[0]
        return cls(header)


class ChunkHeader(StructuredTuple[ChunkHeaderData]):
    @property
    def tag(self) -> bytes:
        return cast(ChunkHeaderDict, self._header)['tag']

    @property
    def size(self) -> int:
        return cast(ChunkHeaderDict, self._header)['size']


class IFFChunkHeader(ChunkHeader):
    dtype = cast(
        type[HeaderDType],
        np.dtype(
            [
                ('tag', 'S4'),  # 4-byte string for the tag
                ('size', '>u4'),  # 4-byte unsigned int for the size
            ],
        ),
    )

    @classmethod
    def create(cls, data: ChunkHeaderData) -> Self:
        if not data.tag:
            data = replace(data, size=0)
        return super().create(data)


@dataclass(frozen=True)
class ChunkSettings:
    header_dtype: type[ChunkHeader]
    alignment: int
    inclheader: bool
    skip_byte: int | None = None


class ChunkLike(Protocol):
    @property
    def tag(self) -> str:
        """Return the chunk tag."""

    @property
    def data(self) -> ArrayBuffer:
        """Return the chunk data buffer."""


NULL_TAG = '_'


@dataclass(frozen=True, slots=True)
class Chunk:
    header: ChunkHeader
    data: ArrayBuffer

    @property
    def tag(self) -> str:
        if not self.header.tag:
            return NULL_TAG
        return self.header.tag.decode('ascii')

    def __len__(self) -> int:
        return len(self.data)

    def __bytes__(self) -> bytes:
        return bytes(self.header) + memoryview(self.data).tobytes()

    def __iter__(self) -> Iterator[str | ArrayBuffer]:
        return iter((self.tag, self.data))

    @overload
    def __getitem__(self, index: Literal[0]) -> str: ...
    @overload
    def __getitem__(self, index: Literal[1]) -> ArrayBuffer: ...
    @overload
    def __getitem__(self, index: int) -> str | ArrayBuffer: ...
    @overload
    def __getitem__(self, index: slice) -> Sequence[str | ArrayBuffer]: ...
    def __getitem__(
        self,
        index: slice | int,
    ) -> Sequence[str | ArrayBuffer] | str | ArrayBuffer:
        return tuple(self)[index]

    def __repr__(self) -> str:
        return f'Chunk<{self.tag}>[{len(self)}]'


def read_chunk_header(
    cfg: ChunkSettings,
    buffer: ArrayBuffer,
    offset: int = 0,
) -> tuple[int, ChunkHeader]:
    header_data = buffer[offset : offset + cfg.header_dtype.itemsize()]
    chunk_header = cfg.header_dtype.from_buffer(header_data)
    return offset + cfg.header_dtype.itemsize(), chunk_header


class UnexpectedBufferSizeError(ValueError):
    def __init__(self, expected: int, given: int, buffer: ArrayBuffer) -> None:
        super().__init__(f'chunk data size mismatch: {expected} != {given}')
        self.expected = expected
        self.given = given
        self.buffer = buffer


def nslice(buffer: ArrayBuffer, start: int, end: int) -> ArrayBuffer:
    res = buffer[start:end]
    assert getattr(res, 'nbytes', len(res)) == len(res)
    if len(res) != end - start:
        raise UnexpectedBufferSizeError(len(res), end - start, buffer)
    return res


def untag(
    cfg: ChunkSettings,
    buffer: ArrayBuffer,
    offset: int = 0,
) -> tuple[int, Chunk]:
    offset, chunk_header = read_chunk_header(cfg, buffer, offset)

    if set(bytes(chunk_header)) == {0}:
        end = len(buffer)
    else:
        end = int(offset + chunk_header.size)

        if cfg.inclheader:
            end -= cfg.header_dtype.itemsize()
    chunk_data = nslice(buffer, offset, end)
    return end, Chunk(chunk_header, chunk_data)


def calc_align(offset: int, align: int) -> int:
    """Calculate difference from given offset to next aligned offset."""
    return (align - offset) % align


def read_chunks(
    cfg: ChunkSettings,
    buffer: ArrayBuffer,
    offset: int = 0,
) -> Iterator[tuple[int, Chunk]]:
    while offset < len(buffer):
        offset = workaround_x80(cfg, buffer, offset)
        noffset, chunk = untag(cfg, buffer, offset)
        yield offset, chunk
        offset = noffset + calc_align(noffset, cfg.alignment)


def mktag(
    cfg: ChunkSettings,
    tag: str,
    buffer: ArrayBuffer,
) -> Chunk:
    size = len(buffer)
    if tag == NULL_TAG:
        tag = ''
    if cfg.inclheader:
        size += cfg.header_dtype.itemsize()
    header = cfg.header_dtype.create(
        ChunkHeaderData(tag=tag.encode('ascii'), size=size),
    )
    return Chunk(header, buffer)


def workaround_x80(
    cfg: ChunkSettings,
    buffer: ArrayBuffer,
    offset: int = 0,
) -> int:
    """WORKAROUND: in Pajama Sam 2, some DIGI chunks are off by 1.
    header appears as '\\x80DIG' and index indicate they should start 1 byte afterwards.
    since header tag needs to be ASCII, it's low risk.
    """
    if cfg.skip_byte is not None and buffer[offset] == cfg.skip_byte:
        getattr(cfg, 'logger', logging).warning(
            f'found \\x{cfg.skip_byte:02x} between chunks, skipping 1 byte...',
        )
        return offset + 1
    return offset


def write_chunks(cfg: ChunkSettings, chunks: Iterable[Chunk]) -> bytes:
    stream = bytearray()
    for chunk in chunks:
        content = bytes(chunk)
        stream += content + bytes(calc_align(len(content), cfg.alignment))
    return bytes(stream)


class UnexpectedTagError(ValueError):
    def __init__(self, expected: str, got: str) -> None:
        super().__init__(f'expected tag to be {expected} but got {got}')


def assert_tag(target: str, chunk: 'ChunkLike') -> 'ArrayBuffer':
    """Return chunk data if chunk has target 4CC tag."""
    if chunk.tag != target:
        raise UnexpectedTagError(target, chunk.tag)
    return chunk.data
