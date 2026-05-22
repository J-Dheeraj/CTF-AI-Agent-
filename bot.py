"""
bot.py — Telegram bot for the Singapore remote support team (20 people).

Each team member DMs the bot or uses the shared group. The bot talks to
the CTF Command Center (server.py) over HTTP so the shared challenge board
stays consistent for Vegas too.

Commands
--------
/challenges [category]   — list all challenges (unsolved first)
/challenge <id>          — show challenge details + last 3 AI messages
/new                     — add a challenge (guided multi-step)
/solve <id> [profile]    — trigger agent on a challenge (default: ctf-singapore)
/cancel <id>             — cancel a running agent job
/flag <id> <flag>        — submit a flag manually
/assign <id> <@username> — assign a challenge to yourself or someone else
/score                   — team scoreboard
/active                  — list challenges with agents running
/help                    — show this list

Set in .env:
  TELEGRAM_BOT_TOKEN=...
  SERVER_URL=http://localhost:8000      (or your VPS URL)
  CTF_TOKEN=changeme
"""

from __future__ import annotations

import os
import textwrap
from typing import cast

import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN  = os.environ["TELEGRAM_BOT_TOKEN"]
SERVER_URL = os.getenv("SERVER_URL", "http://localhost:8000").rstrip("/")
CTF_TOKEN  = os.getenv("CTF_TOKEN", "changeme")
PROFILES   = ["ctf-singapore", "ctf-solo", "ctf-team", "ctf-vegas", "ctf-practice"]

HEADERS = {"X-CTF-Token": CTF_TOKEN, "Content-Type": "application/json"}

# ConversationHandler states
(NEW_TITLE, NEW_CATEGORY, NEW_POINTS, NEW_DESC, NEW_FILES, NEW_CONFIRM) = range(6)


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def _get(path: str) -> dict | list:
    r = httpx.get(f"{SERVER_URL}{path}", headers=HEADERS, timeout=10)
    r.raise_for_status()
    return r.json()


def _post(path: str, body: dict) -> dict:
    r = httpx.post(f"{SERVER_URL}{path}", json=body, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()


def _delete(path: str) -> dict:
    r = httpx.delete(f"{SERVER_URL}{path}", headers=HEADERS, timeout=10)
    r.raise_for_status()
    return r.json()


# ── Formatters ────────────────────────────────────────────────────────────────

_STATUS_EMOJI = {
    "unsolved":    "🔴",
    "in_progress": "🟡",
    "solved":      "🟢",
    "abandoned":   "⚫",
}
_CAT_EMOJI = {
    "web":       "🌐",
    "crypto":    "🔐",
    "binary":    "💾",
    "forensics": "🔬",
    "osint":     "🕵️",
    "misc":      "🎲",
    "recon":     "📡",
    "unknown":   "❓",
}


def _fmt_challenge_list(challenges: list[dict]) -> str:
    if not challenges:
        return "No challenges found."
    lines = []
    for c in challenges:
        e  = _STATUS_EMOJI.get(c["status"], "❓")
        ce = _CAT_EMOJI.get(c["category"], "❓")
        pt = f" [{c['points']}pts]" if c["points"] else ""
        ag = " 🤖" if c.get("agent_running") else ""
        as_ = f" @{c['assigned_to']}" if c.get("assigned_to") else ""
        lines.append(f"{e}{ce} #{c['id']} {c['title']}{pt}{ag}{as_}")
    return "\n".join(lines)


def _fmt_challenge_detail(c: dict) -> str:
    e  = _STATUS_EMOJI.get(c["status"], "❓")
    ce = _CAT_EMOJI.get(c["category"], "❓")
    flag_line = f"\n🚩 Flag: `{c['flag']}`" if c.get("flag") else ""
    assign_line = f"\n👤 Assigned: {c['assigned_to']}" if c.get("assigned_to") else ""
    agent_line  = "\n🤖 Agent: RUNNING" if c.get("agent_running") else ""
    msgs = c.get("messages", [])
    ai_msgs = [m for m in msgs if m["role"] == "ai"]
    preview = ""
    if ai_msgs:
        last = ai_msgs[-1]["content"]
        preview = "\n\n*Latest AI output:*\n" + textwrap.shorten(last, width=400, placeholder="…")
    return (
        f"{e}{ce} *#{c['id']} {c['title']}*\n"
        f"Category: {c['category']} | Points: {c.get('points', 0)}\n"
        f"Status: {c['status']}{flag_line}{assign_line}{agent_line}\n\n"
        f"*Description:*\n{textwrap.shorten(c['description'], 300, placeholder='…')}"
        f"{preview}"
    )


# ── Command handlers ──────────────────────────────────────────────────────────

async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "🚩 *CTF Command Center — Singapore Bot*\n\n"
        "/challenges `[category]` — list challenges\n"
        "/challenge `<id>` — challenge detail\n"
        "/new — add a challenge (guided)\n"
        "/solve `<id>` `[profile]` — run AI agent\n"
        "/cancel `<id>` — stop agent\n"
        "/flag `<id>` `<flag>` — submit flag\n"
        "/assign `<id>` `<name>` — assign challenge\n"
        "/score — team scoreboard\n"
        "/active — challenges with agents running\n\n"
        "Profiles: `ctf-singapore` (default) · `ctf-vegas` · `ctf-solo`\n"
    )
    await update.message.reply_markdown(text)


