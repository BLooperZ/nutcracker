import builtins
from dataclasses import dataclass
from functools import cached_property
from typing import IO, Iterator, NamedTuple, Protocol, Sequence, Union, overload

from .buffer import BufferLike, Splicer, splice
from .structured import Structured


class ChunkHeader(NamedTuple):
    etag: bytes
    size: int


@dataclass(frozen=True)
class Chunk(object):
    tag: str
    buffer: BufferLike
    slice: Splicer

    @cached_property
    def data(self) -> bytes:
        return bytes(self.slice(self.buffer))

    def __len__(self) -> int:
        return len(self.buffer)

    def __bytes__(self) -> bytes:
        return bytes(self.buffer)

    def __iter__(self) -> Iterator[Union[str, bytes]]:
        return iter((self.tag, self.data))

    @overload
    def __getitem__(self, index: int) -> Union[str, bytes]:
        ...

    @overload
    def __getitem__(self, index: builtins.slice) -> Sequence[Union[str, bytes]]:
        ...

    def __getitem__(
        self,
        index: Union[builtins.slice, int],
    ) -> Union[Sequence[Union[str, bytes]], str, bytes]:
        return tuple(self)[index]

    def __repr__(self) -> str:
        return 'Chunk<{tag}>[{size}]'.format(tag=self.tag, size=len(self))


class ChunkFactory(Protocol):
    def untag(self, buffer: BufferLike, offset: int = 0) -> Chunk:
        ...

    def mktag(self, tag: str, data: bytes) -> bytes:
        ...


@dataclass(frozen=True)
class _StructuredChunkHeader(Structured[ChunkHeader]):
    _struct: Structured[ChunkHeader]

    @property
    def size(self) -> int:
        return self._struct.size

    def unpack(self, stream: IO[bytes]) -> ChunkHeader:
        return self.unpack_from(stream.read(self.size))

    def unpack_from(self, buffer: BufferLike, offset: int = 0) -> ChunkHeader:
        return self._struct.unpack_from(buffer, offset)

    def pack(self, data: ChunkHeader) -> bytes:
        return self._struct.pack(data)


@dataclass(frozen=True)
class StructuredChunk(ChunkFactory, _StructuredChunkHeader):
    def untag(self, buffer: BufferLike, offset: int = 0) -> Chunk:
        header = self.unpack_from(buffer, offset)
        splicer = Splicer(self.size, header.size - self.size)
        return Chunk(
            header.etag.decode('ascii'),
            splice(buffer, offset, header.size),
            splicer,
        )

    def mktag(self, tag: str, data: bytes) -> bytes:
        return self.pack(ChunkHeader(tag.encode('ascii'), len(data) + self.size)) + data

NULL_TAG = b'_'

@dataclass(frozen=True)
class SizeFixedChunk(StructuredChunk):
    size_fix: int = 0

    def unpack_from(self, buffer: BufferLike, offset: int = 0) -> ChunkHeader:
        etag, size = self._struct.unpack_from(buffer, offset)
        if set(etag) == {0} and size == 0:
            return ChunkHeader(NULL_TAG, len(buffer) - offset)
        return ChunkHeader(etag, size + self.size_fix)

    def pack(self, data: ChunkHeader) -> bytes:
        if data.etag == NULL_TAG:
            return self._struct.pack(ChunkHeader(b'', 0))
        return self._struct.pack(ChunkHeader(data.etag, data.size - self.size_fix))

@dataclass(frozen=True)
class OldSputmChunk(StructuredChunk):
    size_fix: int = 0

    def unpack_from(self, buffer: BufferLike, offset: int = 0) -> ChunkHeader:
        etag, size = self._struct.unpack_from(buffer, offset)
        if set(etag) == {0}:
            etag = NULL_TAG
        return ChunkHeader(etag, size + self.size_fix)

    def pack(self, data: ChunkHeader) -> bytes:
        etag = data.etag
        if etag == NULL_TAG:
            etag = b'\0\0'
        return self._struct.pack(ChunkHeader(etag, data.size - self.size_fix))
