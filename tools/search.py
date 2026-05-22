"""
tools/search.py – CTF writeup & knowledge search.

Searches CTFtime, GitHub, and Google for existing writeups and techniques.
"""

from __future__ import annotations

import urllib.parse
import requests
from langchain_core.tools import tool

_TIMEOUT = 15


@tool
def search_ctf_writeups(query: str) -> str:
    """
    Search for CTF writeups and relevant techniques online.

    Use this when you are stuck, want to understand a technique, or want to
    see how similar challenges have been solved before.

    Searches:
    - CTFtime.org writeups
    - GitHub repositories
    - Google (via DuckDuckGo Lite)

    Args:
        query: Search terms (e.g. "RSA low exponent CTF writeup",
               "heap overflow glibc 2.35 tcache", "web SSRF AWS metadata CTF").

    Returns:
        List of relevant results with titles and URLs.
    """
    results: list[str] = []

    # ── DuckDuckGo Lite (no API key needed) ───────────────────────────────────
    try:
        encoded = urllib.parse.quote_plus(f"{query} CTF writeup site:ctftime.org OR site:github.com")
        resp = requests.get(
            "https://html.duckduckgo.com/html/",
            params={"q": f"{query} CTF writeup"},
            headers={"User-Agent": "Mozilla/5.0 (CTF-Agent/1.0)"},
            timeout=_TIMEOUT,
        )
        import re
        # Extract result snippets from DuckDuckGo HTML
        titles = re.findall(r'class="result__title"[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', resp.text, re.DOTALL)
        snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</div>', resp.text, re.DOTALL)
        clean = lambda s: re.sub(r"<[^>]+>", "", s).strip()

        for i, ((url, title), snip) in enumerate(zip(titles[:8], snippets[:8])):
            results.append(f"[{i+1}] {clean(title)}\n    URL: {url}\n    {clean(snip)[:200]}")
    except Exception as exc:
        results.append(f"[DuckDuckGo error] {exc}")

    # ── CTFtime search fallback ───────────────────────────────────────────────
    try:
        ctftime_url = f"https://ctftime.org/writeups?search={urllib.parse.quote(query)}"
        results.append(f"\nDirect CTFtime search: {ctftime_url}")
    except Exception:
        pass

    return "\n\n".join(results) if results else "No results found."
