"""Stable errors without exception text from providers."""


class DemoError(Exception):
    def __init__(self, code: str, status: int = 400):
        super().__init__(code)
        self.code = code
        self.status = status
