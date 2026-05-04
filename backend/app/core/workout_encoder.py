from __future__ import annotations

import time

from fit_tool.fit_file_builder import FitFileBuilder
from fit_tool.profile.messages.file_id_message import FileIdMessage
from fit_tool.profile.messages.workout_message import WorkoutMessage
from fit_tool.profile.messages.workout_step_message import WorkoutStepMessage
from fit_tool.profile.profile_type import (
    FileType,
    Intensity,
    Sport,
    SubSport,
    WorkoutStepDuration,
    WorkoutStepTarget,
)

from .models import (
    DurationCalories,
    DurationDistance,
    DurationHrGreaterThan,
    DurationHrLessThan,
    DurationOpen,
    DurationReps,
    DurationTime,
    TargetCadence,
    TargetHeartRateCustom,
    TargetHeartRateZone,
    TargetOpen,
    TargetPace,
    TargetPowerCustom,
    TargetPowerZone,
    TargetSpeed,
    WorkoutDefinition,
    WorkoutStep,
)

# fit-tool's time_created setter expects Unix milliseconds and converts to FIT epoch internally.
# (FIT epoch = Unix epoch + 631065600 seconds = 1989-12-31)

_SPORT_MAP: dict[str, Sport] = {
    "generic": Sport.GENERIC,
    "running": Sport.RUNNING,
    "cycling": Sport.CYCLING,
    "swimming": Sport.SWIMMING,
    "walking": Sport.WALKING,
}

_SUB_SPORT_MAP: dict[str, SubSport] = {
    "generic": SubSport.GENERIC,
    "treadmill": SubSport.TREADMILL,
    "street": SubSport.STREET,
    "trail": SubSport.TRAIL,
    "track": SubSport.TRACK,
    "indoor_cycling": SubSport.INDOOR_CYCLING,
    "spin": SubSport.SPIN,
    "road": SubSport.ROAD,
    "mountain": SubSport.MOUNTAIN,
    "downhill": SubSport.DOWNHILL,
    "recumbent": SubSport.RECUMBENT,
    "cyclocross": SubSport.CYCLOCROSS,
    "hand_cycling": SubSport.HAND_CYCLING,
    "track_cycling": SubSport.TRACK_CYCLING,
    "indoor_rowing": SubSport.INDOOR_ROWING,
    "elliptical": SubSport.ELLIPTICAL,
    "stair_climbing": SubSport.STAIR_CLIMBING,
    "lap_swimming": SubSport.LAP_SWIMMING,
    "open_water": SubSport.OPEN_WATER,
}

# Map schema intensity strings to FIT Intensity enum.
# "easy", "repeat", "threshold", "work", "hard_interval" have no exact FIT equivalent
# and are mapped to the nearest standard value.
_INTENSITY_MAP: dict[str, Intensity] = {
    "active": Intensity.ACTIVE,
    "easy": Intensity.RECOVERY,
    "warmup": Intensity.WARMUP,
    "cooldown": Intensity.COOLDOWN,
    "recovery": Intensity.RECOVERY,
    "interval": Intensity.INTERVAL,
    "repeat": Intensity.ACTIVE,
    "threshold": Intensity.INTERVAL,
    "work": Intensity.ACTIVE,
    "hard_interval": Intensity.INTERVAL,
}


def encode_workout(workout: WorkoutDefinition, timestamp: int | None = None) -> bytes:
    """
    Pure deterministic function: WorkoutDefinition → FIT binary bytes.
    Pass timestamp as Unix milliseconds explicitly in tests for reproducibility.
    fit-tool converts Unix ms → FIT epoch seconds internally.
    """
    ts = timestamp if timestamp is not None else int(time.time() * 1000)

    builder = FitFileBuilder(auto_define=True, min_string_size=50)

    file_id = FileIdMessage()
    file_id.type = FileType.WORKOUT
    file_id.manufacturer = 255  # DEVELOPMENT
    file_id.product = 0
    file_id.time_created = ts
    file_id.serial_number = 1
    builder.add(file_id)

    wkt = WorkoutMessage()
    wkt.sport = _SPORT_MAP[workout.sport]
    wkt.num_valid_steps = len(workout.steps)
    wkt.workout_name = workout.name
    if workout.sub_sport and workout.sub_sport in _SUB_SPORT_MAP:
        wkt.sub_sport = _SUB_SPORT_MAP[workout.sub_sport]
    builder.add(wkt)

    for i, step in enumerate(workout.steps):
        builder.add(_build_step_message(i, step))

    return builder.build().to_bytes()


