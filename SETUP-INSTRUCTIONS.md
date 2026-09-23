# Aifya — Claude Code Setup Instructions
## Copy-paste these commands in order

---

## STEP 1: Install Claude Code (if not already installed)

```bash
# Install Claude Code CLI
npm install -g @anthropic-ai/claude-code

# Verify installation
claude --version

# Login
claude login
```

---

## STEP 2: Create your project and copy files

```bash
# Create project directory (or cd into your existing repo)
mkdir aifya && cd aifya
git init

# Copy the CLAUDE.md to project root
# (Copy the CLAUDE.md file from the downloaded files)
cp ~/Downloads/CLAUDE.md ./CLAUDE.md

# Create the .claude directory structure
mkdir -p .claude/skills/kenya-clinical
mkdir -p .claude/skills/fhir-builder
mkdir -p .claude/skills/sha-claims
mkdir -p .claude/skills/redcap-integration
mkdir -p .claude/skills/swahili-medical
mkdir -p .claude/skills/offline-patterns
mkdir -p .claude/agents
mkdir -p docs

# Copy all skill files from downloaded files into their directories
# Copy all agent files from downloaded files into .claude/agents/
# Copy settings.json into .claude/
# (These are all the files generated for you)
```

---

## STEP 3: Install MCP Servers (run each command)

```bash
# PostgreSQL — lets Claude inspect your DB schema and run queries
claude mcp add postgres-mcp \
  --transport stdio \
  -- npx -y @modelcontextprotocol/server-postgres \
  "postgresql://user:password@localhost:5432/aifya"

# GitHub — lets Claude create PRs, manage issues, review code
claude mcp add github \
  --transport stdio \
  -- npx -y @modelcontextprotocol/server-github

# Playwright — lets Claude browse your app and run E2E tests
claude mcp add playwright \
  --transport stdio \
  -- npx -y @anthropic-ai/mcp-playwright

# Context7 — live documentation lookup (prevents hallucinated APIs)
claude mcp add context7 \
  --transport stdio \
  -- npx -y @context7/mcp-server
```

**Note:** Replace the PostgreSQL connection string with your actual credentials once your database is running.

---

## STEP 4: Install Community Plugins

```bash
# Official code review plugin (free, from Anthropic)
claude /plugin install anthropic/code-review

# TypeScript LSP for real-time type checking
claude /plugin install anthropic/typescript-lsp
```

---

## STEP 5: Copy your existing codebase

```bash
# If you have existing ScribeAI and ClaimFlow codebases:
cp -r /path/to/your/scribe-ai ./services/ai-service/scribe/
cp -r /path/to/your/claimflow ./services/ai-service/claimflow/

# Claude Code will build the HMIS application around these existing modules
```

---

## STEP 6: Populate docs/ directory

Copy the specification documents into `docs/` and rename them:

| Source file (from downloads) | Destination |
|---|---|
| hmis-blueprint.md | docs/architecture.md |
| hmis-hpc-update.md | docs/gpu-deployment.md |
| hmis-research-analytics.md | docs/analytics.md |
| afyaai-complete-spec.md | docs/database-schema.md (Section 4) + docs/api-contracts.md (Section 5) + docs/frontend-patterns.md (Section 6) |
| aifya-gap-analysis.md | docs/module-specs.md |
| aifya-final-specification.md | docs/clinical-trials.md + docs/testing-strategy.md |

**Or simply:** put all spec files in `docs/` as-is. The CLAUDE.md references them with `@docs/` prefix and Claude Code will read whichever is relevant.

---

## STEP 7: Start your first Claude Code session

```bash
# Navigate to project root
cd aifya

# Start Claude Code
claude

# Your first prompt should be:
# "Read CLAUDE.md and @docs/database-schema.md. Set up the monorepo
#  structure with package.json, Docker configs, and the first module:
#  Patient Registration."
```

---

## STEP 8: Module-by-module build prompts

Use these prompts one per session for efficient, focused builds:

### Session 1: Project scaffold
```
Set up the Aifya monorepo: apps/web (Next.js 15), services/api-gateway (FastAPI),
services/billing-service (Go), packages/shared (types). Include docker-compose.yml,
Makefile with dev/test/lint/typecheck commands, and .env.example.
```

