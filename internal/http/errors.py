class APIError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


class BadRequestError(APIError):
    def __init__(self, message: str):
        super().__init__(400, message)


class UpstreamError(APIError):
    def __init__(self, message: str):
        super().__init__(502, message)
