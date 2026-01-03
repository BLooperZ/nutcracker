#!/usr/bin/env python3

import io
import os
from collections.abc import Iterable, Iterator, Sequence

from nutcracker.kernel2.chunk import Chunk
from nutcracker.kernel2.element import Element
from nutcracker.kernel2.fileio import read_file, write_file
from nutcracker.sputm.tree import GameResource, GameResourceConfig

from .index import (
    read_directory_leg as read_dir,
)
from .index import (
    read_directory_leg_v8 as read_dir_v8,
)
from .index import (
    read_dlfl,
)
from .preset import sputm


def write_dlfl(index) -> bytes:
    yield len(index).to_bytes(2, byteorder='little', signed=False)
    yield b''.join(
        off.to_bytes(4, byteorder='little', signed=False) for off in index.values()
    )


def write_dir(index) -> bytes:
    yield len(index).to_bytes(2, byteorder='little', signed=False)
    rooms, offsets = zip(*index.values())
    yield b''.join(room.to_bytes(1, byteorder='little', signed=False) for room in rooms)
    yield b''.join(off.to_bytes(4, byteorder='little', signed=False) for off in offsets)


def write_dir_v8(index) -> bytes:
    yield len(index).to_bytes(4, byteorder='little', signed=False)
    rooms, offsets = zip(*index.values())
    yield b''.join(room.to_bytes(1, byteorder='little', signed=False) for room in rooms)
    yield b''.join(off.to_bytes(4, byteorder='little', signed=False) for off in offsets)


def bind_directory_changes(read, write, orig, mapping) -> bytes:
    bound = {**dict(read(orig)), **mapping}
    data = b''.join(write(bound))
    return data + orig[len(data) :]


def make_index_from_resource(
    resource: Iterable[Element], ref: Iterable[Element], base_fix: int = 0
) -> Iterator[Chunk]:
    maxs = {}
    diri = {}
    dirr = {}
    dirs = {}
    dirn = {}
    dirc = {}
    dirf = {}
    dirm = {}
    dirt = {}
    dlfl = {}
    rnam = {}
    dobj = {}
    aary = {}

    resmap = {
        'RMDA': dirr,
        'RMSC': dirr,
        'SCRP': dirs,
        'DIGI': dirn,
        'SOUN': dirn,
        'AKOS': dirc,
        'CHAR': dirf,
        'MULT': dirm,
        'AWIZ': dirm,
        'COST': dirc,
        'TALK': dirn,
        'TLKE': dirt,
    }

    dirmap = {
        # Humoungus Entertainment games
        'DIRI': diri,
        'DIRR': dirr,
        'DIRS': dirs,
        'DIRN': dirn,
        'DIRC': dirc,
        'DIRF': dirf,
        'DIRM': dirm,
        'DIRT': dirt,
        # LucasArts SCUMM games
        'DSCR': dirs,
        'DRSC': dirr,
        'DSOU': dirn,
        'DCOS': dirc,
        'DCHR': dirf,
    }

    for t in resource:
        # sputm.render(t)
        for lflf in sputm.findall('LFLF', t):
            diri[lflf.attribs['gid']] = (lflf.attribs['gid'], 0)
            dlfl[lflf.attribs['gid']] = lflf.attribs['offset'] + 16
            for elem in lflf.children():
                if elem.tag in resmap and elem.attribs.get('gid'):
                    resmap[elem.tag][elem.attribs['gid']] = (
                        lflf.attribs['gid'],
                        elem.attribs['offset'] + base_fix,
                    )

    def build_index(root: Iterable[Element]) -> Iterator[Chunk]:
        for elem in root:
            tag, data = elem.tag, elem.data

            reader, writer = (
                (read_dir_v8, write_dir_v8) if base_fix == 8 else (read_dir, write_dir)
            )

            if tag == 'DLFL':
                data = bind_directory_changes(read_dlfl, write_dlfl, elem.data, dlfl)
            if tag in dirmap:
                data = bind_directory_changes(reader, writer, elem.data, dirmap[tag])

            yield sputm.mktag(tag, data)

    return build_index(ref)


def update_element(
    basedir: str,
    elements: Iterable[Element],
    files: dict[str, bytes],
) -> Iterator[Element]:
    offset = 0
    for elem in elements:
        elem.attribs['offset'] = offset
        full_path = os.path.join(basedir, elem.attribs.get('path'))
        if full_path in files:
            print(elem.attribs.get('path'))
            if os.path.isfile(full_path):
                attribs = elem.attribs
                elem = next(sputm.map_chunks(read_file(full_path)))
                elem.attribs = attribs
            else:
                elem.update_children(update_element(basedir, elem.children(), files))
        offset += len(elem.data) + 8
        elem.attribs['size'] = len(elem.data)
        yield elem


def update_loff(config: GameResourceConfig, disk: Element) -> None:
    """Update LOFF chunk if exists"""
    loff = sputm.find('LOFF', disk)
    if loff:
        rooms = list(sputm.findall('LFLF', disk))
        with io.BytesIO() as stream:
            stream.write(bytes([len(rooms)]))
            for room in rooms:
                room_id = room.attribs['gid']
                room_off = room.attribs['offset'] + 16 - config.base_fix
                stream.write(room_id.to_bytes(1, byteorder='little', signed=False))
                stream.write(room_off.to_bytes(4, byteorder='little', signed=False))
            loff_data = stream.getvalue()
        assert len(loff.data) == len(loff_data)
        loff.update_raw(loff_data)


def rebuild_resources(
    gameres: GameResource,
    basename: str,
    updated_resource: Sequence[Element],
) -> None:
    index_file, *disks = gameres.game.disks
    for t, disk in zip(updated_resource, disks, strict=True):
        update_loff(gameres.config, t)

        _, ext = os.path.splitext(disk)
        write_file(
            f'{basename}{ext}',
            bytes(
                sputm.mktag(
                    t.tag,
                    memoryview(
                        sputm.write_chunks(
                            sputm.mktag(e.tag, e.data) for e in t.children()
                        )
                    ),
                )
            ),
            key=gameres.game.chiper_key,
        )

    _, ext = os.path.splitext(index_file)
    write_file(
        f'{basename}{ext}',
        sputm.write_chunks(
            make_index_from_resource(
                updated_resource,
                gameres.game.index,
                gameres.config.base_fix,
            ),
        ),
        key=gameres.game.chiper_key,
    )


# ## REFERENCE
# <MAXS ---- path="MAXS" />
# <DIRI ---- path="DIRI" />
# <DIRR ---- path="DIRR" />
# <DIRS ---- path="DIRS" />
# <DIRN ---- path="DIRN" />
# <DIRC ---- path="DIRC" />
# <DIRF ---- path="DIRF" />
# <DIRM ---- path="DIRM" />
# <DLFL ---- path="DLFL" />
# <RNAM ---- path="RNAM" />
# <DOBJ ---- path="DOBJ" />
# <AARY ---- path="AARY" />
