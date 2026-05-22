# CTF AI Agent

A multi-user AI agent for competitive CTF (Capture the Flag) events. Built for a 23-person team — 3 on-site at DEFCON Las Vegas + 20 remote in Singapore — all solving challenges simultaneously through a shared web dashboard.

## How It Works

One person runs the server. Everyone else connects via browser or Telegram. The AI agent works challenges in the background; the whole team sees results in real time.

```
Browser / Telegram
      │
      ▼
FastAPI Server  ──  SQLite challenge board  ──  WebSocket broadcast
      │
      ▼
LangGraph ReAct Agent  (one thread per challenge, up to 5 concurrent)
      │
      ▼
LLM backend (Gemini / Groq / Claude / Ollama)
```

---

## Features

- **Real-time dashboard** — Kanban-style challenge board, live flag notifications, scoreboard
- **Telegram bot** — Singapore team submits and tracks challenges without opening a browser
- **Concurrent solving** — up to 5 agent sessions run in parallel (one per challenge)
- **Two-team workflow** — Vegas profile (fast, terse, 20 iterations) hands off to Singapore profile (deep, 50 iterations) when stuck
- **SKILL knowledge base** — domain playbooks for web, crypto, binary, forensics, OSINT, recon, misc
- **Auto skill capture** — agent summarises winning techniques after each solve for future sessions
- **Rate limiting** — per-IP request cap + concurrent agent cap so no one can abuse the shared key
- **Multiple LLM backends** — Gemini (free), Groq (free), Claude (best quality), Ollama (local)

---

## Quickstart

### 1. Clone and install

```bash
git clone https://github.com/J-Dheeraj/CTF-AI-Agent-.git
cd CTF-AI-Agent-
pip install -r requirements.txt
pip install -r requirements-server.txt
```

### 2. Configure

```bash
cp .env.example .env
```

Edit `.env` and set your LLM backend. Recommended free option:

```env
HERMES_BACKEND=gemini
GEMINI_API_KEY=AIzaSy...        # free at aistudio.google.com
GEMINI_MODEL=gemini-2.0-flash

CTF_TOKEN=your-team-password    # teammates enter this to access the dashboard
```

### 3. Start the server

```bash
python -m uvicorn server:app --host 0.0.0.0 --port 8080
```

Open `http://localhost:8080` in your browser.

### 4. Share with your team

```
Dashboard:  http://<your-ip>:8080
Token:      whatever you set as CTF_TOKEN
```

Teammates open the URL, enter the token, and start submitting challenges. No account, no API key needed on their end.

---

## LLM Backends

