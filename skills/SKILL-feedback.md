# SKILL-feedback — Feedback & GEPA Evolution

## Feedback Command
```
/feedback [wrong approach] → [correct approach] | category: [web|crypto|binary|forensics|osint|misc|recon]
```

**Examples:**
```
/feedback assumed SHA256 was truncated MD5 → was SHA1 | category: crypto
/feedback tried SQLi on login first → was JWT alg=none | category: web
/feedback binwalk missed embedded ZIP → needed manual xxd offset search | category: forensics
```

Corrections are appended to `feedback-log.md` with a timestamp.

---

## How GEPA Works

**GEPA** (Generative Experience-based Pattern Adaptation) evolves SKILL files from accumulated
feedback and high-tool-count sessions.

### Trigger Conditions
- 3 or more `/feedback` entries with the same category → flag for skill update
- Any session using 5+ tool calls on a single challenge → auto-capture pattern candidate
- Weekly curator runs every Sunday: reviews all `feedback-log.md` entries from the past week

### Evolution Pipeline
1. `feedback-log.md` reviewed for recurring patterns
2. Patterns extracted (no solution details — technique-level only)
3. New or updated skill section drafted in `skills/auto/<category>-<date>.md`
4. Human reviews `skills/auto/` before any changes are applied
5. Approved changes merged into the relevant `SKILL-*.md`
6. `feedback-log.md` archived, reset for the next cycle

### Manual Trigger
```bash
# From project root
python main.py --profile ctf-solo --challenge "run skills evolve now"
# OR edit SKILL files directly and restart the agent
```

---

## What Gets Captured

**YES — technique-level patterns:**
- "SQLi on GraphQL introspection — use `{__schema{...}}` not standard payloads"
- "RSA e=65537 with n~512 bits → Fermat factorization worked, p and q were close"
- "PNG with extra data after IEND chunk — binwalk missed it, manual xxd found offset"

**NO — solution details:**
- Specific challenge flags
- Platform-specific infrastructure details (IP, ports from live competitions)
- Any data that could deanonymise a challenge author or platform

---

## feedback-log.md Format

Entries are appended automatically. Each entry:
```
[2025-01-15T14:23:01] category=crypto
  wrong:   assumed fixed XOR key length of 8
  correct: IC analysis showed key length 13; vigenere with 13-char key
---
```

Pattern threshold: 3 similar entries in the same category → GEPA proposes a skill update.

---

## Auto-Skill Generation
When a session uses 5+ tool calls, the agent writes a brief pattern note to `skills/auto/`:
```
skills/auto/web-2025-01-15-jwt-algnone.md
skills/auto/crypto-2025-01-20-rsa-fermat.md
```
Review these weekly. Merge the useful ones into the main SKILL files.
