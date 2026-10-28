class AppError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


class PermanentProcessingError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(422, "processing_rejected", message)


class RetryableProcessingError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(503, "processing_failed", message)
