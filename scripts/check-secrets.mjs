#!/usr/bin/env node
/**
 * Secret guard for this repository.
 *
 * Catches the failure mode that actually bit us: a REAL secret pasted into a
 * tracked template (.env.example) instead of a placeholder. Two independent
 * checks, both scoped to secret-bearing setting names so ordinary shared
 * defaults (localhost URLs, Africa/Nairobi, facility UUIDs) never trip it:
 *
 *   1. Cross-reference - a value that also appears in an ignored, live .env.
 *   2. Shape           - a secret-named key assigned a literal high-entropy
 *                        value, plus private-key blocks and token prefixes.
 *
 * Usage:
 *   node scripts/check-secrets.mjs            # staged files (used by the hook)
 *   node scripts/check-secrets.mjs --all      # every tracked file
 *   SKIP_SECRET_CHECK=1 git commit ...        # one-off bypass
 *
 * Enable the hook once per clone:
 *   git config core.hooksPath .githooks
 */

import { execFileSync } from "node:child_process";
import { readFileSync, statSync, readdirSync } from "node:fs";
import { join, relative, sep } from "node:path";

const ALL = process.argv.includes("--all");
const root = execFileSync("git", ["rev-parse", "--show-toplevel"], { encoding: "utf8" }).trim();
const git = (args) => execFileSync("git", args, { cwd: root, encoding: "utf8" });

const tracked = new Set(git(["ls-files"]).split("\n").filter(Boolean));
const targets = ALL
  ? [...tracked]
  : git(["diff", "--cached", "--name-only", "--diff-filter=ACM"]).split("\n").filter(Boolean);

const SKIP_DIR = /(^|[\\/])(node_modules|\.venv|\.next|\.git|_tmp|pgdata|minio-data)([\\/]|$)/;
const SKIP_FILE = /(^|[\\/])(uv\.lock|pnpm-lock\.yaml|package-lock\.json)$|\.(pdf|png|jpe?g|gif|ico|woff2?|zip|gz|mp4)$/i;

const SECRET_NAME = /(SECRET|PASSWORD|PASSKEY|PASSPHRASE|TOKEN|API_KEY|APIKEY|CONSUMER|CREDENTIAL|ENCRYPTION|PRIVATE)/;
const PLACEHOLDER = /replace|change_?me|your[_-]|example|placeholder|dummy|sample|xxx|<[^>]*>|\.\.\.|todo/i;
const BENIGN = /^(localhost|127\.0\.0\.1|admin|postgres|sandbox|development|production|internal|true|false|aifya|aifya_user|aifya_app|minioadmin|aifya-dev-key|aifya_dev_password|dev_only_replace_with_openssl_rand_hex_32|aifya_minio_dev_secret|aifya_scribe_dev_jwt_secret|keycloak)$/i;
const LITERAL = /^[A-Za-z0-9_\-.:\/+=]{12,}$/;
const DEV_DEFAULT = /(^|_)(dev|local|test|ci|dummy)(_|$)/i;
const PATH_LIKE = /^[.~\/]|[\/]{2}|\/\/[^\s]*|\.(pem|key|crt|json|txt|env|p12|pfx)$/i;
const TOKEN = /(sk-ant-[A-Za-z0-9_\-]{20,}|sk-[A-Za-z0-9]{32,}|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{30,}|xox[baprs]-[A-Za-z0-9\-]{10,}|AIza[0-9A-Za-z_\-]{30,})/;
const PRIVATE_KEY = /-----BEGIN [A-Z ]*PRIVATE KEY-----/;

/** "0123456789abcdef" repeated 4x is a test dummy, not a secret. */
function isRepeated(v) {
  for (let n = 1; n <= 16; n++) {
    if (v.length % n) continue;
    if (v.slice(0, n).repeat(v.length / n) === v) return true;
  }
  return false;
}
function isInteresting(key, value) {
  if (!value || value.length < 12) return false;
  if (!SECRET_NAME.test(key)) return false;
  if (PLACEHOLDER.test(value) || BENIGN.test(value)) return false;
  if (DEV_DEFAULT.test(value) || PATH_LIKE.test(value)) return false;
  if (isRepeated(value)) return false;
  if (!LITERAL.test(value)) return false;
  return true;
}

/** High confidence only: a literal with both letters and digits. */
function isHighConfidence(key, value) {
  return isInteresting(key, value) && /[0-9]/.test(value) && /[A-Za-z]/.test(value);
}

// ---- values that live in ignored .env files (the actual secrets) ----
const liveValues = new Map();
function scanEnvFile(abs) {
  let text; try { text = readFileSync(abs, "utf8"); } catch { return; }
  for (const line of text.split(/\r?\n/)) {
    const m = line.match(/^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(\S+)\s*$/);
    if (m && isInteresting(m[1], m[2])) liveValues.set(m[2], m[1]);
  }
}
(function walk(dir) {
  let entries = []; try { entries = readdirSync(dir, { withFileTypes: true }); } catch { return; }
  for (const e of entries) {
    const abs = join(dir, e.name);
    if (SKIP_DIR.test(abs)) continue;
    if (e.isDirectory()) { walk(abs); continue; }
    const rel = relative(root, abs).split(sep).join("/");
    if (/^\.env/.test(e.name) && !tracked.has(rel)) scanEnvFile(abs);
  }
})(root);

// ---- scan ----
const findings = [];
function add(rel, line, what, sample) { findings.push({ rel, line, what, sample }); }
function redact(v) { return v.slice(0, 4) + "…(" + v.length + " chars)"; }

for (const rel of targets) {
  if (SKIP_FILE.test(rel)) continue;
  const abs = join(root, rel);
  let size = 0; try { size = statSync(abs).size; } catch { continue; }
  if (size > 1_500_000) continue;
  let text; try { text = readFileSync(abs, "utf8"); } catch { continue; }
  if (text.slice(0, 8192).includes("\u0000")) continue;

  const lines = text.split(/\r?\n/);
  lines.forEach((line, i) => {
    const ln = i + 1;
    if (line.length > 2000) line = line.slice(0, 2000);
    if (PRIVATE_KEY.test(line)) { add(rel, ln, "private key block", "<redacted>"); return; }
    const tok = line.match(TOKEN);
    if (tok) { add(rel, ln, "token-shaped value", redact(tok[1])); return; }
    for (const [v, k] of liveValues) {
      if (line.includes(v)) { add(rel, ln, "matches live .env value of " + k, redact(v)); break; }
    }
    const m = line.match(/^\s*(?:export\s+|-\s+)?([A-Z][A-Z0-9_]{2,})\s*[:=]\s*(\S+)\s*$/);
    if (m && isHighConfidence(m[1], m[2])) add(rel, ln, m[1] + " = literal secret", redact(m[2]));
  });
}

if (findings.length === 0) {
  console.log("check-secrets: clean - checked " + targets.length + (ALL ? " tracked files" : " staged file(s)") + ".");
  process.exit(0);
}
console.error("\ncheck-secrets: BLOCKED - possible secret" + (findings.length > 1 ? "s" : "") + " in this commit\n");
for (const f of findings) console.error("  " + f.rel + ":" + f.line + "  [" + f.what + "]  " + f.sample);
console.error("\nReal secrets belong in .env (gitignored); templates must use placeholders.");
console.error("Bypass once with: SKIP_SECRET_CHECK=1 git commit ...\n");
process.exit(1);
