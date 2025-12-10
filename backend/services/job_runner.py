import logging
import threading
import time
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
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
    """Simple background job runner backed by ThreadPoolExecutor."""

    def __init__(self, max_workers: int = 2):
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="job")
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

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
        }
        with self._lock:
            self._jobs[job_id] = job_record
        future = self._executor.submit(self._run_job, job_id, func)
        with self._lock:
            self._jobs[job_id]["_future"] = future
        return job_id

    def list_jobs(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [self._public_view(job) for job in self._jobs.values()]

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            job = self._jobs.get(job_id)
            return self._public_view(job) if job else None

    def wait_for(self, job_id: str, timeout: float = 10.0) -> Optional[Dict[str, Any]]:
        future: Optional[Future[Any]] = None
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                future = job.get("_future")
        if future:
            future.result(timeout=timeout)
        return self.get_job(job_id)

    def _run_job(self, job_id: str, func: Callable[[str, Dict[str, Any]], Any]):
        with self._lock:
            job = self._jobs.get(job_id, {})
            job["status"] = "running"
            job["startedAt"] = time.time()
        try:
            result = func(job_id, job.get("metadata", {}))
            with self._lock:
                job = self._jobs.get(job_id, {})
                job["status"] = "finished"
                job["finishedAt"] = time.time()
                job["result"] = result
            job_logger.info("Job %s (%s) finished", job_id, job.get("type"))
        except Exception as exc:  # pragma: no cover - defensive logging
            with self._lock:
                job = self._jobs.get(job_id, {})
                job["status"] = "failed"
                job["finishedAt"] = time.time()
                job["error"] = str(exc)
            job_logger.exception("Job %s failed", job_id)

    @staticmethod
    def _public_view(job: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not job:
            return None
        return {k: v for k, v in job.items() if k != "_future"}


job_runner = JobRunner()
