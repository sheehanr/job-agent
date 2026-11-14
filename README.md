# Job Agent

> **Built with [Claude Code](https://claude.com/claude-code).** The code in
> this repo was written by Claude (Anthropic's AI coding assistant) from my
> requirements and feedback; I designed what it should do, tested it and
> use it. Commits made by Claude are marked `Co-Authored-By: Claude`.

A personal internship and co-op tracker. Every 30 minutes it checks
[Simplify's internship list](https://github.com/SimplifyJobs/Summer2027-Internships)
and the careers sites of the companies you care about, has an AI read each
new job description against a plain-English profile of what you want, and
sends the good matches to your phone. A small dashboard holds everything it
found, what you've applied to, and what you've ruled out.

- **Fast:** company careers sites are checked directly, so new postings
  usually reach you before they show up on aggregators.
- **Few false positives:** the AI reads the actual description, catching
  PhD-only roles, mislabeled full-time jobs, marketing "analytics" roles and
  postings for the wrong term.
- **Tunable:** describe what you want in `config/profile.md`. Tap
  "Not a fit" on a notification and the filter learns from it.

## How it works

```
Simplify listings ─┐
                   ├─> cheap rules ─> dedupe ─> fetch description ─> AI judge ─> notify
Company sites ─────┘   (US, term,                (job-site APIs)     (Gemini)    (ntfy)
                        tech role,                                       │
                        degree, blocklist)                               v
                                                                Supabase ─> dashboard (Vercel)
```

1. **Collect.** Downloads Simplify's listings (every season) and reads each
   company in `config/companies.yaml` that has a `site`, through that job
   site's public API (Workday, Greenhouse, Lever, Ashby, SmartRecruiters,
   iCIMS, Oracle, Eightfold, SuccessFactors, Jibe, Radancy).
2. **Rules.** Drops anything clearly irrelevant before paying the AI: outside
   the US, not a tech role, graduate-students only, the wrong term, or a
   blocked company.
3. **Dedupe.** A role found on both a company site and Simplify is judged
   once.
4. **AI judge.** Fetches the full job description and has Gemini fill in a
   structured judgment: internship or not, term, undergrad eligibility, US
   location, role fit, company tier, pay, verdict (alert / maybe / skip) and
   a one-line reason. Your settings are then applied to that judgment (for
   example, Summer 2027 roles only count at top-tier companies).
5. **Notify.** Each match becomes an ntfy notification titled
   "Company - Role", with the apply link and location. Tapping it opens the
   posting; the **Not a fit: role** and **Not a fit: company** buttons
   record feedback the AI sees on later runs.
6. **Coverage.** For postings found on company sites, the tracker records
   whether Simplify also listed them and how many hours later, so you can see
   which direct checks are worth keeping.

The first time a source is checked, everything it already lists is saved as
"baseline": judged and shown on the dashboard, but never notified.

## Your settings (`config/`)

| File | What it's for |
|---|---|
| `profile.md` | What you want, in plain English. The AI reads it for every posting. |
| `settings.yaml` | Target terms, AI model, notifications on/off, dashboard link. |
| `companies.yaml` | Companies on your radar, and which ones to check directly. |
| `blocklist.yaml` | Companies that never alert, and kinds of company the AI should skip. |

**Terms.** `target_terms` (e.g. `Fall 2027`) alert at the normal bar.
`top_tier_only_terms` (e.g. `Summer 2027`) alert only at top-tier companies.
Postings with no term listed go through, and the AI reads the dates from the
description.

**Adding a company.** Run

```
python scripts/find_job_site.py "Company Name"
```

It works out which job site the company uses from Simplify's apply links or
by probing the common job-site APIs, and prints the `site:` line to paste
into `companies.yaml`. Companies with custom-built, bot-protected careers
sites (Google, Meta, Apple, Microsoft, Amazon, Tesla, ...) are left without
a `site` and come through Simplify only.

**Shadow mode.** With `notifications.enabled: false`, everything runs and
fills the dashboard, but nothing is pushed to your phone.

## Daily use

- **Phone:** tap a notification to open the posting. If it's wrong, tap
  **Not a fit: role** or **Not a fit: company**.
- **Dashboard:** *Matches* is your inbox, best first. Mark postings
  **Applied** or **Not a fit** (with an optional reason). Every action has an
  **Undo**. *Skipped by AI* shows what the filter turned down and why, so you
  can check it isn't too strict; *Coverage* shows how Simplify compares with
  the direct checks and the status of recent runs.

## Setup (for your own copy)

You need free accounts on GitHub, Supabase, Google Cloud and Vercel, and the
[ntfy](https://ntfy.sh) app on your phone. The AI runs on Gemini through
Google Cloud's Vertex AI; at this volume it costs a few dollars a month.

1. **Fork or copy this repo** and keep it public (GitHub Actions minutes are
   free for public repos). Edit everything in `config/`, including
   `dashboard_url` once you have it.
2. **Supabase:** create a project (region close to US East). From
   *Connect → Session pooler* copy the connection string, and from
   *Project Settings → API Keys* the project URL and secret key.
3. **Google Cloud:** create a project, link billing, enable the
   *Vertex AI API*, create a service account with the
   *Agent Platform User* (`roles/aiplatform.user`) role and download a JSON
   key. Set a budget alert while you're there.
4. **ntfy:** install the app and subscribe to a long random topic name. Treat
   the topic like a password: anyone who knows it can read your alerts.
5. **Local `.env`** (gitignored), for running things from your computer:

   ```
   SUPABASE_URL=https://xxxx.supabase.co
   SUPABASE_SECRET_KEY=sb_secret_...
   SUPABASE_DB_URL=postgresql://postgres.xxxx:password@aws-0-us-east-1.pooler.supabase.com:5432/postgres
   GCP_PROJECT_ID=your-project-id
   NTFY_TOPIC=your-topic
   FEEDBACK_SECRET=any-long-random-string
   DASHBOARD_PASSWORD=a-password-you-choose
   GH_DISPATCH_TOKEN=github_pat_...
   ```

   Put the Google key file next to it as `gcp-key.json` (also gitignored).
6. **Create the tables:** `python scripts/setup_db.py`
7. **GitHub secrets** (*Settings → Secrets and variables → Actions*):
   `SUPABASE_DB_URL`, `GCP_PROJECT_ID`, `GCP_SA_KEY` (the whole JSON key
   file), `NTFY_TOPIC`, `FEEDBACK_SECRET`.
8. **Dashboard:** import the `dashboard/` folder as a Vercel project (no
   build step) and set `SUPABASE_URL`, `SUPABASE_SECRET_KEY`,
   `DASHBOARD_PASSWORD` and `FEEDBACK_SECRET` as environment variables. Put
   its URL in `config/settings.yaml`.
9. **Schedule:** create a fine-grained GitHub token for this repo only, with
   *Actions: read and write*, and run

   ```
   python scripts/setup_scheduler.py your-name/your-repo
   ```

   Supabase then starts the workflow every 30 minutes. (GitHub's own cron is
   kept as a backup, but it often runs hours late.)
10. **Test:** run the *Run tracker* workflow by hand from the Actions tab,
    then open the dashboard. The *Send test notification* workflow pushes
    one real notification to your phone. When you're happy with what it finds, set
    `notifications.enabled: true`.

## Running locally

```
python3.12 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python -m pytest -q        # tests
python -m tracker          # one full run
```

## Project layout

```
config/              your settings (the only folder you need to edit)
tracker/             the tracker: pipeline, rules, AI, notifications
tracker/sources/     one adapter per job site, plus Simplify
dashboard/           the website (static page + Vercel server functions)
db/schema.sql        database tables
scripts/             finding a company's job site, scheduler setup
tests/               unit tests
```
