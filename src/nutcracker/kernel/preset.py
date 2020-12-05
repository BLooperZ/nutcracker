from dataclasses import dataclass, replace
from typing import Any, TypeVar

from . import chunk, settings, tree

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
    print_chunks = staticmethod(chunk.print_chunks)

    from .resource import (
        untag,
        read_chunks,
        mktag,
        write_chunks,
    )


@dataclass(frozen=True)
class _ShellPreset(settings._IndexSetting, _ChunkPreset):

    # static pass through
    find = staticmethod(tree.find)
    findall = staticmethod(tree.findall)
    findpath = staticmethod(tree.findpath)
    render = staticmethod(tree.render)

    from .index import (
        map_chunks,
        generate_schema,
    )


preset = _ChunkPreset()
shell = _ShellPreset()
