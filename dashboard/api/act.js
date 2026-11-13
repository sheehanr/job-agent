import { idList, requireAuth, setFeedback } from "./_lib.js";

export default async function handler(req, res) {
  if (!requireAuth(req, res)) return;
  if (req.method !== "POST") return res.status(405).end();
  const { ids, action, kind, reason } = req.body || {};
  const list = idList(ids);
  if (!list.length) return res.status(400).json({ error: "No postings" });
  try {
    const rows = await setFeedback(list, action, {
      kind: kind === "company" ? "company" : kind === "role" ? "role" : null,
      reason: typeof reason === "string" ? reason.slice(0, 500) : null,
    });
    res.status(200).json({ ok: true, updated: rows.length });
  } catch (e) {
    res.status(400).json({ error: String(e.message || e) });
  }
}
