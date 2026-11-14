import { VIEWS, requireAuth, sb } from "./_lib.js";

const FIELDS = [
  "id", "source", "company", "title", "locations", "url", "terms", "tier", "verdict",
  "judgment", "description_status", "first_seen", "posted_at", "posted_approx", "active", "baseline",
  "user_status", "feedback_kind", "feedback_reason", "feedback_at", "applied_at",
].join(",");


export default async function handler(req, res) {
  if (!requireAuth(req, res)) return;
  const view = VIEWS[req.query.view] ? req.query.view : "matches";
  const limit = view === "skipped" ? 300 : 1000;
  try {
    const rows = await sb(
      `postings?select=${FIELDS}&${VIEWS[view]}&source=neq.legacy&order=first_seen.desc&limit=${limit}`,
    );
    res.setHeader("Cache-Control", "no-store");
    res.status(200).json({ view, rows });
  } catch (e) {
    res.status(500).json({ error: String(e.message || e) });
  }
}
