from dataclasses import dataclass, replace
from typing import Any, TypeVar

from . import iterchunk, settings, tree

_SettingT = TypeVar('_SettingT', bound='_DefaultOverride')


@dataclass(frozen=True)
class _DefaultOverride(object):
    def __call__(self: _SettingT, **kwargs: Any) -> _SettingT:
        return replace(self, **kwargs)


@dataclass(frozen=True)
class _ChunkPreset(settings._ChunkSetting, _DefaultOverride):

    # static pass through
    assert_tag = staticmethod(iterchunk.assert_tag)
    drop_offsets = staticmethod(iterchunk.drop_offsets)
    print_chunks = staticmethod(iterchunk.print_chunks)

    # isort: off
    from .resource import (
        read_chunks,
        write_chunks,
    )
    # isort: on


@dataclass(frozen=True)
class _ShellPreset(settings._IndexSetting, _ChunkPreset):

    # static pass through
    find = staticmethod(tree.find)
    findall = staticmethod(tree.findall)
    findpath = staticmethod(tree.findpath)
    render = staticmethod(tree.render)

    # isort: off
    from .index import (
        map_chunks,
        generate_schema,
    )
    # isort: on


preset = _ChunkPreset()
shell = _ShellPreset()
