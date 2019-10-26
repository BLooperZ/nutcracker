python -m nutcracker.decode_san nuts\fonts\ft\*.NUT --nut --target nuts\out\ft
python -m nutcracker.encode_nut nuts\out\ft\SCUMMFNT.NUT\chars.png --target nuts\test\ft\SCUMMFNT.NUT --ref nuts\fonts\ft\SCUMMFNT.NUT --codec 21
python -m nutcracker.encode_nut nuts\out\ft\SPECFNT.NUT\chars.png --target nuts\test\ft\SPECFNT.NUT --ref nuts\fonts\ft\SPECFNT.NUT --codec 21
python -m nutcracker.encode_nut nuts\out\ft\TECHFNT.NUT\chars.png --target nuts\test\ft\TECHFNT.NUT --ref nuts\fonts\ft\TECHFNT.NUT --codec 21
python -m nutcracker.encode_nut nuts\out\ft\TITLFNT.NUT\chars.png --target nuts\test\ft\TITLFNT.NUT --ref nuts\fonts\ft\TITLFNT.NUT --codec 21

python -m nutcracker.decode_san nuts\fonts\dig\*.NUT --nut --target nuts\out\dig
python -m nutcracker.encode_nut nuts\out\dig\FONT0.NUT\chars.png --target nuts\test\dig\FONT0.NUT --ref nuts\fonts\dig\FONT0.NUT --codec 21 --fake 44
python -m nutcracker.encode_nut nuts\out\dig\FONT1.NUT\chars.png --target nuts\test\dig\FONT1.NUT --ref nuts\fonts\dig\FONT1.NUT --codec 21 --fake 44
python -m nutcracker.encode_nut nuts\out\dig\FONT2.NUT\chars.png --target nuts\test\dig\FONT2.NUT --ref nuts\fonts\dig\FONT2.NUT --codec 21 --fake 44
python -m nutcracker.encode_nut nuts\out\dig\FONT3.NUT\chars.png --target nuts\test\dig\FONT3.NUT --ref nuts\fonts\dig\FONT3.NUT --codec 21 --fake 44

python -m nutcracker.decode_san nuts\fonts\comi\*.NUT --nut --target nuts\out\comi
python -m nutcracker.encode_nut nuts\out\comi\FONT0.NUT\chars.png --target nuts\test\comi\FONT0.NUT --ref nuts\fonts\comi\FONT0.NUT --codec 44
python -m nutcracker.encode_nut nuts\out\comi\FONT1.NUT\chars.png --target nuts\test\comi\FONT1.NUT --ref nuts\fonts\comi\FONT1.NUT --codec 44
python -m nutcracker.encode_nut nuts\out\comi\FONT2.NUT\chars.png --target nuts\test\comi\FONT2.NUT --ref nuts\fonts\comi\FONT2.NUT --codec 44
python -m nutcracker.encode_nut nuts\out\comi\FONT3.NUT\chars.png --target nuts\test\comi\FONT3.NUT --ref nuts\fonts\comi\FONT3.NUT --codec 21 --fake 44
python -m nutcracker.encode_nut nuts\out\comi\FONT4.NUT\chars.png --target nuts\test\comi\FONT4.NUT --ref nuts\fonts\comi\FONT4.NUT --codec 44
