class MemoryPAError(Exception):
    status = "error"


class Conflict(MemoryPAError):
    status = "conflict"


class ReviewRequired(MemoryPAError):
    status = "review_required"

    def __init__(self, message, candidates=()):
        super().__init__(message)
        self.candidates = list(candidates)


class UncertainWrite(MemoryPAError):
    status = "uncertain_write"
