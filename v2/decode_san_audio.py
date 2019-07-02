#!/usr/bin/env python3
import io

import smush

from fobj import unobj, mkobj
from ahdr import parse_header
from codex import get_decoder
from image import save_single_frame_image

import struct
from functools import partial


frame_audio_size = {
    12: 7352 // 2,
	10: 8802 // 2
}

def clip(lower, upper, value):
    return lower if value < lower else upper if value > upper else value

clip_byte = partial(clip, 0, 255)

def readcstr(f):
    return ''.join(iter(lambda: f.read(1).decode(), '\00'))

def read_le_uint16(f):
    return struct.unpack('<H', f[:2])[0]

def read_le_uint32(f):
    return struct.unpack('<I', f[:4])[0]

def handle_sound_buffer(track_id, index, max_frames, flags, vol, pan, chunk, size, frame_no):
    fname = f'sound/PSAD_{track_id:04d}.RAW'
    if index == 0:
        c_stream = io.BytesIO(chunk)
        saud = smush.assert_tag('SAUD', smush.untag(c_stream))
        assert c_stream.read() == b''
        for tag, data in smush.read_chunks(saud):
            if tag == 'SDAT':
                print('first length', len(data))
                with open(fname, 'wb') as aud:
                    # aud.write(b'\x80' * frame_audio_size[12] * frame_no)
                    aud.write(data)
            elif tag == 'STRK':
                print(data)
            else:
                raise ValueError(f'Unknown audio tag: {tag}')
    else:
        print('other length', len(chunk))
        with open(fname, 'ab') as aud:
            aud.write(chunk) 
FLAG_UNSIGNED = 1 << 0
FLAG_16BITS = 1 << 1
FLAG_LITTLE_ENDIAN = 1 << 2

def handle_sound_frame(chunk, frame_no):
    track_id = read_le_uint16(chunk)
    index = read_le_uint16(chunk[2:])
    max_frames = read_le_uint16(chunk[4:])
    flags = read_le_uint16(chunk[6:])
    vol = chunk[8]
    pan = chunk[9]
    if index == 0:
        print(f'track_id:{track_id}, max_frames:{max_frames}, flags:{flags}, vol:{vol}, pan:{pan}')     
        print(f'unsigned: {flags & FLAG_UNSIGNED}')
        print(f'16bit: {flags & FLAG_16BITS}')
        print(f'le: {flags & FLAG_LITTLE_ENDIAN}')
    handle_sound_buffer(track_id, index, max_frames, flags, vol, pan, chunk[10:], len(chunk) - 10, frame_no)

def convert_fobj(datam):
    meta, data = unobj(datam)
    width = meta['x2'] - meta['x1']
    height = meta['y2'] - meta['y1']
    decode = get_decoder(meta['codec'])
    if decode == NotImplemented:
        print(f"Codec not implemented: {meta['codec']}")
        return None

    if meta['x1'] != 0 or meta['y1'] != 0:
        print('TELL ME')

    print(meta)

    locs = {'x1': meta['x1'], 'y1': meta['y1'], 'x2': meta['x2'], 'y2': meta['y2']}
    return locs, decode(width, height, data)

def non_parser(chunk):
    return chunk

def parse_frame(frame, parsers):
    chunks = list(smush.read_chunks(frame))
    return [(tag, parsers.get(tag, non_parser)(chunk)) for tag, chunk in chunks]

def verify_nframes(frames, nframes):
    for idx, frame in enumerate(frames):
        if nframes and idx > nframes:
            raise ValueError('too many frames')
        yield frame

def filter_chunk_once(chunks, target):
    return next((frame for tag, frame in chunks if tag == target), None)

def delta_color(org_color, delta_color):
    return clip_byte((org_color * 129 + delta_color) // 128)

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('filename', help='filename to read from')
    args = parser.parse_args()

    with smush.open(args.filename) as smush_file:
        header = parse_header(smush_file.header)
        print(header['palette'][39])

        palette = header['palette']

        frames = verify_nframes(smush_file, header['nframes'])
        frames = (list(smush.read_chunks(frame)) for frame in frames)

        # parsers = {
        #     'FOBJ': convert_fobj
        # }

        # frames = (frame for idx, frame in enumerate(frames) if 1050 > idx)
        # parsed_frames = list(parse_frame(frame, parsers) for frame in frames)

        # for idx, frame in enumerate(parsed_frames):
        #     print((idx, [tag for tag, chunk in frame]))

        # image_frames = ((filter_chunk_once(parsed, 'FOBJ'), filter_chunk_once(parsed, 'NPAL')) for parsed in parsed_frames)
        # image_frames, pal_frames = zip(*image_frames)
        # frames_pil = save_frame_image(image_frames)

        palette = [x for l in palette for x in l]
        screen = []

        delta_pal = []


        for idx, frame in enumerate(frames):
            print(f'{idx} - {[tag for tag, _ in frame]}')

            for tag, chunk in frame:
                if tag == 'PSAD':
                    handle_sound_frame(chunk, idx)
                # if tag == 'NPAL':
                #     palette = list(zip(*[iter(chunk)]*3))
                #     palette = [x for l in palette for x in l]
                #     continue
                # if tag == 'XPAL':

                #     sub_size = len(chunk)
                #     print(f'{idx} - XPAL {sub_size}')

                #     if sub_size == 0x300 * 3 + 4:
                #         delta_pal = struct.unpack(f'<{0x300}h', chunk[4:4 + 2 * 0x300])
                #         palette = list(zip(*[iter(chunk[4 + 2 * 0x300:])]*3))
                #         palette = [x for l in palette for x in l]

                #     if sub_size == 6:

                #         print(f'{idx} - XPAL 6 {chunk}')
                #         palette = [delta_color(palette[i], delta_pal[i]) for i in range(0x300)]
                #         # print(f'NEW PALETTE: {palette}')

                # elif tag == 'FOBJ':
                #     screen = convert_fobj(chunk)
                #     continue
                else:
                    # print(f'TAG {tag} not implemented yet')
                    continue
            # im = save_single_frame_image(screen)
            # # im = im.crop(box=(0,0,320,200))
            # im.putpalette(palette)
            # im.save(f'out/FRME_{idx:05d}.png')           
