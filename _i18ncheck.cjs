const fs = require("fs");
const path = require("path");
const base = String.raw`C:\Users\User\OneDrive\Desktop\caro's project\Aifya-main\Aifya-main\apps\web\src\messages`;
function flatten(o, p = "") {
  if (o === null || typeof o !== "object") return [p];
  return Object.entries(o).flatMap(([k, v]) => flatten(v, p ? `${p}.${k}` : k));
}
// duplicate-key scanner copied from locale-keys.test.ts
function findDuplicateKeys(raw) {
  const duplicates = [];
  let index = 0;
  const skipWs = () => { while (index < raw.length && /\s/.test(raw.charAt(index))) index += 1; };
  const readString = () => {
    index += 1; let value = "";
    while (index < raw.length) {
      if (raw[index] === "\\") { value += raw[index + 1]; index += 2; }
      else if (raw[index] === '"') { index += 1; return value; }
      else { value += raw[index]; index += 1; }
    }
    throw new Error("unterminated string");
  };
  const readValue = (pp) => {
    skipWs();
    const c = raw[index];
    if (c === "{") readObject(pp);
    else if (c === "[") readArray(pp);
    else if (c === '"') readString();
    else while (index < raw.length && !/[\s,[\]}]/.test(raw.charAt(index))) index += 1;
  };
  const readObject = (pp) => {
    index += 1; const seen = new Set(); skipWs();
    if (raw[index] === "}") { index += 1; return; }
    for (;;) {
      skipWs();
      const key = readString();
      const kp = [...pp, key];
      if (seen.has(key)) duplicates.push(kp.join("."));
      seen.add(key); skipWs(); index += 1; readValue(kp); skipWs();
      if (raw[index] === ",") { index += 1; continue; }
      index += 1; return;
    }
  };
  const readArray = (pp) => {
    index += 1; skipWs();
    if (raw[index] === "]") { index += 1; return; }
    for (;;) {
      readValue(pp); skipWs();
      if (raw[index] === ",") { index += 1; continue; }
      index += 1; return;
    }
  };
  readValue([]);
  return duplicates;
}
const en = JSON.parse(fs.readFileSync(path.join(base, "en.json"), "utf8"));
const sw = JSON.parse(fs.readFileSync(path.join(base, "sw.json"), "utf8"));
const a = new Set(flatten(en)), b = new Set(flatten(sw));
const missingInSw = [...a].filter((k) => !b.has(k));
const missingInEn = [...b].filter((k) => !a.has(k));
const dupEn = findDuplicateKeys(fs.readFileSync(path.join(base, "en.json"), "utf8"));
const dupSw = findDuplicateKeys(fs.readFileSync(path.join(base, "sw.json"), "utf8"));
console.log(JSON.stringify({
  en: a.size, sw: b.size, missingInSw, missingInEn, dupEn, dupSw,
  usageKeys: [...a].filter((k) => k.includes("usageBilling")).length,
}, null, 1));
