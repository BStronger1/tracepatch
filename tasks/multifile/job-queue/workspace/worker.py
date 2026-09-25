class Worker:
    def __init__(self, queue, settings, handler):
        self.queue, self.settings, self.handler = queue, settings, handler

    def run_one(self):
        job = self.queue.take()
        if job is None:
            return False
        try:
            self.handler(job.payload)
        except Exception:
            self.queue.finish(job, 'failed')
        else:
            self.queue.finish(job, 'done')
        return True
