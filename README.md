# NUTCracker
Tools to decode and re-encode fonts (.NUT) for Full Throttle and Curse of Monkey Island

## Usage
### Decoding
Decode given font file (NUT_FILE)
```
nutcracker.py -d NUT_FILE
```
This will result in NUT_FILE.PNG font image which can be edited using regular image editing software (e.g. GIMP)

### Encoding
Encode given font image (PNG_FILE) with given codec number (CODEC)
```
nutcracker.py -e PNG_FILE CODEC
```
This will convert font image file back to font file which can be used in game

Available codecs: 
* 21 (FT)
* 44 (COMI*)

*FONT3.NUT was actually encoded using codec 21 method. it can be forced using `-f CODEC`:
```
nutcracker.py -e FONT3.NUT.PNG 44 -f 21
```

see more examples in cmds.txt