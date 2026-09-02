"""FastAPI transport for any RobotPort implementation."""

from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from physical_robot.contracts import (
    CommandRecord,
    CommandRequest,
    ErrorResponse,
    HardwareStatePatch,
    RobotState,
)
from physical_robot.errors import RobotError
from physical_robot.ports import RobotPort
from physical_robot.products import ProductCapabilityProfile, ProductProfile
from physical_robot.runtime import MockRobotRuntime


def create_app(port: RobotPort | None = None) -> FastAPI:
    robot_port = port or MockRobotRuntime()
    app = FastAPI(
        title="Physical Robot Interface",
        version="1.1.0",
        description=(
            "Vendor-neutral RobotPort. software protective_stop is not a certified "
            "hardware emergency stop."
        ),
    )

    def get_port() -> RobotPort:
        return robot_port

    Port = Annotated[RobotPort, Depends(get_port)]

    @app.exception_handler(RobotError)
    async def robot_error_handler(_request: Request, exc: RobotError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(code=exc.code, message=exc.message).model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        locations = [".".join(str(item) for item in error["loc"]) for error in exc.errors()]
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(
                code="validation_error", message=f"invalid fields: {', '.join(locations)}"
            ).model_dump(),
        )

    @app.get("/healthz", include_in_schema=False)
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/products", response_model=list[ProductProfile])
    def list_products(port: Port) -> tuple[ProductProfile, ...]:
        return port.catalog()

    @app.get("/v2/products", response_model=list[ProductCapabilityProfile])
    def list_product_capabilities(port: Port) -> tuple[ProductCapabilityProfile, ...]:
        return port.capability_catalog()

    @app.get("/v2/products/{product_id}", response_model=ProductCapabilityProfile)
    def get_product_capability(product_id: str, port: Port) -> ProductCapabilityProfile:
        return port.get_capability_profile(product_id)

    @app.get("/v1/robots", response_model=list[RobotState])
    def list_robots(port: Port) -> tuple[RobotState, ...]:
        return port.list_states()

    @app.get("/v1/robots/{robot_id}", response_model=RobotState)
    def get_robot(robot_id: str, port: Port) -> RobotState:
        return port.get_state(robot_id)

    @app.post("/v1/commands", response_model=CommandRecord, status_code=202)
    def submit_command(command: CommandRequest, port: Port) -> CommandRecord:
        return port.submit(command)

    @app.get("/v1/commands/{command_id}", response_model=CommandRecord)
    def get_command(command_id: str, port: Port) -> CommandRecord:
        return port.get_command(command_id)

    @app.post("/v1/commands/{command_id}/cancel", response_model=CommandRecord)
    def cancel_command(command_id: str, port: Port) -> CommandRecord:
        return port.cancel(command_id)

    @app.patch("/v1/simulator/robots/{robot_id}/hardware-state", response_model=RobotState)
    def simulate_hardware_state(
        robot_id: str, patch: HardwareStatePatch, port: Port
    ) -> RobotState:
        return port.simulate_hardware_state(robot_id, patch)

    return app


app = create_app()
