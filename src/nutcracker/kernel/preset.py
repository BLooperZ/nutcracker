from dataclasses import dataclass, replace
from typing import Any, TypeVar

from . import resource, chunk, settings
from .types import Chunk

_SettingT = TypeVar('_SettingT', bound='_DefaultOverride')

@dataclass(frozen=True)
class _DefaultOverride:
    def __call__(self: _SettingT, **kwargs: Any) -> _SettingT:
        return replace(self, **kwargs)

@dataclass(frozen=True)
class _ChunkPreset(settings._ChunkSetting, _DefaultOverride):

    # static pass through
    assert_tag = staticmethod(chunk.assert_tag)
    drop_offsets = staticmethod(chunk.drop_offsets)

    untag = resource.untag
    read_chunks = resource.read_chunks

from . import tree, index

@dataclass(frozen=True)
class _ShellPreset(settings._IndexSetting, _ChunkPreset):

    # static pass through
    find = staticmethod(tree.find)
    findall = staticmethod(tree.findall)
    findpath = staticmethod(tree.findpath)
    render = staticmethod(tree.render)

    map_chunks = index.map_chunks
    generate_schema = index.generate_schema

preset = _ChunkPreset()
shell = _ShellPreset()