### Session 2: Database + Auth
```
Read @docs/database-schema.md. Create all SQLAlchemy models with the base audit mixin,
Alembic migrations, and Keycloak integration for auth. Start with: facilities, staff,
patients, encounters, clinical_notes, diagnoses, prescriptions tables.
```

### Session 3: Patient Registration
```
Build the Patient Registration module end-to-end. Backend: CRUD API with search
(name, national ID, phone). Frontend: registration form, patient search with Cmd+K,
patient detail page with timeline. Include offline support and Swahili translations.
```

### Session 4: OPD Queue + Consultation
```
Build OPD module. Queue management with triage (SATS colors). Consultation page with:
vitals panel, diagnosis entry (ICD-10 autocomplete), prescription panel (drug autocomplete
with KEML tag), lab order panel. Include the ScribeAI recorder button.
```

### Continue with one module per session...

---

## STEP 9: Run agents periodically

```bash
# After implementing a module, run the code reviewer:
claude "Run the code-reviewer agent on all files changed in the last commit"

# After adding new UI strings, run the translator:
claude "Run the i18n-translator agent to update Swahili translations"

# Before a PR, run the security auditor:
claude "Run the security-auditor agent on the entire services/ directory"

# After implementing a clinical workflow, run the test writer:
claude "Run the test-writer agent to create clinical scenario tests for the OPD module"
```

---

## STEP 10: Verify your setup

After Steps 1-6, run this to verify everything is configured:

```bash
# Check CLAUDE.md exists
ls -la CLAUDE.md

# Check skills are in place
ls .claude/skills/*/SKILL.md

# Check agents are in place
ls .claude/agents/*.md

# Check settings
cat .claude/settings.json | python -m json.tool

# Check MCP servers
claude mcp list

# Check plugins
claude /plugin list

# Start Claude Code and ask it to verify
claude "Check that all Aifya skills, agents, and MCP servers are properly configured. List what you see."
```

---

## Directory Structure After Setup

```
aifya/
├── CLAUDE.md                          ✅ Project config (auto-loaded)
├── .claude/
│   ├── settings.json                  ✅ Hooks + permissions
│   ├── skills/
│   │   ├── kenya-clinical/SKILL.md    ✅ Clinical standards
│   │   ├── fhir-builder/SKILL.md      ✅ FHIR R4 patterns
│   │   ├── sha-claims/SKILL.md        ✅ SHA integration
│   │   ├── redcap-integration/SKILL.md ✅ REDCap sync
│   │   ├── swahili-medical/SKILL.md   ✅ Medical Swahili
│   │   └── offline-patterns/SKILL.md  ✅ Offline-first
│   └── agents/
│       ├── code-reviewer.md           ✅ Clinical safety review
│       ├── test-writer.md             ✅ Clinical scenario tests
│       ├── i18n-translator.md         ✅ Swahili translations
│       └── security-auditor.md        ✅ Security audit
├── docs/                              ✅ Detailed specs (progressive disclosure)
│   ├── (your spec files here)
├── apps/
│   └── web/                           🔨 (Claude Code builds this)
├── services/
│   ├── api-gateway/                   🔨 (Claude Code builds this)
│   ├── ai-service/
│   │   ├── scribe/                    📦 (Your existing ScribeAI code)
│   │   └── claimflow/                 📦 (Your existing ClaimFlow code)
│   ├── billing-service/               🔨 (Claude Code builds this)
│   └── sync-service/                  🔨 (Claude Code builds this)
├── ml/                                🔨 (Claude Code builds this)
├── infrastructure/                    🔨 (Claude Code builds this)
└── packages/shared/                   🔨 (Claude Code builds this)
```

✅ = You set up (from these files)
📦 = Your existing code
🔨 = Claude Code builds

---

## Estimated Token Cost Per Session

| Session Type | Tokens Used | Estimated Cost |
|---|---|---|
| CLAUDE.md (auto-loaded) | ~3,000 | Always |
| + 1 skill (on-demand) | ~500 | When relevant |
| + 1 MCP tool call | ~2,000 | When using DB/GitHub |
| + 1 doc reference | ~3,000 | When reading specs |
| **Typical session total** | **~8,000-12,000** | **Very efficient** |
| Without progressive disclosure | ~35,000+ | **3-4x more expensive** |

Your setup saves ~70-80% on tokens compared to putting everything in CLAUDE.md.

---

*You're ready to build Aifya. Start with Session 1 (project scaffold) and work through one module per session.*
