"""Background scheduler for integration sync().

Per docs/ARCHITECTURE.md: a background scheduler calls each configured
integration's sync() on its own sync_interval_seconds. On boot, main.py
schedules every integration that already has saved credentials; whenever
credentials are saved or removed afterwards, main.py calls schedule()/
unschedule() to keep the running jobs in sync.

The admin panel's "Sync now" button (POST /api/integrations/{id}/sync-now)
is handled directly by main.py and runs independently of this schedule —
an on-demand sync never waits for or disturbs the next scheduled tick.
"""
import logging
from typing import Any, Callable

from apscheduler.schedulers.background import BackgroundScheduler

from backend.core.integration_registry import IntegrationRegistry

logger = logging.getLogger(__name__)

_JOB_ID_PREFIX = "lifeboard-integration-sync-"


class IntegrationScheduler:
    def __init__(
        self,
        integration_registry: IntegrationRegistry,
        load_credentials: Callable[[str], dict],
        open_db: Callable[[], Any],
    ):
        """
        load_credentials(integration_id) -> dict, {} if none saved.
        open_db() -> a fresh sqlite3.Connection. Jobs run in APScheduler's
        worker thread pool, and sqlite3 connections must not be shared
        across threads, so a fresh connection is opened and closed on
        every tick (mirrors how /sync-now does it in main.py).
        """
        self._integration_registry = integration_registry
        self._load_credentials = load_credentials
        self._open_db = open_db
        self._scheduler = BackgroundScheduler()

    def start(self) -> None:
        self._scheduler.start()

    def shutdown(self) -> None:
        self._scheduler.shutdown(wait=False)

    def _job_id(self, integration_id: str) -> str:
        return f"{_JOB_ID_PREFIX}{integration_id}"

    def _run_sync(self, integration_id: str) -> None:
        # Must not raise: APScheduler would log a traceback and skip the
        # *next* occurrence of this job too if an exception escaped a
        # run, so every failure mode here is caught defensively even
        # though integration_registry.sync() already catches the
        # integration's own exceptions.
        try:
            credentials = self._load_credentials(integration_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Scheduled sync for %r: failed to load credentials (%s)", integration_id, exc)
            return
        if not credentials:
            return

        try:
            db = self._open_db()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Scheduled sync for %r: failed to open db (%s)", integration_id, exc)
            return
        try:
            self._integration_registry.sync(integration_id, credentials=credentials, db=db)
        finally:
            db.close()

    def schedule(self, integration_id: str, sync_interval_seconds: int) -> None:
        """(Re)schedules an integration's sync() on its own interval.
        Safe to call again for an integration that's already scheduled
        (e.g. credentials re-saved with a new value) — replaces the
        existing job rather than running two in parallel. Does not run
        immediately on call; the first tick fires after one interval
        (manual 'Sync now' is the way to get data right away)."""
        self._scheduler.add_job(
            self._run_sync,
            trigger="interval",
            seconds=sync_interval_seconds,
            args=[integration_id],
            id=self._job_id(integration_id),
            replace_existing=True,
        )

    def unschedule(self, integration_id: str) -> None:
        """Removes the scheduled job for an integration, if any. Safe to
        call for an integration that isn't currently scheduled."""
        self._scheduler.remove_job(self._job_id(integration_id), jobstore=None) if self._has_job(
            integration_id
        ) else None

    def _has_job(self, integration_id: str) -> bool:
        return self._scheduler.get_job(self._job_id(integration_id)) is not None

    def scheduled_integration_ids(self) -> set[str]:
        return {
            job.id[len(_JOB_ID_PREFIX):]
            for job in self._scheduler.get_jobs()
            if job.id.startswith(_JOB_ID_PREFIX)
        }
