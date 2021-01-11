import struct
from dataclasses import dataclass
from typing import Generic, IO, Sequence, TypeVar, Callable


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
        values = self.structure.unpack(stream.read(self.structure.size))
        return self.factory(**dict(zip(self.fields, values)))

    def pack(self, data: T) -> bytes:
        return self.structure.pack(*[getattr(data, field) for field in self.fields])
