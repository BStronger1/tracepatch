from config import Settings
from queue_store import Queue
from worker import Worker

queue = Queue()
assert queue.enqueue('a', {'value': 1})
seen = []
worker = Worker(queue, Settings({}), lambda payload: seen.append(payload['value']))
assert worker.run_one() is True
assert worker.run_one() is False
assert seen == [1]
assert queue.jobs['a'].state == 'done'

queue = Queue()
queue.enqueue('retry', {})
def transient(payload):
    raise TimeoutError('temporary')
worker = Worker(queue, Settings({'max_attempts': 2}), transient)
worker.run_one()
assert queue.jobs['retry'].state == 'pending', 'a timeout should be retried'
print('visible tests passed')
