def retry_call(fn, attempts):
    for _ in range(attempts):
        try:
            return fn()
        except Exception:
            pass
    return None
