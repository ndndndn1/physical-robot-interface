"""Stable errors shared by the runtime, API, and clients."""

from __future__ import annotations


class RobotError(Exception):
    def __init__(self, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class NotFoundError(RobotError):
    def __init__(self, resource: str) -> None:
        super().__init__("not_found", f"{resource} was not found", 404)


class ConflictError(RobotError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(code, message, 409)


class CapacityError(RobotError):
    def __init__(self) -> None:
        super().__init__("capacity_exhausted", "bounded command store is full", 503)
