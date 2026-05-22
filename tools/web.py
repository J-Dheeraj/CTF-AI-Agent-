"""
tools/web.py – HTTP tools for web exploitation challenges.

Provides:
  - web_request  : Raw HTTP request with full control (method, headers, body)
  - web_fetch_page : Simple GET + return readable text (strips HTML tags)
"""

from __future__ import annotations

import re
import json as _json
import requests
from langchain_core.tools import tool

_TIMEOUT = 20
_SESSION = requests.Session()
_SESSION.max_redirects = 10


def _strip_html(html: str) -> str:
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.I)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


@tool
def web_request(
    url: str,
    method: str = "GET",
    headers: str = "{}",
    body: str = "",
    follow_redirects: bool = True,
) -> str:
    """
    Send an HTTP request and return the status code, response headers, and body.

    Use this for:
    - Web exploitation (SQLi, XSS, SSRF, IDOR, auth bypass)
    - Interacting with CTF web services
    - Cookie/session manipulation
    - Sending POST/PUT/PATCH/DELETE requests

    Args:
        url: Full URL including scheme (e.g. http://challenge.ctf:8080/login).
        method: HTTP verb – GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS.
        headers: JSON string of extra headers, e.g. '{"Cookie": "session=abc"}'.
        body: Request body string (use for POST data or JSON payloads).
        follow_redirects: Whether to follow HTTP redirects (default True).

    Returns:
        String with status line, headers, and response body (truncated to 6 000 chars).
    """
    try:
        parsed_headers: dict = _json.loads(headers) if headers.strip() else {}
    except _json.JSONDecodeError as exc:
        return f"[ERROR] headers must be valid JSON: {exc}"

    try:
        resp = _SESSION.request(
            method=method.upper(),
            url=url,
            headers=parsed_headers,
            data=body.encode() if body else None,
            allow_redirects=follow_redirects,
            timeout=_TIMEOUT,
            verify=False,  # CTF certs are often self-signed
        )
    except Exception as exc:
        return f"[REQUEST ERROR] {exc}"

    resp_headers = "\n".join(f"  {k}: {v}" for k, v in resp.headers.items())
    body_text = resp.text[:6000]
    return (
        f"Status: {resp.status_code} {resp.reason}\n"
        f"Headers:\n{resp_headers}\n\n"
        f"Body:\n{body_text}"
    )


@tool
def web_fetch_page(url: str) -> str:
    """
    Fetch a web page and return its readable text content (HTML stripped).

    Use this when you just want to read a page's visible text — e.g. reading
    a challenge description page, a robots.txt, or source comments.

    Args:
        url: URL to GET.

    Returns:
        Visible text content of the page, up to 6 000 chars.
    """
    try:
        resp = _SESSION.get(url, timeout=_TIMEOUT, verify=False)
        text = _strip_html(resp.text)
        return text[:6000] or "(empty page)"
    except Exception as exc:
        return f"[FETCH ERROR] {exc}"
