"""Supported mock product profiles and immutable v2 capability metadata."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

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


CAPABILITY_PROFILE_VERSION: Final[Literal["2.0.0"]] = "2.0.0"


class JointLimit(BaseModel):
    """A mock product's planner-visible position and velocity envelope."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    joint_name: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
    min_position_rad: float = Field(ge=-6.283186, le=6.283186)
    max_position_rad: float = Field(ge=-6.283186, le=6.283186)
    max_velocity_rad_s: float = Field(gt=0, le=20)

    @model_validator(mode="after")
    def ordered_range(self) -> JointLimit:
        if self.min_position_rad >= self.max_position_rad:
            raise ValueError("min_position_rad must be less than max_position_rad")
        return self


class ProductCapabilityProfile(BaseModel):
    """Strict v2 product envelope; the digest covers every preceding field."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    schema_version: Literal["2.0.0"] = CAPABILITY_PROFILE_VERSION
    product_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
    classification: str = Field(min_length=1, max_length=128)
    product_name: str = Field(min_length=1, max_length=128)
    model_name: str = Field(min_length=1, max_length=128)
    capabilities: tuple[CommandType, ...] = Field(min_length=1)
    joint_count: int = Field(ge=1, le=16)
    connection_interface: str = Field(min_length=1, max_length=256)
    joint_limits: tuple[JointLimit, ...] = Field(min_length=1, max_length=16)
    max_manipulation_force_n: float = Field(gt=0, le=250)
    max_navigation_speed_mps: float = Field(gt=0, le=2)
    max_payload_kg: float = Field(gt=0, le=1_000)
    base_frame: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_/]{0,63}$")
    tool_frame: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_/]{0,63}$")
    profile_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_envelope_and_digest(self) -> ProductCapabilityProfile:
        if len(self.joint_limits) != self.joint_count:
            raise ValueError("joint_limits length must equal joint_count")
        names = [limit.joint_name for limit in self.joint_limits]
        if len(names) != len(set(names)):
            raise ValueError("joint limit names must be unique")
        capability_values = [capability.value for capability in self.capabilities]
        if capability_values != sorted(set(capability_values)):
            raise ValueError("capabilities must be unique and canonically ordered")
        if self.base_frame == self.tool_frame:
            raise ValueError("base_frame and tool_frame must be different")
        expected = capability_profile_digest(
            self.model_dump(mode="json", exclude={"profile_digest"})
        )
        if self.profile_digest != expected:
            raise ValueError("profile_digest does not match the canonical profile")
        return self


def capability_profile_digest(payload: dict[str, Any]) -> str:
    """Return the stable digest for a JSON-compatible v2 profile payload."""

    canonical = json.dumps(
        payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode()
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


@dataclass(frozen=True)
class _CapabilitySpecification:
    joint_names: tuple[str, ...]
    min_position_rad: float
    max_position_rad: float
    max_velocity_rad_s: float
    max_manipulation_force_n: float
    max_navigation_speed_mps: float
    max_payload_kg: float
    base_frame: str
    tool_frame: str


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

_CAPABILITY_SPECS = {
    "mock-humanoid-mh-01": _CapabilitySpecification(
        joint_names=tuple(f"joint_{index:02d}" for index in range(1, 13)),
        min_position_rad=-2.8,
        max_position_rad=2.8,
        max_velocity_rad_s=1.5,
        max_manipulation_force_n=120.0,
        max_navigation_speed_mps=1.0,
        max_payload_kg=15.0,
        base_frame="base_link",
        tool_frame="right_hand_tool0",
    ),
    "mock-mobile-manipulator-mm-01": _CapabilitySpecification(
        joint_names=tuple(f"arm_joint_{index}" for index in range(1, 7)),
        min_position_rad=-3.0,
        max_position_rad=3.0,
        max_velocity_rad_s=2.0,
        max_manipulation_force_n=80.0,
        max_navigation_speed_mps=1.25,
        max_payload_kg=10.0,
        base_frame="base_link",
        tool_frame="arm_tool0",
    ),
}


def product_catalog() -> tuple[ProductProfile, ...]:
    return _PRODUCTS


def get_product(product_id: str) -> ProductProfile | None:
    return next((product for product in _PRODUCTS if product.product_id == product_id), None)


def capability_profiles_for(
    products: tuple[ProductProfile, ...],
) -> tuple[ProductCapabilityProfile, ...]:
    """Build v2 envelopes for the supported mock product IDs."""

    profiles: list[ProductCapabilityProfile] = []
    for product in products:
        try:
            specification = _CAPABILITY_SPECS[product.product_id]
        except KeyError as exc:
            raise ValueError(f"no capability limits configured for {product.product_id}") from exc
        payload: dict[str, Any] = {
            "schema_version": CAPABILITY_PROFILE_VERSION,
            "product_id": product.product_id,
            "classification": product.classification,
            "product_name": product.product_name,
            "model_name": product.model_name,
            "capabilities": sorted(item.value for item in product.capabilities),
            "joint_count": product.joint_count,
            "connection_interface": product.connection_interface,
            "joint_limits": [
                {
                    "joint_name": name,
                    "min_position_rad": specification.min_position_rad,
                    "max_position_rad": specification.max_position_rad,
                    "max_velocity_rad_s": specification.max_velocity_rad_s,
                }
                for name in specification.joint_names
            ],
            "max_manipulation_force_n": specification.max_manipulation_force_n,
            "max_navigation_speed_mps": specification.max_navigation_speed_mps,
            "max_payload_kg": specification.max_payload_kg,
            "base_frame": specification.base_frame,
            "tool_frame": specification.tool_frame,
        }
        profiles.append(
            ProductCapabilityProfile.model_validate(
                {**payload, "profile_digest": capability_profile_digest(payload)}
            )
        )
    return tuple(profiles)


def product_capability_catalog() -> tuple[ProductCapabilityProfile, ...]:
    return capability_profiles_for(_PRODUCTS)


def get_product_capability(product_id: str) -> ProductCapabilityProfile | None:
    return next(
        (profile for profile in product_capability_catalog() if profile.product_id == product_id),
        None,
    )
