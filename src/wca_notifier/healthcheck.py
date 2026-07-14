from __future__ import annotations

import os
import time
from pathlib import Path

HEARTBEAT_PATH = Path("/tmp/wca-monitor-heartbeat")


def main() -> None:
    poll_interval = int(os.getenv("POLL_INTERVAL_SECONDS", "3600"))
    maximum_age = poll_interval * 2 + 300
    if not HEARTBEAT_PATH.exists():
        raise SystemExit("monitor has not completed its first cycle")
    age = time.time() - HEARTBEAT_PATH.stat().st_mtime
    if age > maximum_age:
        raise SystemExit(f"monitor heartbeat is stale ({int(age)} seconds)")


if __name__ == "__main__":
    main()
