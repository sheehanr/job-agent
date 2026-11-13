"""python -m tracker  - one run of the job tracker."""

import json
import sys
import time

from tracker import config, pipeline


def main():

    t0 = time.time()

    def log(msg):
        print(f"[{time.time() - t0:6.0f}s] {msg}", flush=True)

    cfg = config.load()
    summary = pipeline.run(cfg, log)
    print(json.dumps(summary, indent=2, default=str))

    errors = summary.get("source_errors") or {}
    if errors:
        print(f"\n{len(errors)} source(s) failed:")
        for name, err in errors.items():
            print(f"  {name}: {err}")


if __name__ == "__main__":
    sys.exit(main())
