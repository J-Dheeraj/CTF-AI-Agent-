"""
tools/encoding.py – Encoding / decoding helper.

Covers the most common transformations seen in CTF challenges.
"""

from __future__ import annotations

import base64
import binascii
import json
import urllib.parse
from langchain_core.tools import tool


_OPERATIONS = {
    "b64_encode", "b64_decode",
    "b64url_encode", "b64url_decode",
    "hex_encode", "hex_decode",
    "url_encode", "url_decode",
    "rot13",
    "xor",          # requires key
    "binary_to_text",
    "text_to_binary",
    "caesar",       # requires shift (int)
    "morse_decode",
    "morse_encode",
}

_MORSE_MAP = {
    "A": ".-", "B": "-...", "C": "-.-.", "D": "-..", "E": ".",
    "F": "..-.", "G": "--.", "H": "....", "I": "..", "J": ".---",
    "K": "-.-", "L": ".-..", "M": "--", "N": "-.", "O": "---",
    "P": ".--.", "Q": "--.-", "R": ".-.", "S": "...", "T": "-",
    "U": "..-", "V": "...-", "W": ".--", "X": "-..-", "Y": "-.--",
    "Z": "--..", "0": "-----", "1": ".----", "2": "..---",
    "3": "...--", "4": "....-", "5": ".....", "6": "-....",
    "7": "--...", "8": "---..", "9": "----.",
}
_MORSE_REVERSE = {v: k for k, v in _MORSE_MAP.items()}


@tool
def encode_decode(operation: str, data: str, key: str = "") -> str:
    """
    Perform common encoding / decoding operations on a string.

    Supported operations:
      b64_encode, b64_decode, b64url_encode, b64url_decode,
      hex_encode, hex_decode, url_encode, url_decode,
      rot13, caesar (key=shift as int), xor (key=hex key e.g. "0xAB" or "AB"),
      binary_to_text, text_to_binary,
      morse_encode, morse_decode

    Args:
        operation: One of the supported operation names above.
        data: The input string to transform.
        key: Optional key/parameter (shift for caesar, hex byte for xor).

    Returns:
        The transformed string, or an error message.

    Examples:
        encode_decode("b64_decode", "aGVsbG8=")
        encode_decode("caesar", "Khoor Zruog", key="3")
        encode_decode("xor", "48656c6c6f", key="AB")
    """
    try:
        op = operation.strip().lower()

        if op == "b64_encode":
            return base64.b64encode(data.encode()).decode()

        if op == "b64_decode":
            # try with and without padding
            padded = data + "=" * (-len(data) % 4)
            return base64.b64decode(padded).decode("utf-8", errors="replace")

        if op == "b64url_encode":
            return base64.urlsafe_b64encode(data.encode()).decode()

        if op == "b64url_decode":
            padded = data + "=" * (-len(data) % 4)
            return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")

        if op == "hex_encode":
            return data.encode().hex()

        if op == "hex_decode":
            cleaned = data.replace(" ", "").replace("0x", "").replace("\\x", "")
            return bytes.fromhex(cleaned).decode("utf-8", errors="replace")

        if op == "url_encode":
            return urllib.parse.quote(data)

        if op == "url_decode":
            return urllib.parse.unquote(data)

        if op == "rot13":
            return data.translate(str.maketrans(
                "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
                "NOPQRSTUVWXYZABCDEFGHIJKLMnopqrstuvwxyzabcdefghijklm",
            ))

        if op == "caesar":
            shift = int(key) if key else 13
            result = []
            for ch in data:
                if ch.isalpha():
                    base = ord("A") if ch.isupper() else ord("a")
                    result.append(chr((ord(ch) - base - shift) % 26 + base))
                else:
                    result.append(ch)
            return "".join(result)

        if op == "xor":
            if not key:
                return "[ERROR] xor requires a key (hex byte, e.g. 'AB')"
            k = bytes.fromhex(key.replace("0x", ""))
            raw = bytes.fromhex(data.replace(" ", "")) if all(c in "0123456789abcdefABCDEF " for c in data) else data.encode()
            result_bytes = bytes(b ^ k[i % len(k)] for i, b in enumerate(raw))
            return result_bytes.decode("utf-8", errors="replace")

        if op == "binary_to_text":
            bits = data.replace(" ", "")
            chars = [chr(int(bits[i:i+8], 2)) for i in range(0, len(bits), 8)]
            return "".join(chars)

        if op == "text_to_binary":
            return " ".join(f"{ord(c):08b}" for c in data)

        if op == "morse_encode":
            return " ".join(_MORSE_MAP.get(c.upper(), "?") for c in data if c != " ")

        if op == "morse_decode":
            return "".join(_MORSE_REVERSE.get(token, "?") for token in data.split())

        return f"[ERROR] Unknown operation: {operation!r}. Supported: {sorted(_OPERATIONS)}"

    except Exception as exc:
        return f"[ENCODE/DECODE ERROR] {exc}"
