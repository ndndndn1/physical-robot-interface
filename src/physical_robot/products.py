"""Supported mock product profiles."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from physical_robot.contracts import CommandType


class ProductProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    product_id: str
    classification: str
    product_name: str
    model_name: str
    capabilities: frozenset[CommandType]
    joint_count: int = Field(ge=1, le=16)
    connection_interface: str


_PRODUCTS = (
    ProductProfile(
        product_id="mock-humanoid-mh-01",
        classification="industrial_humanoid",
        product_name="MockHumanoid",
        model_name="MH-01",
        capabilities=frozenset(CommandType),
        joint_count=12,
        connection_interface="RobotPort REST v1; replace mock with a conforming hardware adapter",
    ),
    ProductProfile(
        product_id="mock-mobile-manipulator-mm-01",
        classification="autonomous_mobile_manipulator",
        product_name="MockMobileManipulator",
        model_name="MM-01",
        capabilities=frozenset(CommandType),
        joint_count=6,
        connection_interface="RobotPort REST v1; replace mock with a conforming hardware adapter",
    ),
)


def product_catalog() -> tuple[ProductProfile, ...]:
    return _PRODUCTS


def get_product(product_id: str) -> ProductProfile | None:
    return next((product for product in _PRODUCTS if product.product_id == product_id), None)

