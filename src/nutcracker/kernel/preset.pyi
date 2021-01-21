from dataclasses import dataclass, replace
from typing import Any, Callable, Dict, IO, Iterable, Iterator, Optional, Set, Tuple, TypeVar

from . import types, settings

_SettingT = TypeVar('_SettingT', bound='_DefaultOverride')


@dataclass(frozen=True)
class _DefaultOverride:
    def __call__(self: _SettingT, **kwargs: Any) -> _SettingT:
        return replace(self, **kwargs)


class _ChunkPreset(settings._ChunkSetting, _DefaultOverride):
    def assert_tag(self, target: str, chunk: types.Chunk) -> bytes: ...

    def print_chunks(
        self,
        chunks: Iterable[Tuple[int, types.Chunk]],
        level: int = ...,
        base: int = ...,
    ) -> Iterator[Tuple[int, types.Chunk]]: ...

    def drop_offsets(
        self, chunks: Iterable[Tuple[int, types.Chunk]]
    ) -> Iterator[types.Chunk]: ...

    def untag(self, stream: IO[bytes]) -> types.Chunk: ...

    def read_chunks(self, data: bytes) -> Iterator[Tuple[int, types.Chunk]]: ...

    def mktag(self, tag: str, data: bytes) -> bytes: ...

    def write_chunks(self, chunks: Iterable[bytes]) -> bytes: ...


class _ShellPreset(settings._IndexSetting, _ChunkPreset):
    def findall(self, tag: str, root: types.ElementTree) -> Iterator[types.Element]: ...

    def find(self, tag: str, root: types.ElementTree) -> Optional[types.Element]: ...

    def findpath(
        self, path: str, root: Optional[types.Element]
    ) -> Optional[types.Element]: ...

    def render(
        self, element: Optional[types.Element], level: int = ..., stream: IO[str] = ...
    ) -> None: ...

    def map_chunks(
        self,
        data: bytes,
        parent: Optional[types.Element] = ...,
        level: int = ...,
        extra: Optional[
            Callable[[Optional[types.Element], types.Chunk, int], Dict[str, Any]]
        ] = ...,
    ) -> Iterator[types.Element]: ...

    def generate_schema(self, data: bytes) -> Dict[str, Set[str]]: ...


shell: _ShellPreset = ...
