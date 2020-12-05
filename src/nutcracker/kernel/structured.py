import struct
from typing import Generic, IO, Protocol, Sequence, TypeVar, Callable


T = TypeVar('T')


class Structured(Protocol, Generic[T]):
    size: int

    def unpack(self, stream: IO[bytes]) -> T:
        pass

    def pack(self, data: T) -> bytes:
        pass


def structured_tuple(
    fields: Sequence[str], structure: struct.Struct, base: Callable[..., T]
) -> Structured[T]:
    def unpack(stream: IO[bytes]) -> T:
        return base(**dict(zip(fields, structure.unpack(stream.read(structure.size)))))

    def pack(data: T) -> bytes:
        return structure.pack(*[getattr(data, field) for field in fields])

    return type(
        base.__name__,
        (),
        {
            'size': structure.size,
            'unpack': staticmethod(unpack),
            'pack': staticmethod(pack),
        },
    )()