async def cmd_challenges(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    category = ctx.args[0].lower() if ctx.args else None
    try:
        data = cast(list, _get(f"/api/challenges{('?category=' + category) if category else ''}"))
    except Exception as e:
        await update.message.reply_text(f"Server error: {e}")
        return
    unsolved   = [c for c in data if c["status"] != "solved"]
    solved     = [c for c in data if c["status"] == "solved"]
    sb         = cast(dict, _get("/api/scoreboard"))
    header     = f"📊 *{sb['solved']}/{sb['total']} solved | {sb['points']} pts*\n\n"
    body       = _fmt_challenge_list(unsolved + solved)
    await update.message.reply_markdown(header + body)


async def cmd_challenge(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not ctx.args:
        await update.message.reply_text("Usage: /challenge <id>"); return
    try:
        c = cast(dict, _get(f"/api/challenges/{ctx.args[0]}"))
    except Exception as e:
        await update.message.reply_text(f"Error: {e}"); return
    text = _fmt_challenge_detail(c)
    kb = []
    if c["status"] != "solved" and not c.get("agent_running"):
        kb.append([
            InlineKeyboardButton("🤖 Solve (SG)", callback_data=f"solve:{c['id']}:ctf-singapore"),
            InlineKeyboardButton("⚡ Solve (Vegas)", callback_data=f"solve:{c['id']}:ctf-vegas"),
        ])
    if c.get("agent_running"):
        kb.append([InlineKeyboardButton("🛑 Cancel agent", callback_data=f"cancel:{c['id']}")])
    markup = InlineKeyboardMarkup(kb) if kb else None
    await update.message.reply_markdown(text, reply_markup=markup)


async def button_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    parts = query.data.split(":")
    action = parts[0]

    if action == "solve":
        cid, profile = parts[1], parts[2]
        try:
            r = _post(f"/api/challenges/{cid}/solve", {"profile": profile})
            await query.edit_message_text(f"🤖 Agent started on #{cid} ({profile}). Status: {r['status']}")
        except Exception as e:
            await query.edit_message_text(f"Error: {e}")

    elif action == "cancel":
        cid = parts[1]
        try:
            r = _delete(f"/api/challenges/{cid}/solve")
            await query.edit_message_text(f"🛑 Agent cancelled for #{cid}: {r}")
        except Exception as e:
            await query.edit_message_text(f"Error: {e}")


async def cmd_solve(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not ctx.args:
        await update.message.reply_text("Usage: /solve <id> [profile]"); return
    cid     = ctx.args[0]
    profile = ctx.args[1] if len(ctx.args) > 1 else "ctf-singapore"
    if profile not in PROFILES:
        await update.message.reply_text(f"Unknown profile. Use one of: {', '.join(PROFILES)}"); return
    try:
        r = _post(f"/api/challenges/{cid}/solve", {"profile": profile})
    except Exception as e:
        await update.message.reply_text(f"Error: {e}"); return
    await update.message.reply_text(f"🤖 Agent submitted for #{cid} ({profile}). Status: {r['status']}")


async def cmd_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not ctx.args:
        await update.message.reply_text("Usage: /cancel <id>"); return
    try:
        r = _delete(f"/api/challenges/{ctx.args[0]}/solve")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}"); return
    await update.message.reply_text(f"🛑 Cancel result: {r}")


async def cmd_flag(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if len(ctx.args) < 2:
        await update.message.reply_text("Usage: /flag <id> <flag>"); return
    cid  = ctx.args[0]
    flag = " ".join(ctx.args[1:])
    user = update.effective_user.username or update.effective_user.first_name
    try:
        r = _post(f"/api/challenges/{cid}/flag", {"flag": flag, "submitted_by": user})
    except Exception as e:
        await update.message.reply_text(f"Error: {e}"); return
    await update.message.reply_markdown(f"🚩 *Flag recorded for #{cid}!*\n`{flag}`")


async def cmd_assign(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if len(ctx.args) < 2:
        await update.message.reply_text("Usage: /assign <id> <name>"); return
    cid    = ctx.args[0]
    name   = ctx.args[1].lstrip("@")
    try:
        _post(f"/api/challenges/{cid}/assign", {"assigned_to": name, "profile": "ctf-singapore"})
    except Exception as e:
        await update.message.reply_text(f"Error: {e}"); return
    await update.message.reply_text(f"👤 #{cid} assigned to {name}")


async def cmd_score(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        sb = cast(dict, _get("/api/scoreboard"))
    except Exception as e:
        await update.message.reply_text(f"Error: {e}"); return
    lines = [f"📊 *Team Scoreboard*", f"Solved: {sb['solved']}/{sb['total']} | Points: {sb['points']}\n"]
    for cat in sb.get("by_category", []):
        ce = _CAT_EMOJI.get(cat["category"], "❓")
        lines.append(f"{ce} {cat['category']}: {cat['s']}/{cat['n']}")
    await update.message.reply_markdown("\n".join(lines))


async def cmd_active(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        status = cast(dict, _get("/api/status"))
    except Exception as e:
        await update.message.reply_text(f"Error: {e}"); return
    ids = status.get("active_agents", [])
    ws  = status.get("ws_clients", 0)
    if not ids:
        await update.message.reply_text(f"No agents running. {ws} users connected.")
        return
    lines = [f"🤖 *{len(ids)} agents running* | {ws} users connected"]
    for cid in ids:
        try:
            c = cast(dict, _get(f"/api/challenges/{cid}"))
            lines.append(f"  • #{cid} {c['title']} [{c['category']}]")
        except Exception:
            lines.append(f"  • #{cid}")
    await update.message.reply_markdown("\n".join(lines))


# ── /new — multi-step guided challenge intake ─────────────────────────────────

async def new_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("📝 New challenge — what's the *title*?", parse_mode="Markdown")
    return NEW_TITLE

async def new_title(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data["title"] = update.message.text.strip()
    cats = " | ".join(["web","crypto","binary","forensics","osint","misc","recon","unknown"])
    await update.message.reply_text(f"Category? ({cats})")
    return NEW_CATEGORY

async def new_category(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    cat = update.message.text.strip().lower()
    ctx.user_data["category"] = cat if cat in ["web","crypto","binary","forensics","osint","misc","recon"] else "unknown"
    await update.message.reply_text("Points? (0 if unknown)")
    return NEW_POINTS

async def new_points(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        ctx.user_data["points"] = int(update.message.text.strip())
    except ValueError:
        ctx.user_data["points"] = 0
    await update.message.reply_text("Paste the *challenge description*:", parse_mode="Markdown")
    return NEW_DESC

async def new_desc(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data["description"] = update.message.text.strip()
    await update.message.reply_text("Any filenames in workspace/? (comma-separated, or 'none')")
    return NEW_FILES

async def new_files(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    raw = update.message.text.strip()
    ctx.user_data["files"] = [f.strip() for f in raw.split(",") if f.strip() and f.strip() != "none"]
    d = ctx.user_data
    summary = (
        f"*Confirm new challenge:*\n"
        f"Title: {d['title']}\n"
        f"Category: {d['category']} | Points: {d['points']}\n"
        f"Files: {d['files'] or 'none'}\n"
        f"Description: {textwrap.shorten(d['description'], 200, placeholder='…')}\n\n"
        f"Reply *yes* to add, anything else to cancel."
    )
    await update.message.reply_markdown(summary)
    return NEW_CONFIRM

async def new_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text.strip().lower() not in ("yes", "y"):
        await update.message.reply_text("Cancelled.")
        ctx.user_data.clear()
        return ConversationHandler.END
    d = ctx.user_data
    try:
        r = _post("/api/challenges", {
            "title":       d["title"],
            "category":    d["category"],
            "points":      d["points"],
            "description": d["description"],
            "files":       d["files"],
            "profile":     "ctf-singapore",
        })
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")
        return ConversationHandler.END
    cid = r["id"]
    await update.message.reply_markdown(
        f"✅ Challenge *#{cid} {d['title']}* added!\n"
        f"Start agent: /solve {cid}"
    )
    ctx.user_data.clear()
    return ConversationHandler.END

async def new_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Challenge intake cancelled.")
    ctx.user_data.clear()
    return ConversationHandler.END


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    app_bot = Application.builder().token(BOT_TOKEN).build()

    new_conv = ConversationHandler(
        entry_points=[CommandHandler("new", new_start)],
        states={
            NEW_TITLE:    [MessageHandler(filters.TEXT & ~filters.COMMAND, new_title)],
            NEW_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, new_category)],
            NEW_POINTS:   [MessageHandler(filters.TEXT & ~filters.COMMAND, new_points)],
            NEW_DESC:     [MessageHandler(filters.TEXT & ~filters.COMMAND, new_desc)],
            NEW_FILES:    [MessageHandler(filters.TEXT & ~filters.COMMAND, new_files)],
            NEW_CONFIRM:  [MessageHandler(filters.TEXT & ~filters.COMMAND, new_confirm)],
        },
        fallbacks=[CommandHandler("cancel", new_cancel)],
    )

    app_bot.add_handler(CommandHandler("help",       cmd_help))
    app_bot.add_handler(CommandHandler("start",      cmd_help))
    app_bot.add_handler(CommandHandler("challenges", cmd_challenges))
    app_bot.add_handler(CommandHandler("challenge",  cmd_challenge))
    app_bot.add_handler(CommandHandler("solve",      cmd_solve))
    app_bot.add_handler(CommandHandler("cancel",     cmd_cancel))
    app_bot.add_handler(CommandHandler("flag",       cmd_flag))
    app_bot.add_handler(CommandHandler("assign",     cmd_assign))
    app_bot.add_handler(CommandHandler("score",      cmd_score))
    app_bot.add_handler(CommandHandler("active",     cmd_active))
    app_bot.add_handler(new_conv)
    app_bot.add_handler(CallbackQueryHandler(button_callback))

    print(f"CTF Bot running. Connected to {SERVER_URL}")
    app_bot.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
