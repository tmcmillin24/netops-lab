class BackendError(RuntimeError):
    def __init__(self, code, message, status_code=400, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


class UnknownDeviceError(BackendError):
    def __init__(self, hostname):
        super().__init__(
            "unknown_device",
            f"Unknown current lab device: {hostname.upper()}",
            404,
        )


class LabServiceError(BackendError):
    pass
