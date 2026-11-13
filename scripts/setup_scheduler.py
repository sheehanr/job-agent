"""
Have Supabase start the GitHub workflow every 30 minutes (pg_cron + pg_net).
GitHub's own cron is best-effort and often hours late; a request from
Supabase starts the run within seconds.

    GH_DISPATCH_TOKEN=... python scripts/setup_scheduler.py owner/repo [minutes]

The token is a fine-grained GitHub token limited to this repo with
"Actions: read and write". It's stored encrypted in Supabase Vault.
"""

import sys

sys.path.insert(0, __import__("os").path.dirname(__file__) + "/..")

from tracker import db  # noqa: E402
from tracker.config import env  # noqa: E402

JOB = "job-agent-dispatch"


def main(repo, minutes=30):

    token = env("GH_DISPATCH_TOKEN", required=True)
    url = f"https://api.github.com/repos/{repo}/actions/workflows/run.yml/dispatches"

    with db.connect() as conn:
        conn.execute("create extension if not exists pg_cron")
        conn.execute("create extension if not exists pg_net")

        existing = conn.execute(
            "select id from vault.secrets where name = 'gh_dispatch_token'").fetchone()
        if existing:
            conn.execute("select vault.update_secret(%s, %s)", (existing["id"], token))
        else:
            conn.execute("select vault.create_secret(%s, 'gh_dispatch_token')", (token,))

        conn.execute("select cron.unschedule(jobid) from cron.job where jobname = %s", (JOB,))
        command = f"""
            select net.http_post(
              url := '{url}',
              headers := jsonb_build_object(
                'Authorization', 'Bearer ' || (select decrypted_secret from vault.decrypted_secrets
                                               where name = 'gh_dispatch_token'),
                'Accept', 'application/vnd.github+json',
                'User-Agent', 'job-agent-scheduler',
                'Content-Type', 'application/json'),
              body := '{{"ref": "main"}}'::jsonb)
        """
        conn.execute("select cron.schedule(%s, %s, %s)", (JOB, f"*/{minutes} * * * *", command))

    print(f"Scheduled {repo} every {minutes} minutes.")


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 30)
