"""
Compare AI models on postings the tracker has already judged.

    python scripts/compare_models.py gemini-3.5-flash-lite [gemini-3.8-flash] [--n 60]

Re-judges a sample of stored postings (using their saved descriptions) with
each model and prints how often each agrees with the current verdicts, the
disagreements, and the token cost. Also checks a few hand-labelled cases
where the right answer is known.
"""

import argparse
import concurrent.futures as cf
import random
import sys

sys.path.insert(0, __import__("os").path.dirname(__file__) + "/..")

from tracker import config, db, rules  # noqa: E402
from tracker.ai import Judge  # noqa: E402

# (company, title substring, expected verdict) - known right answers.
KNOWN = [
    ("Microsoft", "Data Scientist Intern - CoreAI", "skip"),      # full-time role mislabeled
    ("Microsoft", "Research Intern", "skip"),                      # PhD only
    ("Meta", "Research Scientist Intern", "skip"),                 # PhD program
    ("Philips", "Insights and Analytics Intern", "skip"),          # marketing analytics
]

# Gemini prices per 1M tokens (input, output incl. thinking), Nov 2026.
PRICES = {"gemini-3.5-flash-lite": (0.30, 2.50), "gemini-3.8-flash": (0.75, 3.75),
          "gemini-3.6-flash": (0.75, 3.75)}


def sample(conn, n):
    rows = db.rows(conn, """
        select * from postings where status = 'judged' and source <> 'legacy'
          and description_status = 'ok'""")
    random.seed(7)
    by_verdict = {}
    for r in rows:
        by_verdict.setdefault(r["verdict"], []).append(r)
    picked = []
    for verdict, items in by_verdict.items():
        picked += random.sample(items, min(len(items), n // 3))
    return picked


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("models", nargs="+")
    ap.add_argument("--n", type=int, default=60)
    args = ap.parse_args()

    cfg = config.load()
    with db.connect() as conn:
        postings = sample(conn, args.n)
        known = []
        for company, title, expected in KNOWN:
            row = conn.execute("select * from postings where company = %s and title ilike %s "
                               "and description is not null limit 1",
                               (company, f"%{title}%")).fetchone()
            if row:
                known.append((row, expected))

    print(f"{len(postings)} sampled postings, {len(known)} known cases\n")

    for model in args.models:
        cfg.settings["ai"] = {**cfg.settings.get("ai", {}), "model": model}
        judge = Judge(cfg)

        def run(p):
            j = judge.judge(p)
            return p, rules.final_verdict(p, j, cfg)[0]

        with cf.ThreadPoolExecutor(8) as ex:
            results = list(ex.map(run, postings))
            known_results = list(ex.map(lambda k: (run(k[0])[1], k[1], k[0]), known))

        agree = sum(1 for p, v in results if v == p["verdict"])
        print(f"== {model}: agrees with stored verdicts on {agree}/{len(results)}")
        for p, v in results:
            if v != p["verdict"]:
                print(f"   {p['company']}: {p['title'][:60]}  stored={p['verdict']} new={v}")
        right = sum(1 for got, want, _ in known_results if got == want)
        print(f"   known cases right: {right}/{len(known_results)}")
        for got, want, p in known_results:
            if got != want:
                print(f"   WRONG {p['company']}: {p['title'][:60]} got={got} want={want}")
        price = PRICES.get(model)
        if price:
            u = judge.usage
            cost = (u["input"] * price[0] + (u["output"] + u["thinking"]) * price[1]) / 1e6
            per = cost / max(1, u["calls"])
            print(f"   tokens in/out/thinking {u['input']}/{u['output']}/{u['thinking']}; "
                  f"${cost:.3f} total, ${per * 1000:.2f} per 1,000 postings\n")


if __name__ == "__main__":
    main()
