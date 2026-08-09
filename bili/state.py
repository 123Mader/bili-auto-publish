import json, os, time

STATUS_PENDING = "pending"
STATUS_PRODUCING = "producing"
STATUS_READY = "ready"
STATUS_UPLOADED = "uploaded"
STATUS_DONE = "done"
STATUS_FAILED = "failed"
MAX_RETRIES = 3

class StateStore:
    def __init__(self, path):
        self.path = path
        self._jobs = {}
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path) as f:
                    self._jobs = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._jobs = {}

    def _save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self._jobs, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    def init_job(self, job_id):
        self._jobs[job_id] = {"job_id": job_id, "status": STATUS_PENDING,
                              "retries": 0, "created": time.time()}
        self._save()
        return self._jobs[job_id]

    def get(self, job_id):
        return self._jobs.get(job_id)

    def set(self, job_id, fields):
        if job_id not in self._jobs:
            self._jobs[job_id] = {"job_id": job_id}
        self._jobs[job_id].update(fields)
        self._save()

    def load_jobs(self):
        return list(self._jobs.values())

    def remove(self, job_id):
        self._jobs.pop(job_id, None)
        self._save()
