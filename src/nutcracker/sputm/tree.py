#!/usr/bin/env python3

import io
import os
import struct
from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping, Optional, Set, Tuple

from nutcracker.utils.fileio import read_file

from .index import (
    compare_pid_off,
    read_directory,
    read_index_he,
    read_index_v5tov7,
    read_index_v7,
    read_index_v8,
)
from .schema import SCHEMA
from .preset import sputm
from .resource import Game, load_resource
from .types import Chunk

UINT32LE = struct.Struct('<I')


@dataclass(frozen=True)
class GameResourceConfig:
    read_index: Callable
    max_depth: int
    base_fix: int = 0


@dataclass(frozen=True)
class GameResource:
    game: Game
    config: GameResourceConfig
    rooms: Mapping[int, str]
    idgens: Any

    @property
    def basename(self):
        return self.game.basename

    @property
    def root(self):
        return read_game_resources(self.game, self.config, self.idgens)

    def read_resources(self, **kwargs):
        return read_game_resources(self.game, self.config, self.idgens, **kwargs)


def save_tree(cfg, element, basedir='.'):
    if not element:
        return
    path = os.path.join(basedir, element.attribs['path'])
    if element.children:
        os.makedirs(path, exist_ok=True)
        for c in element.children:
            save_tree(cfg, c, basedir=basedir)
    else:
        with open(path, 'wb') as f:
            f.write(cfg.mktag(element.tag, element.data))


def read_game_resources(game: Game, config: GameResourceConfig, idgens, **kwargs):
    _, *disks = game.disks

    for didx, disk in enumerate(disks):

        resource = read_file(os.path.join(game.basedir, disk), key=game.chiper_key)

        # # commented out, use pre-calculated index instead,
        # # as calculating is time-consuming
        # s = sputm.generate_schema(resource)
        # pprint.pprint(s)
        # root = sputm.map_chunks(resource, idgen=idgens, schema=s)

        paths: Dict[str, Chunk] = {}
        wraps: Dict[str, Dict[int, int]] = {}

        def update_element_path(parent, chunk, offset):

            if chunk.tag == 'LOFF':
                # should not happen in HE games

                offs = dict(read_directory(chunk.data))

                # # to ignore cloned rooms
                # droo = idgens['LFLF']
                # droo = {k: v for k, v  in droo.items() if v == (didx + 1, 0)}
                # droo = {k: (disk, offs[k]) for k, (disk, _)  in droo.items()}

                droo = {k: (didx + 1, v) for k, v in offs.items()}
                idgens['LFLF'] = compare_pid_off(droo, 16 - config.base_fix)

            get_gid = idgens.get(chunk.tag)
            if not parent:
                gid = didx + 1
            elif parent.attribs['path'] in wraps:
                gid = wraps[parent.attribs['path']].get(offset)
            else:
                gid = get_gid and get_gid(
                    parent and parent.attribs['gid'], chunk.data, offset
                )

            base = chunk.tag + (
                f'_{gid:04d}'
                if gid is not None
                else ''
                if not get_gid
                else f'_o_{offset:04X}'
            )

            dirname = parent.attribs['path'] if parent else ''
            path = os.path.join(dirname, base)

            if path in paths:
                path += 'd'
            # assert path not in paths, path
            paths[path] = chunk

            if chunk.tag == 'WRAP':
                offs = sputm.untag(chunk.data)
                size = len(offs.data) // 4
                offs = dict(
                    zip(struct.unpack(f'<{size}I', offs.data), range(1, size + 1))
                )
                wraps[path] = offs

            res = {'path': path, 'gid': gid}
            return res

        yield from sputm(**kwargs).map_chunks(resource, extra=update_element_path)


def create_config(game: Game) -> GameResourceConfig:
    print(game)
    if game.version >= 8:
        read_index = read_index_v8
        max_depth = 4
        base_fix = 8
        return GameResourceConfig(read_index, max_depth, base_fix)

    if game.version >= 7:
        read_index = read_index_v7
        max_depth = 4
        base_fix = 0
        return GameResourceConfig(read_index, max_depth, base_fix)

    if game.he_version >= 70:
        read_index = read_index_he
        max_depth = 4
        base_fix = 0
        return GameResourceConfig(read_index, max_depth, base_fix)

    if game.version >= 5:
        read_index = read_index_v5tov7
        max_depth = 4
        base_fix = 0
        return GameResourceConfig(read_index, max_depth, base_fix)

    raise NotImplementedError('SCUMM < 5 is not implemented')


def open_game_resource(filename: str, version: Optional[Tuple[int, int]] = None) -> GameResource:
    game = load_resource(filename)

    if version:
        game.version, game.he_version = version
    config = create_config(game)

    rooms, idgens = config.read_index(game.index)

    return GameResource(game, config, rooms, idgens)


def dump_resources(
    gameres: GameResource, basename: str, schema: Optional[Mapping[str, Set]] = None
):
    schema = schema or narrow_schema(
        SCHEMA,
        {'LECF', 'LFLF', 'RMDA', 'ROOM'},
    )
    os.makedirs(basename, exist_ok=True)
    root = gameres.read_resources(schema=schema)
    with open(os.path.join(basename, 'rpdump.xml'), 'w') as f:
        for disk in root:
            sputm.render(disk, stream=f)
            save_tree(sputm, disk, basedir=basename)


def narrow_schema(schema, trail):
    new_schema = dict(schema)
    for container in schema:
        if container not in trail:
            new_schema[container] = set()
    return new_schema
