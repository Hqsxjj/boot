import atexit
import logging
import threading
import time
import uuid
from pathlib import Path
from queue import Queue
from typing import Any, Callable, Dict, List, Optional

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "strm_jobs.log"

job_logger = logging.getLogger("strm.jobs")
if not job_logger.handlers:
    handler = logging.FileHandler(LOG_FILE)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    handler.setFormatter(formatter)
    job_logger.addHandler(handler)
    job_logger.setLevel(logging.INFO)


class JobRunner:
    """Simple job runner backed by a queue and daemon worker threads."""

    def __init__(self, max_workers: int = 2):
        self._queue: "Queue[Optional[tuple[str, Dict[str, Any], Callable[[str, Dict[str, Any]], Any]]]]" = Queue()
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._workers: List[threading.Thread] = []
        self._stopping = False
        for idx in range(max_workers):
            thread = threading.Thread(target=self._worker, name=f"job-{idx}", daemon=True)
            thread.start()
            self._workers.append(thread)

    def submit(
        self,
        job_type: str,
        func: Callable[[str, Dict[str, Any]], Any],
        *,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        job_id = uuid.uuid4().hex
        job_record = {
            "id": job_id,
            "type": job_type,
            "status": "pending",
            "queuedAt": time.time(),
            "startedAt": None,
            "finishedAt": None,
            "metadata": metadata or {},
            "result": None,
            "error": None,
            "event": threading.Event(),
        }
        with self._lock:
            self._jobs[job_id] = job_record
        self._queue.put((job_id, job_record, func))
        return job_id

    def list_jobs(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [self._public_view(job) for job in self._jobs.values()]

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            job = self._jobs.get(job_id)
            return self._public_view(job) if job else None

    def wait_for(self, job_id: str, timeout: float = 10.0) -> Optional[Dict[str, Any]]:
        with self._lock:
            job = self._jobs.get(job_id)
            event = job.get("event") if job else None
        if event:
            event.wait(timeout=timeout)
        return self.get_job(job_id)

    def shutdown(self, wait: bool = False):
        if self._stopping:
            return
        self._stopping = True
        for _ in self._workers:
            self._queue.put(None)
        if wait:
            for worker in self._workers:
                worker.join(timeout=1)

    def _worker(self):
        while True:
            item = self._queue.get()
            if item is None:
                break
            job_id, job_record, func = item
            with self._lock:
                stored = self._jobs.get(job_id, job_record)
                stored["status"] = "running"
                stored["startedAt"] = time.time()
            try:
                result = func(job_id, job_record.get("metadata", {}))
                with self._lock:
                    stored = self._jobs.get(job_id, job_record)
                    stored["status"] = "finished"
                    stored["finishedAt"] = time.time()
                    stored["result"] = result
                job_logger.info("Job %s (%s) finished", job_id, job_record.get("type"))
            except Exception as exc:  # pragma: no cover - defensive logging
                with self._lock:
                    stored = self._jobs.get(job_id, job_record)
                    stored["status"] = "failed"
                    stored["finishedAt"] = time.time()
                    stored["error"] = str(exc)
                job_logger.exception("Job %s failed", job_id)
            finally:
                job_record["event"].set()

    @staticmethod
    def _public_view(job: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not job:
            return None
        filtered = {k: v for k, v in job.items() if k != "event"}
        return filtered


job_runner = JobRunner()
atexit.register(job_runner.shutdown)
