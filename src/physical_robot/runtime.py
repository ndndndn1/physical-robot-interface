"""Deterministic bounded mock implementation of :class:`RobotPort`."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from datetime import timedelta
from threading import RLock

from physical_robot.clock import Clock, SystemClock
from physical_robot.contracts import (
    CommandRecord,
    CommandRequest,
    CommandStatus,
    CommandTransition,
    CommandType,
    HardwareSafetyState,
    HardwareStatePatch,
    ManipulateAction,
    NavigateAction,
    ProtectiveStopAction,
    RobotState,
)
from physical_robot.errors import CapacityError, ConflictError, NotFoundError
from physical_robot.products import ProductProfile, product_catalog

TERMINAL_STATUSES = frozenset(
    {
        CommandStatus.REJECTED,
        CommandStatus.COMPLETED,
        CommandStatus.FAILED,
        CommandStatus.CANCELLED,
    }
)


@dataclass
class _StoredCommand:
    request: CommandRequest
    status: CommandStatus
    transitions: list[CommandTransition]
    error_code: str | None = None


class MockRobotRuntime:
    """Thread-safe mock fleet with no workers, timers, or unbounded queues.

    Polling a command advances accepted -> running -> completed. This deterministic
    scheduling makes tests reproducible while retaining a real cancellation window.
    """

    def __init__(
        self,
        *,
        clock: Clock | None = None,
        max_commands: int = 1_000,
        terminal_retention: timedelta = timedelta(hours=1),
        products: tuple[ProductProfile, ...] | None = None,
    ) -> None:
        if max_commands < 1:
            raise ValueError("max_commands must be positive")
        if terminal_retention.total_seconds() < 0:
            raise ValueError("terminal_retention cannot be negative")
        self._clock = clock or SystemClock()
        self._max_commands = max_commands
        self._terminal_retention = terminal_retention
        self._products = products or product_catalog()
        self._products_by_id = {product.product_id: product for product in self._products}
        if len(self._products_by_id) != len(self._products):
            raise ValueError("product IDs must be unique")
        self._commands: OrderedDict[str, _StoredCommand] = OrderedDict()
        self._lock = RLock()
        self._states = {
            "mh-01-a": self._initial_state("mh-01-a", "mock-humanoid-mh-01"),
            "mm-01-a": self._initial_state(
                "mm-01-a", "mock-mobile-manipulator-mm-01"
            ),
        }

    def _initial_state(self, robot_id: str, product_id: str) -> RobotState:
        product = self._get_product(product_id)
        if product is None:  # pragma: no cover - catalog is defined in-process
            raise ValueError(f"unknown product {product_id}")
        from physical_robot.contracts import Pose2D

        return RobotState(
            robot_id=robot_id,
            product_id=product_id,
            state_version=0,
            observed_at=self._clock.now(),
            pose=Pose2D(x_m=0, y_m=0, yaw_rad=0),
            joint_positions_rad=tuple(0.0 for _ in range(product.joint_count)),
            hardware_safety_state=HardwareSafetyState.NORMAL,
            software_protective_stop=False,
        )

    def catalog(self) -> tuple[ProductProfile, ...]:
        return self._products

    def list_states(self) -> tuple[RobotState, ...]:
        with self._lock:
            return tuple(self._states.values())

    def get_state(self, robot_id: str) -> RobotState:
        with self._lock:
            try:
                return self._states[robot_id]
            except KeyError as exc:
                raise NotFoundError(f"robot {robot_id}") from exc

    def submit(self, request: CommandRequest) -> CommandRecord:
        with self._lock:
            self._cleanup()
            existing = self._commands.get(request.command_id)
            if existing is not None:
                if existing.request == request:
                    return self._record(existing)
                raise ConflictError(
                    "idempotency_conflict",
                    "command_id already exists with a different payload",
                )

            state = self.get_state(request.robot_id)
            if len(self._commands) >= self._max_commands:
                self._evict_oldest_terminal()
            if len(self._commands) >= self._max_commands:
                raise CapacityError()

            stored = _StoredCommand(
                request=request,
                status=CommandStatus.SUBMITTED,
                transitions=[self._transition(CommandStatus.SUBMITTED)],
            )
            self._commands[request.command_id] = stored
            validation_error = self._validate_submission(request, state)
            if validation_error is not None:
                code, message = validation_error
                self._set_status(stored, CommandStatus.REJECTED, message, code)
                return self._record(stored)

            self._set_status(stored, CommandStatus.ACCEPTED)
            self._states[state.robot_id] = state.model_copy(
                update={
                    "active_command_id": request.command_id,
                    "state_version": state.state_version + 1,
                    "observed_at": self._clock.now(),
                }
            )
            return self._record(stored)

    def _validate_submission(
        self, request: CommandRequest, state: RobotState
    ) -> tuple[str, str] | None:
        now = self._clock.now()
        if request.expires_at <= now:
            return ("expired_command", "command expired before acceptance")
        if request.issued_at > now + timedelta(minutes=5):
            return ("future_command", "issued_at is more than five minutes in the future")
        if request.expected_state_version != state.state_version:
            return ("stale_state", "expected_state_version does not match current state")
        product = self._get_product(state.product_id)
        if product is None or request.action.type not in product.capabilities:
            return ("unsupported_capability", "product does not support this command type")
        if state.active_command_id is not None:
            return ("robot_busy", "robot already has an active command")
        if (
            state.hardware_safety_state is HardwareSafetyState.ESTOP_ENGAGED
            and request.action.type is not CommandType.PROTECTIVE_STOP
        ):
            return ("hardware_estop_engaged", "motion is blocked by the hardware E-stop input")
        if (
            state.software_protective_stop
            and request.action.type is not CommandType.PROTECTIVE_STOP
        ):
            return ("software_protective_stop", "motion is blocked by software protective stop")
        if isinstance(request.action, ManipulateAction) and (
            product is None or len(request.action.joint_positions_rad) != product.joint_count
        ):
            return ("invalid_joint_count", "joint target does not match product profile")
        return None

    def get_command(self, command_id: str) -> CommandRecord:
        with self._lock:
            stored = self._find_command(command_id)
            if stored.status in {CommandStatus.ACCEPTED, CommandStatus.RUNNING}:
                state = self.get_state(stored.request.robot_id)
                if (
                    state.hardware_safety_state is HardwareSafetyState.ESTOP_ENGAGED
                    and stored.request.action.type is not CommandType.PROTECTIVE_STOP
                ):
                    self._finish_failed(stored, "hardware_estop_engaged")
                    return self._record(stored)
            if stored.status is CommandStatus.ACCEPTED:
                self._set_status(stored, CommandStatus.RUNNING)
            elif stored.status is CommandStatus.RUNNING:
                if stored.request.expires_at <= self._clock.now():
                    self._finish_failed(stored, "expired_during_execution")
                else:
                    self._finish_completed(stored)
            return self._record(stored)

    def cancel(self, command_id: str) -> CommandRecord:
        with self._lock:
            stored = self._find_command(command_id)
            if stored.status in TERMINAL_STATUSES:
                raise ConflictError(
                    "command_terminal", f"cannot cancel command in {stored.status} state"
                )
            self._set_status(stored, CommandStatus.CANCELLED, "cancelled by client")
            self._release_robot(stored.request.robot_id, command_id)
            return self._record(stored)

    def simulate_hardware_state(
        self, robot_id: str, patch: HardwareStatePatch
    ) -> RobotState:
        with self._lock:
            state = self.get_state(robot_id)
            updates: dict[str, object] = {
                "state_version": state.state_version + 1,
                "observed_at": self._clock.now(),
            }
            if patch.hardware_estop_engaged is not None:
                updates["hardware_safety_state"] = (
                    HardwareSafetyState.ESTOP_ENGAGED
                    if patch.hardware_estop_engaged
                    else HardwareSafetyState.NORMAL
                )
            if patch.pose is not None:
                updates["pose"] = patch.pose
            if patch.joint_positions_rad is not None:
                product = self._get_product(state.product_id)
                if product is None or len(patch.joint_positions_rad) != product.joint_count:
                    raise ConflictError(
                        "invalid_joint_count", "hardware state does not match product profile"
                    )
                updates["joint_positions_rad"] = tuple(patch.joint_positions_rad)
            updated = state.model_copy(update=updates)
            self._states[robot_id] = updated
            return updated

    def _finish_completed(self, stored: _StoredCommand) -> None:
        request = stored.request
        state = self.get_state(request.robot_id)
        updates: dict[str, object] = {
            "active_command_id": None,
            "state_version": state.state_version + 1,
            "observed_at": self._clock.now(),
        }
        if isinstance(request.action, NavigateAction):
            updates["pose"] = request.action.target
        elif isinstance(request.action, ManipulateAction):
            updates["joint_positions_rad"] = tuple(request.action.joint_positions_rad)
        elif isinstance(request.action, ProtectiveStopAction):
            updates["software_protective_stop"] = True
        self._states[state.robot_id] = state.model_copy(update=updates)
        self._set_status(stored, CommandStatus.COMPLETED)

    def _finish_failed(self, stored: _StoredCommand, error_code: str) -> None:
        self._set_status(stored, CommandStatus.FAILED, error_code, error_code)
        self._release_robot(stored.request.robot_id, stored.request.command_id)

    def _release_robot(self, robot_id: str, command_id: str) -> None:
        state = self.get_state(robot_id)
        if state.active_command_id == command_id:
            self._states[robot_id] = state.model_copy(
                update={
                    "active_command_id": None,
                    "state_version": state.state_version + 1,
                    "observed_at": self._clock.now(),
                }
            )

    def _find_command(self, command_id: str) -> _StoredCommand:
        self._cleanup()
        try:
            return self._commands[command_id]
        except KeyError as exc:
            raise NotFoundError(f"command {command_id}") from exc

    def _set_status(
        self,
        stored: _StoredCommand,
        status: CommandStatus,
        detail: str | None = None,
        error_code: str | None = None,
    ) -> None:
        stored.status = status
        stored.error_code = error_code
        stored.transitions.append(self._transition(status, detail))

    def _transition(self, status: CommandStatus, detail: str | None = None) -> CommandTransition:
        return CommandTransition(status=status, occurred_at=self._clock.now(), detail=detail)

    def _record(self, stored: _StoredCommand) -> CommandRecord:
        return CommandRecord(
            request=stored.request,
            status=stored.status,
            transitions=tuple(stored.transitions),
            updated_at=stored.transitions[-1].occurred_at,
            error_code=stored.error_code,
        )

    def _cleanup(self) -> None:
        cutoff = self._clock.now() - self._terminal_retention
        expired = [
            command_id
            for command_id, stored in self._commands.items()
            if stored.status in TERMINAL_STATUSES and stored.transitions[-1].occurred_at <= cutoff
        ]
        for command_id in expired:
            del self._commands[command_id]

    def _evict_oldest_terminal(self) -> None:
        for command_id, stored in self._commands.items():
            if stored.status in TERMINAL_STATUSES:
                del self._commands[command_id]
                return

    def _get_product(self, product_id: str) -> ProductProfile | None:
        return self._products_by_id.get(product_id)

    @property
    def command_count(self) -> int:
        with self._lock:
            self._cleanup()
            return len(self._commands)
