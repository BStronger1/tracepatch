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
        job = Job(job_id, payload)
        self.jobs[job_id] = job
        self.pending.append(job)
        return True

    def take(self):
        if not self.pending:
            return None
        job = self.pending.popleft()
        job.state = 'running'
        return job

    def retry(self, job):
        job.state = 'pending'
        self.pending.appendleft(job)

    def finish(self, job, state):
        job.state = state
