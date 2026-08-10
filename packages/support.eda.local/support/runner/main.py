"""Minimal poll loop for the support monitor Deployment image."""

from __future__ import annotations

import logging
import os
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("support.runner")

POLL_INTERVAL = int(os.environ.get("SUPPORT_POLL_INTERVAL", "60"))


def main() -> None:
    logger.info(
        "EDA support monitor starting (poll_interval=%ss, config=%s)",
        POLL_INTERVAL,
        os.environ.get("SUPPORT_CONFIG", "/config/default_rules.yaml"),
    )
    # State intent handles alarm polling when SupportMonitor CR is reconciled by EDA.
    # This container keeps the Deployment alive and logs readiness for kubectl probes.
    while True:
        logger.debug("support monitor heartbeat")
        time.sleep(max(10, POLL_INTERVAL))


if __name__ == "__main__":
    main()
