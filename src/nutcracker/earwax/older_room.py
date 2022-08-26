
import operator
import pathlib

import os
import struct

from nutcracker.kernel.index import create_element
from .preset import earwax

UINT16LE = struct.Struct('<H')


def read_uint16le(data, offset=0):
    return UINT16LE.unpack_from(data, offset=offset)[0]

def read_room(elem):
    src_file = elem.data

    size = read_uint16le(src_file)
    assert len(src_file) == size

    # print('SIZE', size)

    unk = read_uint16le(src_file, 2)
    width = read_uint16le(src_file, 4)
    height = read_uint16le(src_file, 6)
    unk2 = read_uint16le(src_file, 8)
    im_offs = read_uint16le(src_file, 10)

    elem.children.append(
        create_element(
            4,
            earwax.untag(earwax.mktag('HD', src_file[4:8])),
            path=os.path.join(elem.attribs['path'], f'HDv3'),
        )
    )

    ma_off = read_uint16le(src_file, 12)
    unk_off2 = read_uint16le(src_file, 14)
    unk_off3 = read_uint16le(src_file, 16)
    unk_off4 = read_uint16le(src_file, 18)

    # print('UNKS', ma_off, unk_off2, unk_off3, unk_off4)

    num_objects = src_file[20]
    boxes_off = read_uint16le(src_file, 21)
    num_sounds = src_file[23]
    num_scripts = src_file[24]
    exit_off = read_uint16le(src_file, 25)
    enter_off = read_uint16le(src_file, 27)

    # print(im_offs, num_objects, boxes_off, num_sounds, num_scripts, exit_off, enter_off)

    curroff = 29
    obims = [read_uint16le(src_file, off) for off in range(curroff, curroff + 2 * num_objects, 2)]
    curroff += 2 * num_objects
    assert len(obims) == num_objects, (len(obims), num_objects)
    obcds = [read_uint16le(src_file, off) for off in range(curroff, curroff + 2 * num_objects, 2)]
    curroff += 2 * num_objects
    assert len(obims) == num_objects, (len(obcds), num_objects)

    sounds = src_file[curroff:curroff+num_sounds]
    elem.children.append(
        create_element(
            curroff,
            earwax.untag(earwax.mktag('NL', sounds)),
            path=os.path.join(elem.attribs['path'], f'NLv3'),
        )
    )
    curroff += num_sounds

    scripts = src_file[curroff:curroff+num_scripts]
    elem.children.append(
        create_element(
            curroff,
            earwax.untag(earwax.mktag('SL', scripts)),
            path=os.path.join(elem.attribs['path'], f'SLv3'),
        )
    )
    curroff += num_scripts

    lscripts = []
    while True:
        id = src_file[curroff]
        curroff += 1
        if id == 0:
            break

        lscripts.append((id, read_uint16le(src_file, curroff)))
        curroff += 2

    # print(lscripts)

    # num_boxes = src_file[curroff]
    # boxes = [src_file[curroff + 18 * i: curroff + 18 * (i + 1)] for i in range(num_boxes)]
    bx_block = src_file[curroff: im_offs]
    elem.children.append(
        create_element(
            curroff,
            earwax.untag(earwax.mktag('BX', bx_block)),
            path=os.path.join(elem.attribs['path'], f'BXv3'),
        )
    )
    curroff += len(bx_block)

    assert curroff == im_offs
    im_block = src_file[curroff:ma_off]
    elem.children.append(
        create_element(
            curroff,
            earwax.untag(earwax.mktag('IM', im_block)),
            path=os.path.join(elem.attribs['path'], f'IMv3'),
        )
    )
    curroff += len(im_block)

    offs = obims + sorted(obcds) + [exit_off] + [enter_off] + lscripts

    assert curroff == ma_off
    ma_block = src_file[curroff:offs[0]]
    elem.children.append(
        create_element(
            curroff,
            earwax.untag(earwax.mktag('MA', ma_block)),
            path=os.path.join(elem.attribs['path'], f'MAv3'),
        )
    )
    curroff += len(ma_block)

    # print(offs)
    # TODO: last image

    ocs = sorted([(obcd, idx) for idx, obcd in enumerate(obcds)])
    oboffs = obims + sorted(obcds) + [exit_off]
    # print(ocs)
    for (off, ix), end in zip(ocs, sorted(obcds)[1:] + ([exit_off] if exit_off else [enter_off])):
        if off == end:
            continue
        cd_block = src_file[off:end]
        obj_id = read_uint16le(cd_block, 4)
        elem.children.append(
            create_element(
                off,
                earwax.untag(earwax.mktag('OC', cd_block)),
                path=os.path.join(elem.attribs['path'], f'OCv3_{obj_id:04d}'),
                gid=obj_id,
            )
        )
        # print(f'OCv3_{obj_id:04d}')
        if oboffs[ix] < oboffs[ix+1]:
            im_block = src_file[oboffs[ix]:oboffs[ix+1]]
            elem.children.append(
                create_element(
                    oboffs[ix],
                    earwax.untag(earwax.mktag('OI', im_block)),
                    path=os.path.join(elem.attribs['path'], f'OIv3_{obj_id:04d}'),
                    gid=obj_id,
                )
            )
            # print(f'OIv3_{obj_id:04d}')
        curroff = end

    ex_block = src_file[exit_off:enter_off]
    en_block = src_file[enter_off:lscripts[0][1] if lscripts else size]

    if exit_off > 0:
        elem.children.append(
            create_element(
                exit_off,
                earwax.untag(earwax.mktag('EX', ex_block)),
                path=os.path.join(elem.attribs['path'], f'EXv3'),
            )
        )

    if enter_off > 0:
        elem.children.append(
            create_element(
                enter_off,
                earwax.untag(earwax.mktag('EN', en_block)),
                path=os.path.join(elem.attribs['path'], f'ENv3'),
            )
        )

    lsoffs = [x for _, x in lscripts]
    for (idx, off), end in zip(lscripts, lsoffs[1:] + [size]):
        elem.children.append(
            create_element(
                off,
                earwax.untag(earwax.mktag('LS', src_file[off:end])),
                path=os.path.join(elem.attribs['path'], f'LSv3_{idx:04d}'),
                gid=idx,
            )
        )
        # print(f'LSv3_{idx:04d}', off, end)

    # print(curroff)
    # print(obims)
    # print(obcds)
    # print(scripts)
    # print(sounds)
    # print(lscripts)
    elem.children[:] = sorted(elem.children, key=lambda elem: elem.attribs['offset'])
    # earwax.render(elem)

    return elem