def _build_step_message(index: int, step: WorkoutStep) -> WorkoutStepMessage:
    msg = WorkoutStepMessage()
    msg.message_index = index
    msg.workout_step_name = step.name
    msg.intensity = _INTENSITY_MAP[step.intensity]

    _apply_duration(msg, step.duration)

    if step.target is not None:
        _apply_target_primary(msg, step.target)

    if step.secondary_target is not None:
        _apply_target_secondary(msg, step.secondary_target)

    if step.notes:
        msg.notes = step.notes

    return msg


def _apply_duration(msg: WorkoutStepMessage, duration) -> None:
    if isinstance(duration, DurationTime):
        msg.duration_type = WorkoutStepDuration.TIME
        msg.duration_time = float(duration.value_s)  # seconds; fit-tool converts to ms
    elif isinstance(duration, DurationDistance):
        msg.duration_type = WorkoutStepDuration.DISTANCE
        msg.duration_distance = float(duration.value_m)  # metres; fit-tool converts to cm
    elif isinstance(duration, DurationCalories):
        msg.duration_type = WorkoutStepDuration.CALORIES
        msg.duration_calories = duration.value_kcal
    elif isinstance(duration, DurationHrLessThan):
        msg.duration_type = WorkoutStepDuration.HR_LESS_THAN
        msg.duration_hr = duration.value_bpm
    elif isinstance(duration, DurationHrGreaterThan):
        msg.duration_type = WorkoutStepDuration.HR_GREATER_THAN
        msg.duration_hr = duration.value_bpm
    elif isinstance(duration, DurationReps):
        msg.duration_type = WorkoutStepDuration.REPS
        msg.duration_reps = duration.value_reps
    elif isinstance(duration, DurationOpen):
        msg.duration_type = WorkoutStepDuration.OPEN


def _apply_target_primary(msg: WorkoutStepMessage, target) -> None:
    if isinstance(target, TargetOpen):
        # SPEED with zero range = no pacing guidance (standard Garmin encoding)
        msg.target_type = WorkoutStepTarget.SPEED
        msg.custom_target_value_low = 0
        msg.custom_target_value_high = 0
    elif isinstance(target, TargetHeartRateZone):
        msg.target_type = WorkoutStepTarget.HEART_RATE
        msg.target_hr_zone = target.zone
    elif isinstance(target, TargetHeartRateCustom):
        msg.target_type = WorkoutStepTarget.HEART_RATE
        msg.custom_target_value_low = target.low_bpm
        msg.custom_target_value_high = target.high_bpm
    elif isinstance(target, TargetPowerZone):
        msg.target_type = WorkoutStepTarget.POWER
        msg.target_power = target.zone
    elif isinstance(target, TargetPowerCustom):
        msg.target_type = WorkoutStepTarget.POWER
        msg.custom_target_value_low = target.low_watts
        msg.custom_target_value_high = target.high_watts
    elif isinstance(target, TargetCadence):
        msg.target_type = WorkoutStepTarget.CADENCE
        msg.custom_target_value_low = target.low_rpm
        msg.custom_target_value_high = target.high_rpm
    elif isinstance(target, (TargetSpeed, TargetPace)):
        # Both speed and pace use SPEED target type; values are in m/s
        msg.target_type = WorkoutStepTarget.SPEED
        msg.custom_target_value_low = int(target.low_ms * 1000)   # m/s → mm/s
        msg.custom_target_value_high = int(target.high_ms * 1000)


def _apply_target_secondary(msg: WorkoutStepMessage, target) -> None:
    """Secondary target (e.g., power zone + cadence range simultaneously)."""
    if isinstance(target, TargetOpen):
        return
    elif isinstance(target, TargetHeartRateZone):
        msg.secondary_target_type = WorkoutStepTarget.HEART_RATE
        msg.secondary_target_value = target.zone
    elif isinstance(target, TargetPowerZone):
        msg.secondary_target_type = WorkoutStepTarget.POWER
        msg.secondary_target_value = target.zone
    elif isinstance(target, TargetCadence):
        msg.secondary_target_type = WorkoutStepTarget.CADENCE
        msg.secondary_custom_target_value_low = target.low_rpm
        msg.secondary_custom_target_value_high = target.high_rpm
    elif isinstance(target, (TargetSpeed, TargetPace)):
        msg.secondary_target_type = WorkoutStepTarget.SPEED
        msg.secondary_custom_target_value_low = int(target.low_ms * 1000)
        msg.secondary_custom_target_value_high = int(target.high_ms * 1000)
