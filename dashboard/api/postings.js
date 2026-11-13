import { requireAuth, sb } from "./_lib.js";

const FIELDS = [
  "id", "source", "company", "title", "locations", "url", "terms", "tier", "verdict",
  "judgment", "description_status", "first_seen", "posted_at", "posted_approx", "active", "baseline",
  "user_status", "feedback_kind", "feedback_reason", "feedback_at", "applied_at",
].join(",");

const VIEWS = {
  matches: "status=eq.judged&verdict=eq.alert&user_status=is.null",
  maybe: "status=eq.judged&verdict=eq.maybe&user_status=is.null",
  applied: "user_status=eq.applied",
  not_fit: "user_status=eq.not_fit",
  skipped: "status=eq.judged&verdict=eq.skip&user_status=is.null",
};

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
