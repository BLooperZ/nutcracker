import sys
from itertools import cycle, chain, izip
from modules.smush import encode_frames, decode_frames
from modules.smush import read_nut_file, write_nut_file
from modules.gen import from_font_image
from modules.image import save_image, read_image

def save_binary_file(filename, data):
    with open(filename, 'wb') as f:
        f.write(data)

def save_char_file(idx, data):
    save_binary_file('FONTS/CHAR{:03}'.format(idx), data)

def split_chars(chars):
    for idx, char in enumerate(chars):
        save_char_file(idx, char)

def pad_bg(w, h):
    def pad(char, bg):
        bgc = [bg for _ in range(w)]
        width, height, lines = char
        return [line + bgc[width:] for line in lines] + [bgc for _ in range(h - height)]
    return pad

def filter_chars(chars, indices):
    return (char for idx, char in enumerate(chars) if idx in indices)

def font_image(numChars, chars):
    w = 39
    bgs = cycle([32, 64])

    char = next(chars)
    height = char[1]
    h = ((height / 12) + 1) * 12

    pad = pad_bg(w, h)

    first = pad(char, next(bgs))
    rest = chain.from_iterable(pad(char, bg) for char, bg in izip(chars, bgs))
    data = chain(first, rest)
    return w, numChars * h, data

def save_char_files(chars):
    chars = list(chars)
    for idx, char in enumerate(chars):
        save_char_file(idx, char)
    return (char for char in chars)

def save_char_images(chars):
    chars = list(chars)
    for idx, char in enumerate(chars):
        save_image('PNG/' + 'CHAR{:03d}'.format(idx) + '.PNG', char)
    return (char for char in chars)

def decode_pipeline(filename):
    # TO DO: allow starting and stopping at any stage
    header, numChars, chars = read_nut_file(filename)
    save_binary_file(filename + '.AHDR', header)
    indices = range(numChars)
    chars = filter_chars(chars, indices)

    if (False):
        # only extract chars
        chars = save_char_files(chars)
        return

    chars = decode_frames(chars)

    if (False):
        # save separate char images
        chars = save_char_images(chars)
        return

    save_image(filename + '.PNG', font_image(numChars, chars))

def encode_pipeline(filename, codec, force=None):
    # TO DO: allow starting and stopping at any stage
    with open(filename, 'rb') as imFile:
        data = read_image(imFile)
    numChars, chars = from_font_image(data)

    if (False):
        # save separate char images
        chars = save_char_images(chars)
        return

    chars = encode_frames(chars, codec, force=force)

    if (False):
        # only extract chars
        chars = save_char_files(chars)
        return

    with open(filename[:-4] + '.AHDR', 'rb') as headerFile:
        header = headerFile.read()

    write_nut_file(header, numChars, chars, 'FONT-NEW.NUT')

if __name__=='__main__':
    if not len(sys.argv) > 1:
        print 'Usage: python split-font -[d|e] [args]'
        print '-d FILENAME.NUT'
        print '\tdecode FILENAME.NUT'
        print '-e FILENAME.NUT.PNG CODEC'
        print '\tencode FILENAME.NUT.PNG using codec number CODEC'
        exit()
    action = sys.argv[1]

    if action == '-d':
        if not len(sys.argv) > 2:
            print 'Usage: python split-font -d RESOURCE/SCUMMFNT.NUT'
            exit()
        filename = sys.argv[2]
        decode_pipeline(filename)
        exit()

    elif action == '-e':
        if not len(sys.argv) > 3:
            print 'Usage: python split-font -e RESOURCE/SCUMMFNT.NUT 21'
            exit()
        filename = sys.argv[2]
        codec = int(sys.argv[3])
        force = None
        if len(sys.argv) > 5 and sys.argv[4] == '-f':
            force = int(sys.argv[5])
        encode_pipeline(filename, codec, force=force)
        exit()
    
    print 'Usage: python split-font RESOURCE/SCUMMFNT.NUT'
    exit()



