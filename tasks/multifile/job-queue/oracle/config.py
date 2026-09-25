class Settings:
    def __init__(self, raw):
        value = raw.get('max_attempts', 3)
        if type(value) is not int or value < 1:
            raise ValueError('max_attempts must be a positive integer')
        self.max_attempts = value
