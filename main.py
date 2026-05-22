#!/usr/bin/env python3
"""
main.py – CTF AI Agent CLI entry point.

Usage examples:
  # Interactive mode (paste challenge description)
  python main.py

  # Specify a profile (default: ctf-solo)
  python main.py --profile ctf-solo
  python main.py --profile ctf-team
  python main.py --profile ctf-practice

  # Pass challenge via argument
  python main.py --challenge "Decode this base64: aGVsbG8gd29ybGQ="

  # Load challenge from a text file
  python main.py --challenge-file challenges/web01.txt

  # Verbose: show every LLM message and tool call
  python main.py --verbose --challenge "..."

  # Place challenge files in workspace/ before running
  python main.py --challenge "Reverse the binary at 'crackme'. Find the password."
"""

from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

console = Console()

_PROFILES = ["ctf-solo", "ctf-team", "ctf-practice"]


def _print_message(msg, verbose: bool) -> None:
    if isinstance(msg, SystemMessage):
        if verbose:
            console.print(Panel(str(msg.content)[:500] + "…", title="[dim]System Prompt (SOUL + Skills)[/dim]", style="dim"))
        return

    if isinstance(msg, HumanMessage):
        console.print(Panel(str(msg.content), title="[bold cyan]You[/bold cyan]", border_style="cyan"))
        return

    if isinstance(msg, AIMessage):
        content = str(msg.content) if msg.content else ""
        tool_calls = msg.tool_calls or []

        if content:
            console.print(Panel(Markdown(content), title="[bold green]Hermes[/bold green]", border_style="green"))

        if tool_calls and verbose:
            for tc in tool_calls:
                console.print(
                    Panel(
                        f"[bold]{tc['name']}[/bold]\n{tc['args']}",
                        title="[yellow]Tool Call[/yellow]",
                        border_style="yellow",
                    )
                )
        return

    if isinstance(msg, ToolMessage) and verbose:
        content = str(msg.content)
        if len(content) > 1000:
            content = content[:1000] + "\n… [truncated]"
        console.print(
            Panel(
                content,
                title=f"[yellow]Tool Result: {msg.name}[/yellow]",
                border_style="dim yellow",
            )
        )


@click.command()
@click.option(
    "--profile", "-p",
    default="ctf-solo",
    type=click.Choice(_PROFILES),
    show_default=True,
    help="Agent profile to use.",
)
@click.option("--challenge", "-c", default=None, help="Challenge description as a string.")
@click.option("--challenge-file", "-f", default=None, type=click.Path(exists=True), help="Path to a .txt file with the challenge description.")
@click.option("--context", default="", help="Extra context (file names, hints, etc.).")
@click.option("--verbose", "-v", is_flag=True, help="Show all tool calls and results.")
def main(profile: str, challenge: str | None, challenge_file: str | None, context: str, verbose: bool) -> None:
    """CTF AI Agent – powered by NousResearch Hermes + LangGraph."""

    profile_labels = {
        "ctf-solo":     "[magenta]Solo Solver[/magenta]",
        "ctf-team":     "[blue]Team Coordinator[/blue]",
        "ctf-practice": "[cyan]Practice / Learning[/cyan]",
    }
    console.print(Rule(f"[bold]CTF AI Agent[/bold] · {profile_labels[profile]} · Hermes + LangGraph"))

    # ── Resolve challenge description ─────────────────────────────────────────
    if challenge_file:
        desc = Path(challenge_file).read_text(encoding="utf-8").strip()
    elif challenge:
        desc = challenge.strip()
    else:
        console.print("[cyan]Paste your challenge description below. Press Enter twice when done.[/cyan]\n")
        lines = []
        try:
            while True:
                line = input()
                if line == "" and lines and lines[-1] == "":
                    break
                lines.append(line)
        except (EOFError, KeyboardInterrupt):
            pass
        desc = "\n".join(lines).strip()

    if not desc:
        console.print("[red]No challenge provided. Exiting.[/red]")
        sys.exit(1)

    console.print(Panel(desc[:800] + ("…" if len(desc) > 800 else ""),
                         title="[bold]Challenge[/bold]", border_style="magenta"))
    console.print()

    # ── Run the agent ─────────────────────────────────────────────────────────
    from agent import solve_challenge

    console.print(f"[bold]Starting agent[/bold] (profile: [bold]{profile}[/bold]) … (Ctrl+C to abort)\n")

    try:
        result = solve_challenge(description=desc, extra_context=context, profile=profile)
    except KeyboardInterrupt:
        console.print("\n[yellow]Aborted by user.[/yellow]")
        sys.exit(0)
    except Exception as exc:
        console.print(f"\n[red bold]Agent error:[/red bold] {exc}")
        raise

    # ── Print conversation ────────────────────────────────────────────────────
    if verbose:
        console.print(Rule("Conversation"))
        for msg in result["messages"]:
            _print_message(msg, verbose=verbose)
        console.print()
    else:
        for msg in result["messages"]:
            if isinstance(msg, AIMessage) and msg.content:
                _print_message(msg, verbose=False)

    # ── Final summary ─────────────────────────────────────────────────────────
    console.print(Rule("Result"))
    import config as cfg
    console.print(f"Iterations used: {result['iterations']} / {cfg.MAX_ITERATIONS}")

    flag = result.get("flag")
    if flag:
        console.print(
            Panel(
                f"[bold green]{flag}[/bold green]",
                title="🚩  FLAG FOUND",
                border_style="bright_green",
            )
        )
    else:
        console.print("[yellow]No flag automatically extracted. Check the conversation above for clues.[/yellow]")
        if profile != "ctf-practice":
            console.print("[dim]Tip: Use /feedback to log what didn't work → helps GEPA improve your skills.[/dim]")


if __name__ == "__main__":
    main()
