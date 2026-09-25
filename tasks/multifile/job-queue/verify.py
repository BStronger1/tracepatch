"""Independent contract checks; never copied into the agent workspace."""
import unittest
from config import Settings
from queue_store import Queue, Job
from worker import Worker


class ContractTests(unittest.TestCase):
    def test_settings(self):
        self.assertEqual(Settings({}).max_attempts, 3)
        self.assertEqual(Settings({'max_attempts': 1}).max_attempts, 1)
        for value in (0, -1, True, False, '2', 1.5, None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                Settings({'max_attempts': value})

    def test_duplicate_and_payload_copy(self):
        q = Queue()
        payload = {'x': 1}
        self.assertIs(q.enqueue('a', payload), True)
        payload['x'] = 99
        self.assertIs(q.enqueue('a', {'x': 2}), False)
        job = q.take()
        self.assertEqual(job.payload, {'x': 1})
        self.assertEqual(job.attempts, 0)
        self.assertIs(q.enqueue('a', {}), False)
        q.finish(job, 'done')
        self.assertIs(q.enqueue('a', {}), False)
        self.assertIsNone(q.take())

    def test_retry_fifo_and_no_duplicate(self):
        q = Queue()
        q.enqueue('a', {})
        q.enqueue('b', {})
        a = q.take()
        q.retry(a)
        with self.assertRaises(ValueError):
            q.retry(a)
        self.assertEqual(q.take().job_id, 'b')
        self.assertIs(q.take(), a)
        self.assertIsNone(q.take())

    def test_invalid_transition_is_atomic(self):
        q = Queue()
        q.enqueue('a', {})
        job = q.jobs['a']
        for action in (lambda: q.finish(job, 'done'), lambda: q.retry(job)):
            with self.assertRaises(ValueError):
                action()
            self.assertEqual(job.state, 'pending')
        self.assertIs(q.take(), job)
        with self.assertRaises(ValueError):
            q.finish(job, 'unknown')
        self.assertEqual(job.state, 'running')
        fake = Job('a', {}, state='running')
        for action in (lambda: q.retry(fake), lambda: q.finish(fake, 'done')):
            with self.assertRaises(ValueError):
                action()
        q.finish(job, 'done')
        with self.assertRaises(ValueError):
            q.finish(job, 'failed')
        self.assertEqual(job.state, 'done')
        self.assertIsNone(q.take())

    def test_success_falsey_and_empty(self):
        for result in (None, False, 0):
            q = Queue()
            q.enqueue('a', {})
            w = Worker(q, Settings({}), lambda p: result)
            self.assertIs(w.run_one(), True)
            self.assertEqual((q.jobs['a'].state, q.jobs['a'].attempts), ('done', 1))
            self.assertIs(w.run_one(), False)

    def test_retry_exhaustion(self):
        for limit in (1, 2, 3):
            q = Queue()
            q.enqueue('a', {})
            calls = []
            def fail(p):
                calls.append(1)
                raise TimeoutError('temporary')
            w = Worker(q, Settings({'max_attempts': limit}), fail)
            for _ in range(limit):
                self.assertIs(w.run_one(), True)
            self.assertIs(w.run_one(), False)
            self.assertEqual(len(calls), limit)
            self.assertEqual((q.jobs['a'].state, q.jobs['a'].attempts), ('failed', limit))

    def test_eventual_success_fairness(self):
        q = Queue()
        q.enqueue('a', {'id': 'a'})
        q.enqueue('b', {'id': 'b'})
        seen = []
        def handle(p):
            seen.append(p['id'])
            if len(seen) == 1:
                raise TimeoutError()
        w = Worker(q, Settings({}), handle)
        for _ in range(3):
            self.assertIs(w.run_one(), True)
        self.assertEqual(seen, ['a', 'b', 'a'])
        self.assertEqual((q.jobs['a'].attempts, q.jobs['b'].attempts), (2, 1))
        self.assertTrue(all(j.state == 'done' for j in q.jobs.values()))
        self.assertIs(w.run_one(), False)

    def test_permanent_error_identity(self):
        q = Queue()
        q.enqueue('a', {})
        error = LookupError('permanent')
        def fail(p):
            raise error
        w = Worker(q, Settings({}), fail)
        with self.assertRaises(LookupError) as caught:
            w.run_one()
        self.assertIs(caught.exception, error)
        self.assertEqual((q.jobs['a'].state, q.jobs['a'].attempts), ('failed', 1))
        self.assertIs(w.run_one(), False)


if __name__ == '__main__':
    unittest.main(verbosity=2)
