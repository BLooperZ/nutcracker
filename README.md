# NUTCracker
Tools for editing resources in SCUMM games.

## Features:
* Extract and Edit fonts for v5-v7 + HE
* Extract and Edit NUT fonts - v7-v8
* Extract and Replace SMUSH video frames
* Compress SMUSH videos (like scummvm-tools)
* Extract and Rebuild game resources - v5-v8 + HE
* Extract and Inject text strings - v5-v8 + HE
* Extract and Replace background and objects images - v5-v8 + HE (option to extract EGA backgrounds)
* Decompile V5 Scripts to Windex-like (SCUMM debugger from https://quickandeasysoftware.net/monkey-island-2-talkie-prototype) syntax

## Resources

### Extract and rebuild

Supported games: V5-V8, HE

Extract game resources to patch files using:
```
nutcracker sputm extract PATH/TO/GAME.000
```
*Replace `PATH/TO/GAME.000` to actual game index file (Usually ends with `.000`, `.LA0` or `.HE0`)

This also creates XML-like file `rpdump.xml` to show which files were extracted.

Rebuild game resources from patches (using original resource as reference):
```
nutcracker sputm build --ref PATH/TO/GAME.000 GAME
```

## Fonts

### SPUTM Font (`CHAR` chunks)

Supported games: V5-V7, HE

Extract the fonts using:
```
nutcracker sputm fonts_extract PATH/TO/GAME.000
```

*Replace `PATH/TO/GAME.000` to actual game index file (Usually ends with `.000`, `.LA0` or `.HE0`)

fonts will be extracted as PNG images to directory `GAME/chars` relative to workdir.

*Replace `GAME` with name of the game (e.g. `ATLANTIS` if game index file is `ATLANTIS.000`)

Modify the font images with any image editor.

Create patch files for the modified font:
```
nutcracker sputm fonts_inject --ref PATH/TO/GAME.000 GAME
```
Rebuild game resources
```
nutcracker sputm build --ref PATH/TO/GAME.000 GAME
```

### NUT Fonts

Supported games: V7-V8

#### Decoding
Decode all NUT files in given directory DATADIR
```
nutcracker smush decode DATADIR/*.NUT --nut --target OUTDIR
```
Creates a font image file named chars.png in OUTDIR which can be edited using regular image editing software (e.g. GIMP)

#### Encoding
Encode given font image (PNG_FILE) with given codec number (CODEC) using REF_NUT_FILE as reference
```
python -m nutcracker.smush.encode PNG_FILE --target NEW_NUT_FILE --ref REF_NUT_FILE --codec CODEC [--fake CODEC]
```
This will convert font image file back to font file (NEW_NUT_FILE) which can be used in game.

Available codecs: 
* 21 (FT + The Dig*)
* 44 (COMI*)

*FONT3.NUT and the fonts in The Dig was actually encoded using codec 21 method but marked as 44.
It can be achieved using `--codec 21 --fake 44`.
see examples in [test.bat](test.bat)

## SMUSH Videos

### Decode and Re-encode

Supported games: V7-V8

Decode frames using
```
nutcracker smush decode DATADIR/*.SAN --target OUTDIR
```
Frames will be extracted as PNG files to `OUTDIR/VIDEO.SAN`
where `VIDEO.SAN` matches the filename of the video.

Re-encode the video using:
```
python -m nutcracker.smush.encode_san_seq DATADIR/VIDEO.SAN
``` 
where DATADIR/VIDEO.SAN is path to original SMUSH video file

The new video will be created as `NEW_VIDEO2.SAN` in workdir

*To reduce result file size, it is recommended to only re-encode modified frames, this can be done by removing unaltered frames from `OUTDIR/VIDEO.SAN`

### Compress

Supported games: V7-V8

Compress video frames using zlib compression, as in scummvm-tools
```
nutcracker smush compress DATADIR/*.SAN
```

## Text

### Extract and Inject script text

Supported games: V5-V8, HE

Extract all texts from game to text file using:
```
nutcracker sputm strings_extract --textfile strings.txt PATH/TO/GAME.000
```
*Replace `PATH/TO/GAME.000` to actual game index file (Usually ends with `.000`, `.LA0` or `.HE0`)

Edit the text file using regular text editor.

Inject the modified text in game resources using:
```
nutcracker sputm strings_inject  --textfile strings.txt PATH/TO/GAME.000
```

### Decompile game script

Supported games: V5

Decompile game scripts to script file with Windex-like syntax:

```
python -m nutcracker.sputm.windex_v5 PATH/TO/GAME.000
```
*Replace `PATH/TO/GAME.000` to actual game index file (Usually ends with `.000`, `.LA0` or `.HE0`)


## Graphics

### Room background and object images

Supported games: V5-V8, HE

Extract room background and object images using:

```
nutcracker sputm room decode [--ega] PATH/TO/GAME.000
```
*Replace `PATH/TO/GAME.000` to actual game index file (Usually ends with `.000`, `.LA0` or `.HE0`)

*Use the `--ega` if you wish to simulate EGA graphics on games with EGA backward compatibility mode, don't use it if you wish to modify the graphics for injecting modified graphics later

Room backgrounds and Object images will be extracted as PNG images in `GAME/backgrounds` and `GAME/objects` respectively, where `GAME` is replaced with the name of the game.

Modify the image files, it's recommended to use image editor without palette optimization, such as GraphicsGale.

Create patch files for the modified images using:
```
nutcracker sputm room encode --ref PATH/TO/GAME.000 GAME
```
Rebuild game resources
```
nutcracker sputm build --ref PATH/TO/GAME.000 GAME
```
