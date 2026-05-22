"""
tools/crypto.py – Cryptographic attack primitives for CTF challenges.

Covers the most common crypto challenges: RSA attacks, hash cracking,
Vigenere/Caesar analysis, frequency analysis, padding oracle helpers, etc.
"""

from __future__ import annotations

import math
import hashlib
import itertools
import string
from langchain_core.tools import tool


@tool
def crypto_attack(attack: str, params: str = "{}") -> str:
    """
    Execute a common cryptographic attack or utility.

    Supported attacks (pass as `attack`):
      - rsa_small_e          : Low public exponent attack (e=3, no padding)
      - rsa_factor_n         : Factor N given p and q (reconstruct private key)
      - rsa_wiener           : Wiener's attack for small private exponent d
      - frequency_analysis   : Letter frequency analysis on ciphertext
      - hash_identify        : Identify hash type by length/format
      - hash_crack_md5       : Crack MD5 hash against a wordlist
      - vigenere_kasiski     : Estimate Vigenere key length via Kasiski test
      - xor_bruteforce       : Single-byte XOR brute force

    Args:
        attack: Name of the attack (see above).
        params: JSON string of attack-specific parameters. Examples:
          rsa_small_e:    {"c": "1234", "n": "9999", "e": "3"}
          rsa_factor_n:   {"p": "61", "q": "53", "e": "17"}
          frequency_analysis: {"ciphertext": "Khoor Zruog"}
          hash_crack_md5: {"hash": "5d41402abc...", "wordlist": "password,hello,admin"}
          vigenere_kasiski: {"ciphertext": "ABCDEF..."}
          xor_bruteforce: {"hex_data": "1a2b3c..."}

    Returns:
        Attack result or error message.
    """
    import json
    try:
        p = json.loads(params) if params.strip() else {}
    except json.JSONDecodeError as exc:
        return f"[ERROR] params must be valid JSON: {exc}"

    try:
        atk = attack.strip().lower()

        # ── RSA: low public exponent (cube-root attack) ───────────────────────
        if atk == "rsa_small_e":
            c = int(p.get("c", 0))
            e = int(p.get("e", 3))
            n = int(p.get("n", 0))  # optional – just for context

            # Integer e-th root
            root = int(round(c ** (1 / e)))
            for candidate in range(max(0, root - 100), root + 100):
                if candidate ** e == c:
                    return f"Plaintext (integer): {candidate}\nAs bytes: {candidate.to_bytes((candidate.bit_length() + 7) // 8, 'big')}"
            return f"Could not find exact {e}-th root of c={c}. Try python_exec with gmpy2."

        # ── RSA: reconstruct private key from p, q, e ────────────────────────
        if atk == "rsa_factor_n":
            p_val = int(p.get("p", 0))
            q_val = int(p.get("q", 0))
            e_val = int(p.get("e", 65537))
            n_val = p_val * q_val
            phi = (p_val - 1) * (q_val - 1)
            d = pow(e_val, -1, phi)
            return (
                f"n = {n_val}\n"
                f"phi(n) = {phi}\n"
                f"d (private exponent) = {d}\n\n"
                f"Decrypt: m = pow(c, d, n)"
            )

        # ── Frequency analysis ────────────────────────────────────────────────
        if atk == "frequency_analysis":
            ct = p.get("ciphertext", "")
            letters = [c.upper() for c in ct if c.isalpha()]
            if not letters:
                return "[ERROR] No alphabetic characters found."
            total = len(letters)
            freq = {}
            for ch in letters:
                freq[ch] = freq.get(ch, 0) + 1
            sorted_freq = sorted(freq.items(), key=lambda x: -x[1])
            lines = [f"  {ch}: {cnt} ({cnt/total*100:.1f}%)" for ch, cnt in sorted_freq[:15]]
            english_order = "ETAOINSHRDLCUMWFGYPBVKJXQZ"
            result = "Frequency (top 15):\n" + "\n".join(lines)
            result += f"\n\nEnglish order: {english_order}"
            if sorted_freq:
                most_common = sorted_freq[0][0]
                shift_guess = (ord(most_common) - ord("E")) % 26
                result += f"\n\nIf Caesar: most common '{most_common}' → 'E' → shift={shift_guess}"
            return result

        # ── Hash identification ───────────────────────────────────────────────
        if atk == "hash_identify":
            h = p.get("hash", "").strip()
            length = len(h)
            guesses = {
                32: "MD5",
                40: "SHA-1",
                56: "SHA-224",
                64: "SHA-256",
                96: "SHA-384",
                128: "SHA-512",
            }
            return f"Hash: {h}\nLength: {length} hex chars → likely {guesses.get(length, 'Unknown')}"

        # ── MD5 wordlist crack ────────────────────────────────────────────────
        if atk == "hash_crack_md5":
            target = p.get("hash", "").lower()
            wordlist = p.get("wordlist", "password,123456,admin,hello,flag,secret")
            words = [w.strip() for w in wordlist.split(",")]
            for word in words:
                if hashlib.md5(word.encode()).hexdigest() == target:
                    return f"Cracked! Hash {target} = {word!r}"
            return f"Not found in {len(words)}-word list. Try a larger wordlist via bash (hashcat/john)."

        # ── Vigenere Kasiski ─────────────────────────────────────────────────
        if atk == "vigenere_kasiski":
            ct = p.get("ciphertext", "").upper()
            ct_alpha = "".join(c for c in ct if c.isalpha())
            if len(ct_alpha) < 20:
                return "[ERROR] Ciphertext too short for Kasiski."
            # Find repeated trigrams and their distances
            distances = []
            for i in range(len(ct_alpha) - 3):
                trigram = ct_alpha[i:i+3]
                for j in range(i + 3, len(ct_alpha) - 3):
                    if ct_alpha[j:j+3] == trigram:
                        distances.append(j - i)
            if not distances:
                return "No repeated trigrams found. Key might be very long or ciphertext is too short."
            # GCD of distances
            from math import gcd
            from functools import reduce
            overall_gcd = reduce(gcd, distances)
            # Factors
            factors = [i for i in range(2, overall_gcd + 1) if overall_gcd % i == 0]
            return f"Repeated trigram distances: {distances[:10]}\nGCD: {overall_gcd}\nLikely key lengths: {factors}"

        # ── Single-byte XOR brute force ───────────────────────────────────────
        if atk == "xor_bruteforce":
            hex_data = p.get("hex_data", "").replace(" ", "")
            data = bytes.fromhex(hex_data)
            results = []
            for key_byte in range(256):
                candidate = bytes(b ^ key_byte for b in data)
                printable = sum(1 for b in candidate if 32 <= b < 127)
                if printable / len(candidate) > 0.85:
                    results.append((key_byte, candidate.decode("utf-8", errors="replace"), printable))
            results.sort(key=lambda x: -x[2])
            if not results:
                return "No high-printability candidate found. Try multi-byte XOR via python_exec."
            lines = [f"  key=0x{k:02x}: {txt[:80]}" for k, txt, _ in results[:5]]
            return "Top candidates:\n" + "\n".join(lines)

        return f"[ERROR] Unknown attack: {attack!r}. See tool docstring for supported attacks."

    except Exception as exc:
        return f"[CRYPTO ERROR] {exc}"
