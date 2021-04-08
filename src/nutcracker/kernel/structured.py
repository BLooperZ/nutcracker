import struct
from dataclasses import dataclass
from typing import Callable, Generic, IO, Sequence, TypeVar

T = TypeVar('T')


@dataclass
class StructuredTuple(Generic[T]):
    fields: Sequence[str]
    structure: struct.Struct
    factory: Callable[..., T]

    @property
    def size(self) -> int:
        return self.structure.size

    def unpack(self, stream: IO[bytes]) -> T:
        return self.unpack_from(stream.read(self.structure.size))

    def unpack_from(self, data: bytes, offset: int = 0) -> T:
        values = self.structure.unpack_from(data, offset=offset)
        return self.factory(**dict(zip(self.fields, values)))

    def pack(self, data: T) -> bytes:
        return self.structure.pack(*[getattr(data, field) for field in self.fields])
