from __future__ import annotations

from typing import Annotated, Literal, Union
from pydantic import BaseModel, Field


# ── Duration variants ──────────────────────────────────────────────────────────

class DurationTime(BaseModel):
    type: Literal["time"]
    value_s: float = Field(ge=1, le=86400)


class DurationDistance(BaseModel):
    type: Literal["distance"]
    value_m: float = Field(ge=1, le=100000)


class DurationCalories(BaseModel):
    type: Literal["calories"]
    value_kcal: int = Field(ge=1, le=10000)


class DurationHrLessThan(BaseModel):
    type: Literal["hr_less_than"]
    value_bpm: int = Field(ge=60, le=220)


class DurationHrGreaterThan(BaseModel):
    type: Literal["hr_greater_than"]
    value_bpm: int = Field(ge=60, le=220)


class DurationReps(BaseModel):
    type: Literal["reps"]
    value_reps: int = Field(ge=1, le=1000)


class DurationOpen(BaseModel):
    type: Literal["open"]


Duration = Annotated[
    Union[
        DurationTime,
        DurationDistance,
        DurationCalories,
        DurationHrLessThan,
        DurationHrGreaterThan,
        DurationReps,
        DurationOpen,
    ],
    Field(discriminator="type"),
]


# ── Target variants ────────────────────────────────────────────────────────────

class TargetOpen(BaseModel):
    type: Literal["open"]


class TargetHeartRateZone(BaseModel):
    type: Literal["heart_rate"]
    zone: int = Field(ge=1, le=5)


class TargetHeartRateCustom(BaseModel):
    type: Literal["heart_rate_custom"]
    low_bpm: int = Field(ge=60, le=220)
    high_bpm: int = Field(ge=60, le=220)


class TargetPowerZone(BaseModel):
    type: Literal["power"]
    zone: int = Field(ge=1, le=7)


class TargetPowerCustom(BaseModel):
    type: Literal["power_custom"]
    low_watts: int = Field(ge=0, le=2500)
    high_watts: int = Field(ge=0, le=2500)


class TargetCadence(BaseModel):
    type: Literal["cadence"]
    low_rpm: int = Field(ge=0, le=250)
    high_rpm: int = Field(ge=0, le=250)


class TargetSpeed(BaseModel):
    type: Literal["speed"]
    low_ms: float = Field(ge=0)
    high_ms: float = Field(ge=0)


class TargetPace(BaseModel):
    type: Literal["pace"]
    low_ms: float = Field(ge=0)
    high_ms: float = Field(ge=0)


Target = Annotated[
    Union[
        TargetOpen,
        TargetHeartRateZone,
        TargetHeartRateCustom,
        TargetPowerZone,
        TargetPowerCustom,
        TargetCadence,
        TargetSpeed,
        TargetPace,
    ],
    Field(discriminator="type"),
]


# ── Step + Workout ─────────────────────────────────────────────────────────────

class WorkoutStep(BaseModel):
    name: str = Field(min_length=1, max_length=16)
    intensity: Literal[
        "active", "easy", "warmup", "cooldown", "recovery",
        "interval", "repeat", "threshold", "work", "hard_interval",
    ]
    duration: Duration
    target: Target | None = None
    secondary_target: Target | None = None
    notes: str | None = Field(default=None, max_length=254)


class WorkoutDefinition(BaseModel):
    name: str = Field(min_length=1, max_length=16)
    sport: Literal["running", "cycling", "swimming", "walking", "generic"]
    sub_sport: str | None = None
    description: str | None = Field(default=None, max_length=254)
    steps: list[WorkoutStep] = Field(min_length=1, max_length=100)
