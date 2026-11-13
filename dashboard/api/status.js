import { requireAuth, sb } from "./_lib.js";

export default async function handler(req, res) {
  if (!requireAuth(req, res)) return;
  try {
    const [runs, coverage] = await Promise.all([
      sb("runs?select=id,started_at,finished_at,summary,error&order=id.desc&limit=12"),
      sb("coverage?select=*&order=direct_postings.desc"),
    ]);
    res.setHeader("Cache-Control", "no-store");
    res.status(200).json({ runs, coverage });
  } catch (e) {
    res.status(500).json({ error: String(e.message || e) });
  }
}
