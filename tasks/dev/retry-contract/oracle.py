def retry_call(fn, attempts):
    if type(attempts) is not int or attempts < 1:
        raise ValueError('attempts must be a positive integer')
    for i in range(attempts):
        try:
            return fn()
        except TimeoutError:
            if i == attempts - 1:
                raise
