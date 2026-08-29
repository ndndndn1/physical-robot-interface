"""Small typed client shared by applications and adapter conformance tests."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx

from physical_robot.contracts import (
    CommandRecord,
    CommandRequest,
    ErrorResponse,
    HardwareStatePatch,
    RobotState,
)
from physical_robot.errors import RobotError
from physical_robot.products import ProductProfile


class RobotClient:
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8080",
        *,
        timeout_seconds: float = 5.0,
        client: httpx.Client | None = None,
    ) -> None:
        self._owns_client = client is None
        self._client = client or httpx.Client(base_url=base_url, timeout=timeout_seconds)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> RobotClient:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def products(self) -> tuple[ProductProfile, ...]:
        response = self._request("GET", "/v1/products")
        return tuple(ProductProfile.model_validate(item) for item in response.json())

    def robots(self) -> tuple[RobotState, ...]:
        response = self._request("GET", "/v1/robots")
        return tuple(RobotState.model_validate(item) for item in response.json())

    def state(self, robot_id: str) -> RobotState:
        response = self._request("GET", f"/v1/robots/{robot_id}")
        return RobotState.model_validate(response.json())

    def submit(self, command: CommandRequest) -> CommandRecord:
        response = self._request(
            "POST", "/v1/commands", json=command.model_dump(mode="json")
        )
        return CommandRecord.model_validate(response.json())

    def command(self, command_id: str) -> CommandRecord:
        response = self._request("GET", f"/v1/commands/{command_id}")
        return CommandRecord.model_validate(response.json())

    def cancel(self, command_id: str) -> CommandRecord:
        response = self._request("POST", f"/v1/commands/{command_id}/cancel")
        return CommandRecord.model_validate(response.json())

    def simulate_hardware(self, robot_id: str, patch: HardwareStatePatch) -> RobotState:
        response = self._request(
            "PATCH",
            f"/v1/simulator/robots/{robot_id}/hardware-state",
            json=patch.model_dump(mode="json", exclude_none=True),
        )
        return RobotState.model_validate(response.json())

    def _request(
        self, method: str, url: str, *, json: Mapping[str, Any] | None = None
    ) -> httpx.Response:
        response = self._client.request(method, url, json=json)
        if response.is_error:
            try:
                error = ErrorResponse.model_validate(response.json())
            except ValueError as exc:
                raise RobotError(
                    "invalid_error_response", response.text, response.status_code
                ) from exc
            raise RobotError(error.code, error.message, response.status_code)
        return response
