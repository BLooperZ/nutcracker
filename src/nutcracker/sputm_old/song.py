#!/usr/bin/env python3
import io
import os
import pathlib
import struct
import wave
import struct

UINT32LE = struct.Struct('<I')
UINT32LE_x3 = struct.Struct('<3I')

from nutcracker.utils.fileio import read_file

if __name__ == '__main__':
    import argparse

    from nutcracker.sputm.preset import sputm

    parser = argparse.ArgumentParser(description='extract HE music file (HE4)')
    parser.add_argument('filename', help='filename to read from')
    args = parser.parse_args()

    res = read_file(args.filename)
    basename = os.path.basename(args.filename)

    target_dir = pathlib.Path('SONG_OUT') / basename
    os.makedirs(target_dir, exist_ok=True)

    song = next(sputm.map_chunks(res))

    children = iter(song.children)

    sghd = sputm.assert_tag('SGHD', next(children))
    num_songs, = UINT32LE.unpack_from(sghd)
    print(num_songs)

    songs = []

    for i in range(num_songs):
        elem = next(children)
        assert elem.tag == 'SGEN', elem

        songs.append(
            dict(
                zip(
                    ('song', 'offset', 'size'),
                    UINT32LE_x3.unpack_from(elem.data),
                ),
                name=elem.data[UINT32LE_x3.size:]
            )
        )
    
    for s in songs:
        elem = next(children)
        assert elem.tag == 'DIGI', elem
        assert elem.attribs['offset'] + 8 == s['offset'], (elem.attribs['offset'] + 8, s['offset'])
        assert elem.attribs['size'] + 8 == s['size'], (elem.attribs['size'] + 8, s['size'])
        assert s['name'] == b'\0', s['name']

        songid = s['song']
        
        hshd, sdat = elem.children

        with io.BytesIO(hshd.data) as hshd:
            unk1 = struct.unpack('<H', hshd.read(2))[0]  # 0
            unk2 = struct.unpack('<H', hshd.read(2))[0]  # 32896
            unk3 = struct.unpack('<H', hshd.read(2))[0]  # 65535
            sample_rate = struct.unpack('<H', hshd.read(2))[0]
            unk4 = struct.unpack('<H', hshd.read(2))[0]
            unk5 = struct.unpack('<H', hshd.read(2))[0]
            unk6 = struct.unpack('<H', hshd.read(2))[0]
            unk7 = struct.unpack('<H', hshd.read(2))[0]

        with wave.open(str(target_dir / f'{songid}.WAV'), 'w') as wav:
            # aud.write(b'\x80' * frame_audio_size[12] * frame_no)
            wav.setnchannels(1)
            wav.setsampwidth(1)
            wav.setframerate(sample_rate)
            wav.writeframesraw(sdat.data)

    assert not next(children, None)
