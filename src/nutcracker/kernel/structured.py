import struct
from dataclasses import dataclass
from typing import IO, Callable, Generic, Protocol, Sequence, TypeVar, cast

T_Struct = TypeVar('T_Struct')


class Structured(Protocol[T_Struct]):
    @property
    def size(self) -> int:
        ...

    def unpack(self, stream: IO[bytes]) -> T_Struct:
        ...

    def unpack_from(self, data: bytes, offset: int = 0) -> T_Struct:
        ...

    def pack(self, data: T_Struct) -> bytes:
        ...


@dataclass(frozen=True)
class StructuredTuple(Structured, Generic[T_Struct]):
    _fields: Sequence[str]
    _structure: struct.Struct
    _factory: Callable[..., T_Struct]

    @property
    def size(self) -> int:
        return self._structure.size

    def unpack(self, stream: IO[bytes]) -> T_Struct:
        return self.unpack_from(stream.read(self._structure.size))

    def unpack_from(self, data: bytes, offset: int = 0) -> T_Struct:
        factory = cast(Callable[..., T_Struct], self._factory)
        values = self._structure.unpack_from(data, offset=offset)
        return factory(**dict(zip(self._fields, values)))

    def pack(self, data: T_Struct) -> bytes:
        return self._structure.pack(*[getattr(data, field) for field in self._fields])
