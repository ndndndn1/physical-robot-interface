"""Versioned, vendor-neutral wire contracts.

All timestamps are UTC-aware. ``protective_stop`` is a software command and must
never be represented to an operator as a certified hardware emergency stop.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

CONTRACT_VERSION: Final[Literal["1.0.0"]] = "1.0.0"
Identifier = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")]


class CommandType(StrEnum):
    NAVIGATE = "navigate"
    MANIPULATE = "manipulate"
    PROTECTIVE_STOP = "protective_stop"


class CommandStatus(StrEnum):
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class HardwareSafetyState(StrEnum):
    NORMAL = "normal"
    ESTOP_ENGAGED = "estop_engaged"


class Pose2D(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    x_m: float = Field(ge=-10_000, le=10_000)
    y_m: float = Field(ge=-10_000, le=10_000)
    yaw_rad: float = Field(ge=-3.141593, le=3.141593)
    frame: str = Field(default="map", pattern=r"^[A-Za-z][A-Za-z0-9_/]{0,63}$")


class NavigateAction(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal[CommandType.NAVIGATE] = CommandType.NAVIGATE
    target: Pose2D
    max_speed_mps: float = Field(default=0.5, gt=0, le=2.0)


class ManipulateAction(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal[CommandType.MANIPULATE] = CommandType.MANIPULATE
    joint_positions_rad: tuple[float, ...] = Field(min_length=1, max_length=16)
    max_force_n: float = Field(default=30, gt=0, le=250)


class ProtectiveStopAction(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal[CommandType.PROTECTIVE_STOP] = CommandType.PROTECTIVE_STOP
    reason: str = Field(min_length=1, max_length=256)


RobotAction = Annotated[
    NavigateAction | ManipulateAction | ProtectiveStopAction,
    Field(discriminator="type"),
]


class CommandRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: Literal["1.0.0"] = CONTRACT_VERSION
    command_id: Identifier
    robot_id: Identifier
    issued_at: datetime
    expires_at: datetime
    expected_state_version: int = Field(ge=0)
    action: RobotAction

    @model_validator(mode="after")
    def validate_timestamps(self) -> CommandRequest:
        if self.issued_at.tzinfo is None or self.expires_at.tzinfo is None:
            raise ValueError("issued_at and expires_at must include a UTC offset")
        if self.expires_at <= self.issued_at:
            raise ValueError("expires_at must be later than issued_at")
        return self


class CommandTransition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: CommandStatus
    occurred_at: datetime
    detail: str | None = Field(default=None, max_length=512)


class CommandRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    request: CommandRequest
    status: CommandStatus
    transitions: tuple[CommandTransition, ...]
    updated_at: datetime
    error_code: str | None = None


class RobotState(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: Literal["1.0.0"] = CONTRACT_VERSION
    robot_id: Identifier
    product_id: Identifier
    state_version: int = Field(ge=0)
    observed_at: datetime
    pose: Pose2D
    joint_positions_rad: tuple[float, ...]
    hardware_safety_state: HardwareSafetyState
    software_protective_stop: bool
    active_command_id: Identifier | None = None


class HardwareStatePatch(BaseModel):
    """Test/simulator-only hardware observation, never a software E-stop command."""

    model_config = ConfigDict(extra="forbid")

    hardware_estop_engaged: bool | None = None
    pose: Pose2D | None = None
    joint_positions_rad: list[float] | None = Field(default=None, max_length=16)


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
