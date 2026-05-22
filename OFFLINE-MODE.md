# OFFLINE-MODE.md — CTF AI Agent

## What "Offline" Means Here

The CTF AI Agent can run fully offline (no internet required) when using the Ollama backend.
In this mode:

- The LLM runs locally via Ollama (`nous-hermes3` or any compatible Hermes model)
- No challenge data leaves your machine
- Skill files are read from local `skills/` at startup
- GEPA auto-skill capture writes to local `skills/auto/` only
- `feedback-log.md` stays local

The only time a network connection is needed:
- `search_ctf_writeups` tool — searches CTFtime and GitHub (can be skipped)
- `web_request` / `web_fetch_page` tools — only if the challenge requires network access

---

## Data Flow

```
Challenge description (user input)
          │
          ▼
  profiles/<profile>/SOUL.md     ←── agent identity
  profiles/<profile>/config.yaml ←── behaviour settings
  skills/SKILL-*.md              ←── domain knowledge
          │
          ▼
  Hermes LLM (local Ollama or cloud)
          │
          ├──► tools (bash, python, file ops, encode/decode, crypto, binary, web, search)
          │
          ▼
  flag extracted → printed to terminal
          │
          ├──► feedback-log.md     (if /feedback command used)
          └──► skills/auto/*.md    (if session used 5+ tool calls — GEPA capture)
```

**Data that stays local always:**
- Challenge description and all files in `workspace/`
- Conversation history (in memory, not persisted)
- Feedback log and auto-generated skill drafts

**Data that may go to cloud (only when using OpenRouter/Together backend):**
- The system prompt (SOUL.md + SKILL files) and challenge description
- Tool call results sent back to the LLM for reasoning

---

## Security Boundary (from INTEGRATION.md in MPS pattern)

| Data type | Stays local | Goes to LLM backend |
|---|---|---|
| Challenge files in workspace/ | Yes (file_read tool reads locally) | Content sent as tool result |
| flags found | Local only | Mentioned in LLM response |
| feedback-log.md | Yes — never sent | No |
| skills/auto/ drafts | Yes — never sent | No |
| Web requests (web_request tool) | Made from your machine | URL/response sent to LLM |

---

## Configuration Summary

| Profile | Backend default | Temperature | Max iterations | Auto-capture |
|---|---|---|---|---|
| ctf-solo | ollama | 0.1 | 30 | Yes (5+ calls) |
| ctf-team | ollama | 0.2 | 40 | Yes (5+ calls) |
| ctf-practice | ollama | 0.3 | 50 | Yes (3+ calls) |

Override any value in the profile's `config.yaml` or via environment variables in `.env`.

---

## Weekly Skill Maintenance

1. Review `skills/auto/` for new auto-captured pattern files
2. Read each file — accept useful patterns, discard noise
3. Merge accepted patterns into the relevant `skills/SKILL-*.md`
4. Review `feedback-log.md` — look for recurring errors in the same category
5. Update the SKILL file for that category with the correction
6. Archive the log: `mv feedback-log.md feedback-log-$(date +%Y%m%d).md`

### GEPA Output Review Checklist
- [ ] Pattern is technique-level (not challenge-specific)
- [ ] No flag content or platform-specific infrastructure in the skill
- [ ] Improvement is genuinely new (not already in the SKILL file)
- [ ] Wording is clear and actionable
- [ ] Category is correct (web / crypto / binary / forensics / osint / misc / recon)

---

## Manual GEPA Trigger

GEPA runs automatically after sessions with 5+ tool calls.  
To manually evolve skills, add a note to `feedback-log.md` and run the curator:

```bash
# Add a manual pattern note
echo "[$(date -Iseconds)] category=crypto
  wrong:   assumed padding oracle → server wasn't leaking error diff
  correct: was timing oracle; used response time difference instead
---" >> feedback-log.md

# Then restart the agent — GEPA picks up feedback-log.md on next high-iteration session
```
