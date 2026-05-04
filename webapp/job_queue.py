"""
In-memory async job queue for SnipGen pipeline runs.

Why in-memory and not Redis/Celery:
  - Render runs a persistent process (unlike Vercel serverless)
  - A single gunicorn/uvicorn worker handles all requests
  - Background threads share the same process memory
  - No external service needed — zero extra cost, zero config

Limitations:
  - Jobs lost on server restart (acceptable — user just re-submits)
  - Not horizontally scalable (fine for research tool traffic)
  - Max ~20 concurrent jobs before RAM pressure on free tier

Job lifecycle:
    queued → running → done
                     → failed
"""

from __future__ import annotations

import threading
import time
import traceback
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class JobStatus(str, Enum):
    QUEUED  = "queued"
    RUNNING = "running"
    DONE    = "done"
    FAILED  = "failed"


@dataclass
class Job:
    job_id:     str
    status:     JobStatus       = JobStatus.QUEUED
    result:     Optional[Any]   = None
    error:      Optional[str]   = None
    progress:   str             = "Queued…"
    created_at: float           = field(default_factory=time.time)
    finished_at: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "job_id":      self.job_id,
            "status":      self.status.value,
            "progress":    self.progress,
            "result":      self.result,
            "error":       self.error,
            "elapsed_s":   round(time.time() - self.created_at, 1),
        }


class JobQueue:
    """Thread-safe in-memory job store with background execution."""

    # Keep finished jobs for 30 minutes then evict
    _JOB_TTL = 1800

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        # Start background janitor to evict old jobs
        t = threading.Thread(target=self._janitor, daemon=True)
        t.start()

    def submit(self, fn, *args, **kwargs) -> str:
        """Submit a callable to run in a background thread. Returns job_id."""
        job_id = uuid.uuid4().hex[:16]
        job = Job(job_id=job_id)
        with self._lock:
            self._jobs[job_id] = job
        t = threading.Thread(target=self._run, args=(job_id, fn, args, kwargs), daemon=True)
        t.start()
        return job_id

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def update_progress(self, job_id: str, msg: str) -> None:
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id].progress = msg

    def _run(self, job_id: str, fn, args, kwargs) -> None:
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id].status   = JobStatus.RUNNING
                self._jobs[job_id].progress = "Running pipeline…"
        try:
            result = fn(*args, **kwargs)
            with self._lock:
                if job_id in self._jobs:
                    self._jobs[job_id].status      = JobStatus.DONE
                    self._jobs[job_id].result      = result
                    self._jobs[job_id].progress    = "Done"
                    self._jobs[job_id].finished_at = time.time()
        except Exception as exc:
            with self._lock:
                if job_id in self._jobs:
                    self._jobs[job_id].status      = JobStatus.FAILED
                    self._jobs[job_id].error       = str(exc)
                    self._jobs[job_id].progress    = f"Failed: {exc}"
                    self._jobs[job_id].finished_at = time.time()
            traceback.print_exc()

    def _janitor(self) -> None:
        """Evict jobs older than TTL every 5 minutes."""
        while True:
            time.sleep(300)
            cutoff = time.time() - self._JOB_TTL
            with self._lock:
                evict = [
                    jid for jid, j in self._jobs.items()
                    if j.finished_at and j.finished_at < cutoff
                ]
                for jid in evict:
                    del self._jobs[jid]


# Module-level singleton — shared across all requests in the same process
queue = JobQueue()
