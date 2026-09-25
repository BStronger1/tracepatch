# Job queue contract

This is a small in-memory worker, not a concurrent or persistent queue.

- Settings(raw).max_attempts defaults to 3 only if the key is absent. An explicitly
  supplied value must be a positive int, excluding bool; otherwise raise ValueError.
- Queue.enqueue(job_id, payload) returns True once per id for the queue's lifetime,
  False for duplicate ids (including running/completed jobs). Duplicate enqueue must
  not replace the original payload. Payload is a flat dict: copy it on enqueue.
- Queue.take() returns the next pending Job or None in FIFO order and marks it running.
- Queue.retry(job) marks that running job pending and puts it at the TAIL, once.
  Queue.finish(job, state) accepts done or failed. Both methods raise ValueError
  unless the exact stored Job is currently running. Invalid operations must not
  modify state. Job fields are job_id, payload, attempts (initially 0), state.
- Worker(queue, settings, handler).run_one() returns False if empty, otherwise True
  after a handled job. Increment attempts once before invoking handler(payload).
  On success mark done, including when the result is None or False.
  On TimeoutError, retry if attempts < max_attempts, otherwise mark failed; return True.
  On any other Exception mark failed and re-raise the SAME exception object.
  Failed/done jobs must not run again. A retry must not jump ahead of other pending jobs.

Public fields queue.jobs and Job fields must remain inspectable. Preserve signatures.
No sleep, network, external libraries or asynchronous execution is required.
