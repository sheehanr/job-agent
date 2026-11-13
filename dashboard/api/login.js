import { checkPassword, clearSession, setSession } from "./_lib.js";

export default async function handler(req, res) {
  if (req.method === "DELETE") {
    clearSession(res);
    return res.status(200).json({ ok: true });
  }
  if (req.method !== "POST") return res.status(405).end();
  // Slow down password guessing.
  await new Promise((r) => setTimeout(r, 400));
  if (!checkPassword((req.body || {}).password)) {
    return res.status(401).json({ error: "Wrong password" });
  }
  setSession(res);
  res.status(200).json({ ok: true });
}
