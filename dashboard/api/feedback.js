// Called by the "Not interested" buttons on ntfy notifications. Authenticated
// by an HMAC signature in the link instead of the dashboard cookie.
import crypto from "node:crypto";
import { feedbackSig, idList, setFeedback } from "./_lib.js";

export default async function handler(req, res) {
  const ids = idList(req.query.ids);
  const kind = req.query.kind === "company" ? "company" : "role";
  const sig = String(req.query.sig || "");
  const expected = feedbackSig(ids, kind);
  const ok =
    ids.length &&
    process.env.FEEDBACK_SECRET &&
    sig.length === expected.length &&
    crypto.timingSafeEqual(Buffer.from(sig), Buffer.from(expected));
  if (!ok) return res.status(403).send("Bad signature");
  try {
    await setFeedback(ids, "not_fit", { kind });
    res.status(200).send("Marked as not a fit. Undo it on the dashboard.");
  } catch (e) {
    res.status(500).send("Couldn't save feedback");
  }
}
