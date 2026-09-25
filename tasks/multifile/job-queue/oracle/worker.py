class Worker:
    def __init__(self, queue, settings, handler):
        self.queue, self.settings, self.handler = queue, settings, handler

    def run_one(self):
        job = self.queue.take()
        if job is None:
            return False
        job.attempts += 1
        try:
            self.handler(job.payload)
        except TimeoutError:
            if job.attempts < self.settings.max_attempts:
                self.queue.retry(job)
            else:
                self.queue.finish(job, 'failed')
        except Exception:
            self.queue.finish(job, 'failed')
            raise
        else:
            self.queue.finish(job, 'done')
        return True
