# SKILL-misc — Miscellaneous / Steganography / Jail Escapes

## Steganography Checklist
```bash
# Image
zsteg image.png                    # LSB, zlib, various channels
steghide info image.jpg            # check for embedded data
steghide extract -sf image.jpg -p ""
stegsolve image.png                # Java GUI — bit planes, colour channels
convert image.png -channel R -separate red.png   # split channels

# Audio
audacity audio.wav                 # spectrogram: View → Show Spectrum
sox audio.wav -t spectrogram -o spec.png
# Look for: reversed audio, speed changes, DTMF tones, LSB

# Text / whitespace
cat -A file.txt | grep ' $'        # trailing spaces
python3 -c "
import re
with open('file.txt') as f:
    for line in f:
        bits = ''.join('1' if c==' ' else '0' for c in re.findall('[ \t]', line))
        if bits: print(chr(int(bits,2)), end='')
"
# Snow whitespace stego: stegsnow -C file.txt
# Zero-width characters: check Unicode U+200B, U+200C, U+200D
```

## QR / Barcode
```bash
zbarimg image.png                  # decode QR / barcode
# Online: zxing.org/w/decode.jspx
# Damaged QR: use QRazyBox (online) for partial recovery
```

## Encoding Identification
```
Base64:   A-Za-z0-9+/=  (length multiple of 4)
Base32:   A-Z2-7=
Base58:   Bitcoin-style (no 0, O, I, l)
Hex:      0-9A-F, always even length
Binary:   only 0 and 1, groups of 8
Morse:    dots, dashes, spaces
Bacon:    A/B pairs encoding letters
Braille:  ⠿ unicode dots
ROT13:    Caesar with 13
Atbash:   A↔Z, B↔Y reverse alphabet
```

## Python / Bash Jail Escape
```python
# Restricted shell / Python jail

# Bypass import restrictions
__import__('os').system('id')
().__class__.__bases__[0].__subclasses__()   # find useful classes

# eval/exec tricks
exec(compile('import os; os.system("sh")', '<string>', 'exec'))

# String construction without quotes
chr(111)+chr(115)   # 'os'

# Bash restricted shell
# echo $PATH — often /usr/local/sbin:/usr/local/bin:/sbin:/bin
ls /usr/local/bin   # find allowed binaries
# python3 -c 'import os; os.system("/bin/bash")'
# If / blocked: use env variable PATH manipulation
```

## Number Theory / Math Challenges
```python
from sympy import factorint, isprime, mod_inverse, discrete_log

# Discrete log (small group)
discrete_log(p, g_x, g)   # find x: g^x ≡ g_x (mod p)

# Chinese Remainder Theorem
from sympy.ntheory.modular import crt
r, m = crt([n1, n2, n3], [a1, a2, a3])   # solve x ≡ ai (mod ni)

# Integer factorization
factorint(n)   # sympy
# Online: factordb.com
```

## Game / Scripting Challenges
```python
# If the server asks a series of timed questions, automate with pwntools
from pwn import *
p = remote('host', port)

while True:
    line = p.recvline().decode()
    # parse question, compute answer
    p.sendline(str(answer).encode())
```

## Audio / DTMF
```python
# Decode DTMF tones from wav
import numpy as np
from scipy.io import wavfile
from scipy.signal import spectrogram
# Map frequency peaks to keypad digits
```

## Common CTF Misc Patterns
- Flag hidden in whitespace: trailing spaces encode binary
- Flag in QR code embedded in image: extract with binwalk then zbarimg
- Flag reversible: `s[::-1]` or `rev` command
- Flag is ROT13 of something visible: `echo text | tr A-Za-z N-ZA-Mn-za-m`
- Flag XOR'd with repeating key: try key = "KEY", challenge name, author name
- Game you have to win: automate with pwntools or a script
