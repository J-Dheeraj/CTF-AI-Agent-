"""
agent.py – CTF AI Agent built on LangGraph.

Architecture:
  ┌─────────────┐     tool calls      ┌──────────────┐
  │  Hermes LLM │ ──────────────────▶ │  Tool Node   │
  │  (ReAct)    │ ◀──────────────────  │  (all tools) │
  └─────────────┘   tool results      └──────────────┘
        │
        ▼  "flag found" / max iterations / "__end__"
      [END]

System prompt = SOUL.md (profile identity) + selected SKILL-*.md files.
"""

from __future__ import annotations

import re
import datetime
from pathlib import Path
from typing import Annotated, TypedDict, Sequence

import yaml
from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    SystemMessage,
    AIMessage,
    ToolMessage,
)
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from config import MAX_ITERATIONS, PROJECT_ROOT, WORKSPACE_DIR
from llm_backend import get_hermes_llm
from tools import ALL_TOOLS

# ── Profile loading ───────────────────────────────────────────────────────────

PROFILES_DIR = PROJECT_ROOT / "profiles"
SKILLS_DIR   = PROJECT_ROOT / "skills"
FEEDBACK_LOG = PROJECT_ROOT / "feedback-log.md"


def _load_profile(profile_name: str) -> dict:
    """Load config.yaml for the given profile. Falls back to ctf-solo."""
    profile_dir = PROFILES_DIR / profile_name
    if not profile_dir.exists():
        raise FileNotFoundError(
            f"Profile '{profile_name}' not found in {PROFILES_DIR}. "
            f"Available: {[p.name for p in PROFILES_DIR.iterdir() if p.is_dir()]}"
        )
    config_path = profile_dir / "config.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


def _read_soul(profile_name: str) -> str:
    soul_path = PROFILES_DIR / profile_name / "SOUL.md"
    return soul_path.read_text(encoding="utf-8") if soul_path.exists() else ""


def _load_skills(profile_config: dict) -> str:
    """Read and concatenate skill files listed in profile config."""
    skill_names = profile_config.get("skills", {}).get("load", [])
    parts: list[str] = []
    for name in skill_names:
        skill_path = SKILLS_DIR / f"{name}.md"
        if skill_path.exists():
            parts.append(skill_path.read_text(encoding="utf-8"))
    return "\n\n---\n\n".join(parts)


def build_system_prompt(profile_name: str) -> str:
    config = _load_profile(profile_name)
    soul   = _read_soul(profile_name)
    skills = _load_skills(config)

    return f"{soul}\n\n---\n\n# Skill Reference\n\n{skills}"


# ── GEPA: auto-skill capture ──────────────────────────────────────────────────

def _append_feedback(entry: str) -> None:
    ts = datetime.datetime.now().isoformat(timespec="seconds")
    with open(FEEDBACK_LOG, "a", encoding="utf-8") as f:
        f.write(f"\n[{ts}] {entry}\n---\n")


def _maybe_capture_auto_skill(
    profile_name: str,
    profile_config: dict,
    challenge_desc: str,
    iterations: int,
    messages: Sequence[BaseMessage],
) -> None:
    threshold = profile_config.get("skills", {}).get(
        "evolution", {}
    ).get("trigger_tool_calls", 5)
    if not profile_config.get("skills", {}).get("evolution", {}).get("auto_capture"):
        return
    if iterations < threshold:
        return

    # Ask the LLM to summarise the technique pattern (non-blocking best-effort)
    try:
        from langchain_openai import ChatOpenAI
        llm = get_hermes_llm()
        conversation = "\n".join(
            f"{type(m).__name__}: {str(m.content)[:300]}" for m in messages[-10:]
        )
        prompt = (
            "In 3–5 bullet points, summarise the CTF technique patterns used in "
            "this session. Focus on WHAT technique worked and WHY, not the specific "
            "flag or challenge details. Output only the bullet points.\n\n"
            f"Challenge summary: {challenge_desc[:200]}\n\nSession tail:\n{conversation}"
        )
        response = llm.invoke([HumanMessage(content=prompt)])
        category = _infer_category(challenge_desc)
        date_str = datetime.date.today().isoformat()
        slug = re.sub(r"[^a-z0-9]+", "-", challenge_desc[:30].lower()).strip("-")
        auto_path = SKILLS_DIR / "auto" / f"{category}-{date_str}-{slug}.md"
        auto_path.write_text(
            f"# Auto-captured skill: {category} — {date_str}\n\n"
            f"Source challenge: {challenge_desc[:80]}\n\n"
            f"{response.content}\n\n"
            "_Review and merge into the relevant SKILL-*.md before next session._\n",
            encoding="utf-8",
        )
    except Exception:
        pass  # best-effort; never block the main flow


def _infer_category(text: str) -> str:
    t = text.lower()
    if any(w in t for w in ["sql", "xss", "web", "http", "cookie", "jwt", "ssrf", "lfi"]):
        return "web"
    if any(w in t for w in ["rsa", "aes", "cipher", "crypto", "encrypt", "hash", "xor"]):
        return "crypto"
    if any(w in t for w in ["buffer", "overflow", "pwn", "elf", "binary", "rop", "heap"]):
        return "binary"
    if any(w in t for w in ["pcap", "memory", "disk", "image", "steg", "forensic"]):
        return "forensics"
    if any(w in t for w in ["osint", "username", "domain", "whois", "social"]):
        return "osint"
    return "misc"


