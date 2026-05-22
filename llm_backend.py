"""llm_backend.py – Factory that returns the configured LLM client."""
from __future__ import annotations
from langchain_openai import ChatOpenAI
from config import (
    HERMES_BACKEND, AGENT_TEMPERATURE,
    OLLAMA_BASE_URL, OLLAMA_MODEL,
    OPENROUTER_API_KEY, OPENROUTER_MODEL, OPENROUTER_BASE_URL,
    TOGETHER_API_KEY, TOGETHER_MODEL, TOGETHER_BASE_URL,
    ANTHROPIC_API_KEY, ANTHROPIC_MODEL, ANTHROPIC_BASE_URL,
    GROQ_API_KEY, GROQ_MODEL, GROQ_BASE_URL,
    GEMINI_API_KEY, GEMINI_MODEL, GEMINI_BASE_URL,
)


def get_hermes_llm():
    if HERMES_BACKEND == "ollama":
        return ChatOpenAI(
            model=OLLAMA_MODEL,
            base_url=f"{OLLAMA_BASE_URL}/v1",
            api_key="ollama",
            temperature=AGENT_TEMPERATURE,
        )

    if HERMES_BACKEND == "openrouter":
        if not OPENROUTER_API_KEY:
            raise ValueError("HERMES_BACKEND=openrouter but OPENROUTER_API_KEY is not set.")
        return ChatOpenAI(
            model=OPENROUTER_MODEL,
            base_url=OPENROUTER_BASE_URL,
            api_key=OPENROUTER_API_KEY,
            temperature=AGENT_TEMPERATURE,
            default_headers={"HTTP-Referer": "https://ctf-agent", "X-Title": "CTF-Agent"},
        )

    if HERMES_BACKEND == "together":
        if not TOGETHER_API_KEY:
            raise ValueError("HERMES_BACKEND=together but TOGETHER_API_KEY is not set.")
        return ChatOpenAI(
            model=TOGETHER_MODEL,
            base_url=TOGETHER_BASE_URL,
            api_key=TOGETHER_API_KEY,
            temperature=AGENT_TEMPERATURE,
        )

    if HERMES_BACKEND == "claude":
        if not ANTHROPIC_API_KEY:
            raise ValueError("HERMES_BACKEND=claude but ANTHROPIC_API_KEY is not set.")
        # Anthropic's OpenAI-compatible endpoint works with ChatOpenAI
        return ChatOpenAI(
            model=ANTHROPIC_MODEL,
            base_url=ANTHROPIC_BASE_URL,
            api_key=ANTHROPIC_API_KEY,
            temperature=AGENT_TEMPERATURE,
            default_headers={"anthropic-version": "2023-06-01"},
        )

    if HERMES_BACKEND == "groq":
        if not GROQ_API_KEY:
            raise ValueError("HERMES_BACKEND=groq but GROQ_API_KEY is not set. Get a free key at console.groq.com")
        return ChatOpenAI(
            model=GROQ_MODEL,
            base_url=GROQ_BASE_URL,
            api_key=GROQ_API_KEY,
            temperature=AGENT_TEMPERATURE,
        )

    if HERMES_BACKEND == "gemini":
        if not GEMINI_API_KEY:
            raise ValueError("HERMES_BACKEND=gemini but GEMINI_API_KEY is not set. Get a free key at aistudio.google.com")
        return ChatOpenAI(
            model=GEMINI_MODEL,
            base_url=GEMINI_BASE_URL,
            api_key=GEMINI_API_KEY,
            temperature=AGENT_TEMPERATURE,
        )

    raise ValueError(f"Unknown HERMES_BACKEND: {HERMES_BACKEND!r}. Valid: ollama, openrouter, together, claude, groq, gemini")
