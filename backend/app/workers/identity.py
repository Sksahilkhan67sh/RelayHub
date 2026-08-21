"""
Single source of truth for how a worker process identifies itself, so the identity
written to `worker_heartbeats` (app/workers/celery_app.py) and the identity attached
to a claimed `DeliveryJob` (app/modules/delivery/executor.py, via app/workers/tasks.py)
are always the same string for the same process.

Before this existed, `tasks.py` derived a worker_id via `os.uname().nodename` and
`celery_app.py` derived one via `socket.gethostname()` independently -- these agree
on typical Linux hosts but aren't guaranteed to (containers, /etc/hosts overrides,
etc). Any mismatch would silently break the lease-based stuck-job check in
`reconcile_stuck_jobs` (a job's `claimed_by_worker_id` would never match any row in
`worker_heartbeats`), degrading it to the time-only heuristic without any error.
Computing it once, here, removes that failure mode entirely rather than relying on
both call sites staying in sync by convention.
"""

from __future__ import annotations

import os
import socket
from functools import lru_cache


@lru_cache(maxsize=1)
def get_worker_id() -> str:
    """Stable for the lifetime of this process: `<hostname>-<pid>`."""
    return f"{socket.gethostname()}-{os.getpid()}"
