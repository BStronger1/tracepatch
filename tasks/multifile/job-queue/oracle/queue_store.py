from collections import deque
from dataclasses import dataclass


@dataclass
class Job:
    job_id: str
    payload: dict
    attempts: int = 0
    state: str = 'pending'


class Queue:
    def __init__(self):
        self.jobs = {}
        self.pending = deque()

    def enqueue(self, job_id, payload):
        if job_id in self.jobs:
            return False
        job = Job(job_id, dict(payload))
        self.jobs[job_id] = job
        self.pending.append(job)
        return True

    def take(self):
        if not self.pending:
            return None
        job = self.pending.popleft()
        job.state = 'running'
        return job

    def _require_running(self, job):
        if self.jobs.get(job.job_id) is not job or job.state != 'running':
            raise ValueError('expected the stored running job')

    def retry(self, job):
        self._require_running(job)
        job.state = 'pending'
        self.pending.append(job)

    def finish(self, job, state):
        self._require_running(job)
        if state not in ('done', 'failed'):
            raise ValueError('invalid terminal state')
        job.state = state
