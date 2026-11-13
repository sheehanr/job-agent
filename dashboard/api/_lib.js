// Shared helpers for the dashboard's server functions. Every function
// talks to Supabase with the secret key (server-side only); the browser
// never sees it.
import crypto from "node:crypto";

const SUPABASE_URL = (process.env.SUPABASE_URL || "").replace(/\/$/, "");
const SECRET_KEY = process.env.SUPABASE_SECRET_KEY || "";

export async function sb(path, { method = "GET", body, prefer } = {}) {
  const headers = {
    apikey: SECRET_KEY,
    Authorization: `Bearer ${SECRET_KEY}`,
    "Content-Type": "application/json",
  };
  if (prefer) headers.Prefer = prefer;
  const r = await fetch(`${SUPABASE_URL}/rest/v1/${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const text = await r.text();
  if (!r.ok) throw new Error(`Supabase ${r.status}: ${text.slice(0, 300)}`);
  return text ? JSON.parse(text) : null;
}

// ---- session: one password, a signed cookie that lasts a year ----

const COOKIE = "ja_session";

function sessionToken() {
  const pw = process.env.DASHBOARD_PASSWORD || "";
  return crypto.createHmac("sha256", pw).update("job-agent-session-v1").digest("hex");
}

function safeEqual(a, b) {
  const x = Buffer.from(String(a));
  const y = Buffer.from(String(b));
  return x.length === y.length && crypto.timingSafeEqual(x, y);
}

export function checkPassword(pw) {
  return Boolean(process.env.DASHBOARD_PASSWORD) && safeEqual(pw || "", process.env.DASHBOARD_PASSWORD);
}

export function setSession(res) {
  res.setHeader(
    "Set-Cookie",
    `${COOKIE}=${sessionToken()}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=31536000`,
  );
}

export function clearSession(res) {
  res.setHeader("Set-Cookie", `${COOKIE}=; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=0`);
}

export function authed(req) {
  const cookies = Object.fromEntries(
    (req.headers.cookie || "").split(";").map((c) => c.trim().split("=")).filter((p) => p[0]),
  );
  return Boolean(process.env.DASHBOARD_PASSWORD) && safeEqual(cookies[COOKIE] || "", sessionToken());
}

export function requireAuth(req, res) {
  if (authed(req)) return true;
  res.status(401).json({ error: "Not signed in" });
  return false;
}

// ---- ntfy feedback buttons: same signature as tracker/notify.py ----

export function feedbackSig(ids, kind) {
  const msg = `${[...ids].sort((a, b) => a - b).join(",")}:${kind}`;
  return crypto
    .createHmac("sha256", process.env.FEEDBACK_SECRET || "")
    .update(msg)
    .digest("hex")
    .slice(0, 32);
}

export function idList(ids) {
  const list = (Array.isArray(ids) ? ids : String(ids || "").split(","))
    .map((x) => parseInt(x, 10))
    .filter((x) => Number.isInteger(x) && x > 0);
  return [...new Set(list)].slice(0, 200);
}

export async function setFeedback(ids, action, { kind = null, reason = null } = {}) {
  const now = new Date().toISOString();
  let patch;
  if (action === "applied") {
    patch = { user_status: "applied", applied_at: now };
  } else if (action === "not_fit") {
    patch = { user_status: "not_fit", feedback_kind: kind, feedback_reason: reason, feedback_at: now };
  } else if (action === "reason") {
    patch = { feedback_reason: reason };
  } else if (action === "undo") {
    patch = { user_status: null, feedback_kind: null, feedback_reason: null, feedback_at: null, applied_at: null };
  } else {
    throw new Error("Unknown action");
  }
  return sb(`postings?id=in.(${ids.join(",")})`, {
    method: "PATCH",
    body: patch,
    prefer: "return=representation",
  });
}
