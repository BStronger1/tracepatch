class Settings:
    def __init__(self, raw):
        self.max_attempts = int(raw.get('max_attempts') or 3)
