import { VIEWS, count, requireAuth } from "./_lib.js";

// How many postings each tab holds, so every tab shows its number on load.
export default async function handler(req, res) {
  if (!requireAuth(req, res)) return;
  try {
    const names = Object.keys(VIEWS);
    const totals = await Promise.all(names.map(count));
    res.setHeader("Cache-Control", "no-store");
    res.status(200).json(Object.fromEntries(names.map((n, i) => [n, totals[i]])));
  } catch (e) {
    res.status(500).json({ error: String(e.message || e) });
  }
}
