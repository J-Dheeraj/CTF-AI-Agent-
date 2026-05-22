# SKILL-crypto — Cryptographic Attacks

## Quick Category Check
| Clue | Likely cipher / attack |
|---|---|
| Large n, e, c integers | RSA |
| Hex string, same length as plaintext | XOR / stream cipher |
| Short key repeated | Vigenere / repeating-key XOR |
| Looks like English stats | Caesar / substitution / frequency |
| Dots and dashes | Morse code |
| `=` padding at end | Base64 |
| `gASV...` or `\x80\x04` | Python pickle |
| Block-structured ciphertext | AES (ECB/CBC/CTR) |

## RSA Attacks
```python
from Crypto.PublicKey import RSA
from Crypto.Util.number import long_to_bytes

# Small e (e=3) with small message → cube root
import gmpy2
m, exact = gmpy2.iroot(c, e)
flag = long_to_bytes(int(m))

# Common factor attack (shared p or q between two keys)
from math import gcd
p = gcd(n1, n2)   # if > 1, you have p
q1, q2 = n1 // p, n2 // p
phi = (p-1)*(q1-1)
d = pow(e, -1, phi)
flag = long_to_bytes(pow(c, d, n1))

# Wiener's attack (small d) — use owiener library
import owiener
d = owiener.attack(e, n)

# Fermat's factorization (p, q close together)
import gmpy2
a = gmpy2.isqrt(n) + 1
while True:
    b2 = a*a - n
    b, exact = gmpy2.isqrt_rem(b2)
    if exact == 0: break
    a += 1
p, q = int(a - b), int(a + b)

# Low public exponent broadcast (same m, same e, different n)
# Use Chinese Remainder Theorem then take e-th root
```

## XOR / Stream Cipher
```python
# Single-byte XOR brute force
def score(b): return sum(c in b' etaoinshrdlu' for c in b.lower())
key, best = None, -1
for k in range(256):
    pt = bytes(x ^ k for x in ct)
    s = score(pt)
    if s > best: best, key = s, k
flag = bytes(x ^ key for x in ct)

# Repeating-key XOR — find key length with Hamming distance / IC
# Then solve each position as single-byte XOR
from itertools import cycle
key = b"secret"
enc = bytes(p ^ k for p, k in zip(plaintext, cycle(key)))
```

## AES ECB
```python
# ECB oracle padding attack
# If you control prefix: align so block boundary falls after secret
# Submit identical blocks → identical ciphertext = ECB

from Crypto.Cipher import AES
# Byte-at-a-time ECB decryption (chosen-plaintext)
for byte in range(256):
    candidate = known_prefix + bytes([byte])
    if oracle(candidate) == target_block:
        flag += bytes([byte])
```

## AES CBC
```python
# CBC bit-flipping
# Flip bit in C[i] → flip corresponding bit in P[i+1]
ct = bytearray(ciphertext)
ct[block_pos + offset] ^= original_byte ^ target_byte

# Padding oracle — use padbuster or manual
# If server leaks padding error vs. other error: byte-by-byte decryption
```

## Hash Attacks
```python
# MD5 / SHA1 collision → use known collisionfiles
# Length extension attack (MD5, SHA1, SHA256 without secret suffix)
import hlextend
sha = hlextend.new('sha256')
new_msg, new_hash = sha.extend(append_data, known_msg, secret_len, known_hash)

# Hash cracking
# hashcat -m 0 hash.txt rockyou.txt        # MD5
# hashcat -m 100 hash.txt rockyou.txt      # SHA1
# john --wordlist=rockyou.txt hash.txt
```

## Classical Ciphers
```python
# Caesar / ROT brute force
for shift in range(26):
    print(shift, ''.join(chr((ord(c)-65+shift)%26+65) if c.isalpha() else c for c in ct.upper()))

# Frequency analysis — use quipqiup.com or manual
from collections import Counter
Counter(ct.replace(' ','')).most_common(5)

# Vigenere — Index of Coincidence to find key length, then Caesar per column
```

## Encoding Quick Reference
```python
import base64, binascii
base64.b64decode(s)
binascii.unhexlify(s)          # hex → bytes
s.encode().hex()               # bytes → hex
int(s, 2).to_bytes(...)        # binary string → bytes
```
