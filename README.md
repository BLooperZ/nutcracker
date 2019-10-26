# NUTCracker
Tools for editing resources in SCUMM games.

## NUT File Usage
### Decoding
Decode all NUT files in given directory DATADIR
```
python -m nutcracker.decode_san DATADIR/*.NUT --nut --target OUTDIR
```
Creates a font image file named chars.png in OUTDIR which can be edited using regular image editing software (e.g. GIMP)

### Encoding
Encode given font image (PNG_FILE) with given codec number (CODEC) using REF_NUT_FILE as reference
```
python -m nutcracker.encode_nut PNG_FILE --target NEW_NUT_FILE --ref REF_NUT_FILE --codec CODEC [--fake CODEC]
```
This will convert font image file back to font file (NEW_NUT_FILE) which can be used in game.

Available codecs: 
* 21 (FT + The Dig*)
* 44 (COMI*)

*FONT3.NUT and the fonts in The Dig was actually encoded using codec 21 method but marked as 44.
It can be achieved using `--codec 21 --fake 44`.
see examples in [test.bat](test.bat)