| Backend | Cost | Quality | Setup |
|---------|------|---------|-------|
| `gemini` | Free (1M tokens/day) | Good | [aistudio.google.com](https://aistudio.google.com) → Get API key |
| `groq` | Free (6k TPM limit) | Good | [console.groq.com](https://console.groq.com) → API Keys |
| `claude` | Pay per use | Best | [console.anthropic.com](https://console.anthropic.com) |
| `ollama` | Free, local | Depends on model | `ollama pull nous-hermes3` |

Switch by changing `HERMES_BACKEND` in `.env` and restarting the server.

---

## Profiles

Each challenge can be assigned a profile that controls the agent's behaviour and iteration budget.

| Profile | Use case | Max iterations | Style |
|---------|----------|---------------|-------|
| `ctf-vegas` | On-site, time pressure | 20 | Ultra-terse, pivots fast, posts HANDOFF after 3 fails |
| `ctf-singapore` | Remote deep analysis | 50 | Thorough, documents progress, posts HANDBACK summaries |
| `ctf-solo` | Single player | 30 | Balanced |
| `ctf-team` | General team use | 30 | Balanced |
| `ctf-practice` | Training / warmup | 30 | Verbose, explains reasoning |
| `ctf-lite` | Low token budget | 20 | Minimal skills, fast |

---

## Two-Team Handoff Workflow

```
Vegas gets a challenge → runs ctf-vegas profile
  │
  ├─ Flag found → posts to dashboard, everyone sees it
  │
  └─ Stuck after 3 attempts → posts HANDOFF note
        │
        ▼
     Singapore picks it up → runs ctf-singapore profile
     Reads Vegas's progress, goes deeper
        │
        ├─ Flag found → posts HANDBACK summary
        └─ Still stuck → escalates to full team discussion
```

---

## Telegram Bot (Singapore Team)

Set `TELEGRAM_BOT_TOKEN` in `.env` (get one from [@BotFather](https://t.me/BotFather)), then run:

```bash
python bot.py
```

Available commands:

| Command | Action |
|---------|--------|
| `/new` | Submit a new challenge (guided intake) |
| `/challenges` | List all challenges |
| `/solve <id>` | Trigger agent on a challenge |
| `/flag <id> <flag>` | Submit a flag manually |
| `/score` | Show scoreboard |
| `/active` | Show running agents |

---

## Project Structure

```
CTF-AI-Agent/
├── agent.py              # LangGraph ReAct agent — loads profile + skills, runs solve loop
├── server.py             # FastAPI REST + WebSocket hub
├── worker.py             # Thread pool — one thread per active challenge
├── challenge_store.py    # SQLite challenge board (WAL mode, thread-safe)
├── bot.py                # Telegram bot for Singapore team
├── llm_backend.py        # LLM factory (Gemini / Groq / Claude / Ollama)
├── config.py             # Settings loaded from .env
├── main.py               # Solo CLI mode: python main.py --profile ctf-solo
├── tools/                # Agent tools (bash, web, crypto, binary, file ops, search)
├── profiles/
│   ├── ctf-vegas/        # SOUL.md + config.yaml for each profile
│   ├── ctf-singapore/
│   ├── ctf-solo/
│   ├── ctf-team/
│   ├── ctf-practice/
│   └── ctf-lite/
├── skills/
│   ├── SKILL-web.md      # SQLi, LFI, SSTI, SSRF, JWT, XSS, XXE
│   ├── SKILL-crypto.md   # RSA, AES, XOR, classical ciphers, hash attacks
│   ├── SKILL-binary.md   # Buffer overflow, ROP, format string, pwntools
│   ├── SKILL-forensics.md # File carving, stego, pcap, Volatility
│   ├── SKILL-osint.md    # Domain recon, email/username, image OSINT
│   ├── SKILL-recon.md    # nmap, gobuster, ffuf, SMB, Redis
│   └── SKILL-misc.md     # Encoding, QR, jail escapes, number theory
├── public/
│   └── index.html        # Single-page team dashboard
├── .env.example          # Environment variable template
├── .gitignore
├── requirements.txt
└── requirements-server.txt
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in the values you need.

| Variable | Description |
|----------|-------------|
| `HERMES_BACKEND` | LLM backend: `gemini`, `groq`, `claude`, `ollama`, `openrouter` |
| `GEMINI_API_KEY` | Google AI Studio key (free) |
| `GROQ_API_KEY` | Groq key (free, 6k TPM limit) |
| `ANTHROPIC_API_KEY` | Anthropic key (paid, best quality) |
| `CTF_TOKEN` | Shared password for dashboard access |
| `MAX_CONCURRENT_AGENTS` | Max parallel solves (default: 5) |
| `RATE_LIMIT_PER_HOUR` | Max solve requests per IP per hour (default: 10) |
| `TELEGRAM_BOT_TOKEN` | Optional — enables the Telegram bot |
| `SERVER_PORT` | Server port (default: 8000) |

---

## Security Notes

- The LLM API key lives only in `.env` on the server — teammates never see it
- All solve requests require the `CTF_TOKEN`
- Rate limiting prevents any one person from burning through the API quota
- `.env` is in `.gitignore` — it will never be committed

---

## Built for DEFCON 2026