# ── Agent state ───────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    iterations: int
    flag: str | None


# ── Flag detection ────────────────────────────────────────────────────────────

_FLAG_RE = re.compile(
    r"(?:"
    r"FLAG FOUND:\s*(?P<explicit>[^\s\n]+)"
    r"|(?P<pattern>(?:[A-Z]{2,10}CTF|picoCTF|flag|FLAG|CTF)\{[^}]{3,100}\})"
    r")",
    re.IGNORECASE,
)

def extract_flag(text: str) -> str | None:
    m = _FLAG_RE.search(text)
    if m:
        return m.group("explicit") or m.group("pattern")
    return None


# ── Feedback command handling ─────────────────────────────────────────────────

_FEEDBACK_RE = re.compile(
    r"/feedback\s+(?P<wrong>.+?)\s*→\s*(?P<correct>.+?)(?:\s*\|\s*category:\s*(?P<cat>\w+))?$",
    re.IGNORECASE | re.MULTILINE,
)

def handle_feedback_commands(text: str) -> None:
    for m in _FEEDBACK_RE.finditer(text):
        entry = (
            f"category={m.group('cat') or 'unknown'}\n"
            f"  wrong:   {m.group('wrong').strip()}\n"
            f"  correct: {m.group('correct').strip()}"
        )
        _append_feedback(entry)


# ── Graph nodes ───────────────────────────────────────────────────────────────

def should_continue(state: AgentState) -> str:
    if state.get("flag"):
        return END
    if state.get("iterations", 0) >= MAX_ITERATIONS:
        return END
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tools"
    return END


def after_tools(state: AgentState) -> AgentState:
    flag = state.get("flag")
    if not flag:
        for msg in reversed(state["messages"]):
            if isinstance(msg, ToolMessage):
                flag = extract_flag(str(msg.content))
                if flag:
                    break
    return {"messages": [], "iterations": state.get("iterations", 0), "flag": flag}


# ── Graph assembly ────────────────────────────────────────────────────────────

def _make_call_llm(llm):
    """Return a call_llm node bound to a specific LLM instance."""
    def call_llm(state: AgentState) -> AgentState:
        llm_with_tools = llm.bind_tools(ALL_TOOLS)
        response: AIMessage = llm_with_tools.invoke(state["messages"])
        flag = None
        if isinstance(response.content, str):
            flag = extract_flag(response.content)
            handle_feedback_commands(response.content)
        return {
            "messages": [response],
            "iterations": state.get("iterations", 0) + 1,
            "flag": flag or state.get("flag"),
        }
    return call_llm


def build_ctf_agent(api_key: str | None = None):
    if api_key:
        from langchain_openai import ChatOpenAI
        import config as cfg
        llm = ChatOpenAI(
            model=cfg.ANTHROPIC_MODEL,
            base_url=cfg.ANTHROPIC_BASE_URL,
            api_key=api_key,
            temperature=cfg.AGENT_TEMPERATURE,
            default_headers={"anthropic-version": "2023-06-01"},
        )
    else:
        llm = get_hermes_llm()

    tool_node = ToolNode(ALL_TOOLS)
    graph = StateGraph(AgentState)

    graph.add_node("llm", _make_call_llm(llm))
    graph.add_node("tools", tool_node)
    graph.add_node("after_tools", after_tools)

    graph.set_entry_point("llm")
    graph.add_conditional_edges("llm", should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "after_tools")
    graph.add_edge("after_tools", "llm")

    return graph.compile()


# ── Public API ────────────────────────────────────────────────────────────────

def solve_challenge(
    description: str,
    extra_context: str = "",
    profile: str = "ctf-solo",
    api_key: str | None = None,
) -> dict:
    """
    Run the CTF agent on a challenge description.

    Args:
        description:   Challenge description as given to competitors.
        extra_context: Extra context (file names, hints, etc.).
        profile:       Profile name — one of ctf-solo, ctf-team, ctf-practice.

    Returns:
        dict with keys: flag, messages, iterations.
    """
    profile_config = _load_profile(profile)
    system_prompt  = build_system_prompt(profile)

    # Override config values from profile
    import config as cfg
    cfg.MAX_ITERATIONS = profile_config.get("backend", {}).get("max_iterations", cfg.MAX_ITERATIONS)
    cfg.AGENT_TEMPERATURE = profile_config.get("backend", {}).get("temperature", cfg.AGENT_TEMPERATURE)

    agent = build_ctf_agent(api_key=api_key)

    user_content = description
    if extra_context:
        user_content += f"\n\nAdditional context:\n{extra_context}"

    initial_state: AgentState = {
        "messages": [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_content),
        ],
        "iterations": 0,
        "flag": None,
    }

    final_state = agent.invoke(initial_state, {"recursion_limit": cfg.MAX_ITERATIONS * 3})

    _maybe_capture_auto_skill(
        profile_name=profile,
        profile_config=profile_config,
        challenge_desc=description,
        iterations=final_state.get("iterations", 0),
        messages=final_state["messages"],
    )

    return {
        "flag": final_state.get("flag"),
        "messages": final_state["messages"],
        "iterations": final_state.get("iterations", 0),
    }
