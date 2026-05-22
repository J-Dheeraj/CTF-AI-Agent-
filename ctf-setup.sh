#!/usr/bin/env bash
# ctf-setup.sh — automated setup for CTF AI Agent
# Mirrors the hermes-setup.sh pattern from MPS-AI-Agent-Hermes.
set -e

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()    { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
die()     { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }
header()  { echo -e "\n${BOLD}$*${NC}"; }

header "CTF AI Agent — Setup"
echo "This script installs dependencies, configures your profile, and verifies the agent."
echo

# ── Step 1: Python check ──────────────────────────────────────────────────────
header "Step 1: Python 3.10+"
python3 --version >/dev/null 2>&1 || die "Python 3 not found. Install from python.org."
PY_MINOR=$(python3 -c "import sys; print(sys.version_info.minor)")
[ "$PY_MINOR" -ge 10 ] || die "Python 3.10+ required (found 3.$PY_MINOR)."
info "Python OK"

# ── Step 2: pip install ───────────────────────────────────────────────────────
header "Step 2: Install Python dependencies"
pip install -r requirements.txt -q && info "Dependencies installed." || die "pip install failed."

# Also install PyYAML (needed for profile config.yaml loading)
pip install pyyaml -q

# ── Step 3: Backend selection ─────────────────────────────────────────────────
header "Step 3: Configure LLM backend"
echo "Which backend do you want to use for Hermes?"
echo "  1) Ollama (local, free, requires GPU or fast CPU)"
echo "  2) OpenRouter (cloud, requires API key)"
echo "  3) Together AI (cloud, requires API key)"
read -rp "Choice [1-3, default 1]: " BACKEND_CHOICE
BACKEND_CHOICE=${BACKEND_CHOICE:-1}

case "$BACKEND_CHOICE" in
  1)
    BACKEND="ollama"
    info "Checking Ollama..."
    ollama --version >/dev/null 2>&1 || warn "Ollama not found. Install from https://ollama.com then run: ollama pull nous-hermes3"
    ollama list 2>/dev/null | grep -q "nous-hermes" || warn "nous-hermes3 not pulled yet. Run: ollama pull nous-hermes3"
    ;;
  2)
    BACKEND="openrouter"
    read -rp "OpenRouter API key (sk-or-...): " OR_KEY
    [ -n "$OR_KEY" ] || die "API key required."
    echo "OPENROUTER_API_KEY=$OR_KEY" >> .env
    ;;
  3)
    BACKEND="together"
    read -rp "Together AI API key: " TA_KEY
    [ -n "$TA_KEY" ] || die "API key required."
    echo "TOGETHER_API_KEY=$TA_KEY" >> .env
    ;;
  *)
    die "Invalid choice."
    ;;
esac

# ── Step 4: Write .env ────────────────────────────────────────────────────────
header "Step 4: Write .env"
if [ ! -f .env ]; then
  cp .env.example .env
fi
# Patch HERMES_BACKEND in .env
if grep -q "^HERMES_BACKEND=" .env; then
  sed -i "s/^HERMES_BACKEND=.*/HERMES_BACKEND=$BACKEND/" .env
else
  echo "HERMES_BACKEND=$BACKEND" >> .env
fi
info ".env configured (HERMES_BACKEND=$BACKEND)"

# ── Step 5: Profile selection ─────────────────────────────────────────────────
header "Step 5: Default profile"
echo "Available profiles:"
echo "  ctf-solo     — autonomous solver (recommended for competitions)"
echo "  ctf-team     — collaborative, shares findings"
echo "  ctf-practice — guided learning with hints"
read -rp "Default profile [ctf-solo]: " PROFILE
PROFILE=${PROFILE:-ctf-solo}
[[ "$PROFILE" =~ ^(ctf-solo|ctf-team|ctf-practice)$ ]] || die "Unknown profile: $PROFILE"
info "Default profile: $PROFILE"

# ── Step 6: Verify profiles and skills ───────────────────────────────────────
header "Step 6: Verify profiles and skills"
for p in ctf-solo ctf-team ctf-practice; do
  [ -f "profiles/$p/SOUL.md" ]    && info "  profiles/$p/SOUL.md ✓" || warn "  profiles/$p/SOUL.md missing"
  [ -f "profiles/$p/config.yaml" ] && info "  profiles/$p/config.yaml ✓" || warn "  profiles/$p/config.yaml missing"
done
for s in SKILL-web SKILL-crypto SKILL-binary SKILL-forensics SKILL-osint SKILL-recon SKILL-misc SKILL-feedback; do
  [ -f "skills/$s.md" ] && info "  skills/$s.md ✓" || warn "  skills/$s.md missing"
done
[ -d "skills/auto" ] && info "  skills/auto/ ✓" || mkdir -p skills/auto && info "  skills/auto/ created"

# ── Step 7: Smoke test ────────────────────────────────────────────────────────
header "Step 7: Smoke test"
python3 -c "
import sys
sys.path.insert(0, '.')
import config
from agent import build_system_prompt
prompt = build_system_prompt('$PROFILE')
assert len(prompt) > 100, 'System prompt too short'
print('  System prompt loaded: ' + str(len(prompt)) + ' chars')
print('  Profile: $PROFILE')
" && info "Smoke test passed." || die "Smoke test failed — check the error above."

# ── Done ──────────────────────────────────────────────────────────────────────
header "Setup complete"
echo
echo "Run the agent:"
echo "  python main.py --profile $PROFILE --challenge \"Your CTF challenge here\""
echo
echo "Other profiles:"
echo "  python main.py --profile ctf-team     --challenge \"...\""
echo "  python main.py --profile ctf-practice --challenge \"...\""
echo
echo "Verbose mode (show all tool calls):"
echo "  python main.py --profile $PROFILE --verbose --challenge \"...\""
echo
echo "Log a feedback correction:"
echo "  /feedback [wrong approach] → [correct approach] | category: web"
echo
echo "Review auto-generated skill patterns:"
echo "  ls skills/auto/"
