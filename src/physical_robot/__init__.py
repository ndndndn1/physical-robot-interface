"""Vendor-neutral physical robot contracts and deterministic mock runtime."""

from physical_robot.contracts import (
    CommandRecord,
    CommandRequest,
    CommandStatus,
    CommandType,
    RobotState,
)
from physical_robot.products import ProductProfile, product_catalog

__all__ = [
    "CommandRecord",
    "CommandRequest",
    "CommandStatus",
    "CommandType",
    "ProductProfile",
    "RobotState",
    "product_catalog",
]

