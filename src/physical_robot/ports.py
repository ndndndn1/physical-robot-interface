"""Swap boundary implemented by the mock and by future hardware adapters."""

from __future__ import annotations

from typing import Protocol

from physical_robot.contracts import CommandRecord, CommandRequest, HardwareStatePatch, RobotState
from physical_robot.products import ProductProfile


class RobotPort(Protocol):
    def catalog(self) -> tuple[ProductProfile, ...]: ...

    def list_states(self) -> tuple[RobotState, ...]: ...

    def get_state(self, robot_id: str) -> RobotState: ...

    def submit(self, request: CommandRequest) -> CommandRecord: ...

    def get_command(self, command_id: str) -> CommandRecord: ...

    def cancel(self, command_id: str) -> CommandRecord: ...

    def simulate_hardware_state(self, robot_id: str, patch: HardwareStatePatch) -> RobotState: ...

