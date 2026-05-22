"""
config.py – Centralised settings for the CTF AI Agent.

Values are resolved in this order (highest priority first):
  1. Environment variables (.env file via python-dotenv)
  2. Active profile's config.yaml  (loaded by agent.py at runtime)
  3. Defaults below
"""

from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Backend selection ─────────────────────────────────────────────────────────

HERMES_BACKEND: str = os.getenv("HERMES_BACKEND", "ollama").lower()

# Ollama
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL: str    = os.getenv("OLLAMA_MODEL", "nous-hermes3")

# OpenRouter
OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL: str   = os.getenv("OPENROUTER_MODEL", "nousresearch/hermes-3-llama-3.1-405b")
OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

# Together AI
TOGETHER_API_KEY: str = os.getenv("TOGETHER_API_KEY", "")
TOGETHER_MODEL: str   = os.getenv("TOGETHER_MODEL", "NousResearch/Hermes-3-Llama-3.1-405B-Turbo")
TOGETHER_BASE_URL: str = "https://api.together.xyz/v1"

# Claude (Anthropic) — best CTF reasoning quality (paid)
ANTHROPIC_API_KEY: str  = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL: str    = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
ANTHROPIC_BASE_URL: str = "https://api.anthropic.com/v1"

# Groq — free tier but only 6k TPM (too tight for full skill prompts)
GROQ_API_KEY: str  = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL: str    = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"

# Google Gemini — FREE, 1M tokens/day, excellent tool calling (aistudio.google.com)
GEMINI_API_KEY: str  = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL: str    = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
GEMINI_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta/openai/"

# ── Agent behaviour (defaults; overridden per-profile in agent.py) ────────────

MAX_ITERATIONS: int     = int(os.getenv("MAX_ITERATIONS", "30"))
AGENT_TEMPERATURE: float = float(os.getenv("AGENT_TEMPERATURE", "0.1"))

# ── Safety ────────────────────────────────────────────────────────────────────

_raw_deny = os.getenv("BASH_DENY_PATTERNS", "rm -rf /,mkfs,:(){:|:&};:")
BASH_DENY_PATTERNS: list[str] = [p.strip() for p in _raw_deny.split(",") if p.strip()]

# ── Paths ─────────────────────────────────────────────────────────────────────

PROJECT_ROOT:  Path = Path(__file__).parent
WORKSPACE_DIR: Path = PROJECT_ROOT / "workspace"
WORKSPACE_DIR.mkdir(exist_ok=True)
