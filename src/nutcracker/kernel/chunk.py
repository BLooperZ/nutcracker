from dataclasses import dataclass
from functools import cached_property
from struct import Struct
from typing import ClassVar, Iterator, Protocol, Sequence, Union, overload

from .buffer import splice, BufferLike


@dataclass(frozen=True)
class Chunk:
    tag: str
    _buffer: BufferLike
    _slice: slice

    @cached_property
    def data(self) -> bytes:
        return bytes(self._buffer[self._slice])

    def __len__(self) -> int:
        return len(self._buffer)

    def __bytes__(self) -> bytes:
        return bytes(self._buffer)

    def __iter__(self) -> Iterator[Union[str, bytes]]:
        return iter((self.tag, self.data))

    @overload
    def __getitem__(self, index: int) -> Union[str, bytes]: ...
    @overload
    def __getitem__(self, index: slice) -> Sequence[Union[str, bytes]]: ...

    def __getitem__(self, index: Union[slice, int]) -> Union[Sequence[Union[str, bytes]], str, bytes]:
        return tuple(self)[index]

    def __repr__(self) -> str:
        return f'Chunk<{self.tag}>[{len(self)}]'


class ChunkFactory(Protocol):
    def untag(self, buffer: BufferLike, offset: int = 0) -> Chunk:
        ...

    def mktag(self, tag: str, data: bytes) -> bytes:
        ...


@dataclass(frozen=True)
class ScummChunk(ChunkFactory):

    structure: ClassVar[Struct] = Struct('<I2s')

    def untag(self, buffer: BufferLike, offset: int = 0) -> Chunk:
        size, tag = self.structure.unpack_from(buffer, offset)
        return Chunk(
            tag.decode('ascii'),
            splice(buffer, offset, size),
            slice(self.structure.size, size),
        )

    def mktag(self, tag: str, data: bytes) -> bytes:
        return self.structure.pack(tag.encode('ascii'), len(data)) + data


@dataclass(frozen=True)
class IFFChunk(ChunkFactory):
    structure: ClassVar[Struct] = Struct('>4sI')
    INCLUSIVE: ClassVar[int] = 0
    EXCLUSIVE: ClassVar[int] = structure.size

    size_fix: int = EXCLUSIVE

    def untag(self, buffer: BufferLike, offset: int = 0) -> Chunk:
        tag, size = self.structure.unpack_from(buffer, offset)
        if set(tag) == {0} and size == 0:
            size = len(buffer) - offset
        else:
            size += self.size_fix
        return Chunk(
            tag.decode('ascii'),
            splice(buffer, offset, size),
            slice(self.structure.size, size),
        )

    def mktag(self, tag: str, data: bytes) -> bytes:
        etag = tag.encode('ascii')
        if set(etag) == {0}:
            return self.structure.pack(b'', 0) + data
        return self.structure.pack(etag, len(data) - self.size_fix) + data
