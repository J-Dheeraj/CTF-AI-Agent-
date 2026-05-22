"""CTF tool suite – exports all LangChain tools for the agent."""

from .bash import bash_exec
from .python_exec import python_exec
from .web import web_request, web_fetch_page
from .file_ops import file_read, file_write, file_list
from .encoding import encode_decode
from .crypto import crypto_attack
from .binary import binary_analyze
from .search import search_ctf_writeups

ALL_TOOLS = [
    bash_exec,
    python_exec,
    web_request,
    web_fetch_page,
    file_read,
    file_write,
    file_list,
    encode_decode,
    crypto_attack,
    binary_analyze,
    search_ctf_writeups,
]

__all__ = ["ALL_TOOLS"]
