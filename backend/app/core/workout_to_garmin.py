from __future__ import annotations

from .models import (
    DurationCalories,
    DurationDistance,
    DurationHrGreaterThan,
    DurationHrLessThan,
    DurationOpen,
    DurationReps,
    DurationTime,
    RepeatBlock,
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

# ── ID tables (from garminconnect.workout module) ──────────────────────────────

_SPORT_TYPE: dict[str, dict] = {
    "running":  {"sportTypeId": 1, "sportTypeKey": "running",  "displayOrder": 1},
    "cycling":  {"sportTypeId": 2, "sportTypeKey": "cycling",  "displayOrder": 2},
    "swimming": {"sportTypeId": 4, "sportTypeKey": "swimming", "displayOrder": 3},
    "walking":  {"sportTypeId": 4, "sportTypeKey": "walking",  "displayOrder": 4},
    "generic":  {"sportTypeId": 8, "sportTypeKey": "other",    "displayOrder": 8},
}

_STEP_TYPE: dict[str, dict] = {
    "warmup":       {"stepTypeId": 1, "stepTypeKey": "warmup",    "displayOrder": 1},
    "cooldown":     {"stepTypeId": 2, "stepTypeKey": "cooldown",  "displayOrder": 2},
    "interval":     {"stepTypeId": 3, "stepTypeKey": "interval",  "displayOrder": 3},
    "recovery":     {"stepTypeId": 4, "stepTypeKey": "recovery",  "displayOrder": 4},
    "rest":         {"stepTypeId": 5, "stepTypeKey": "rest",      "displayOrder": 5},
    "active":       {"stepTypeId": 3, "stepTypeKey": "interval",  "displayOrder": 3},
    "threshold":    {"stepTypeId": 3, "stepTypeKey": "interval",  "displayOrder": 3},
    "work":         {"stepTypeId": 3, "stepTypeKey": "interval",  "displayOrder": 3},
    "easy":         {"stepTypeId": 4, "stepTypeKey": "recovery",  "displayOrder": 4},
    "hard_interval":{"stepTypeId": 3, "stepTypeKey": "interval",  "displayOrder": 3},
}

_NO_TARGET = {"workoutTargetTypeId": 1, "workoutTargetTypeKey": "no.target", "displayOrder": 1}

# conditionType IDs match garminconnect.workout.ConditionType
_COND_TIME     = {"conditionTypeId": 2, "conditionTypeKey": "time",                   "displayOrder": 2, "displayable": True}
_COND_DISTANCE = {"conditionTypeId": 1, "conditionTypeKey": "distance",               "displayOrder": 1, "displayable": True}
_COND_CALORIES = {"conditionTypeId": 4, "conditionTypeKey": "calories",               "displayOrder": 4, "displayable": True}
_COND_HR_LT    = {"conditionTypeId": 3, "conditionTypeKey": "heart.rate.less.than",   "displayOrder": 3, "displayable": True}
_COND_HR_GT    = {"conditionTypeId": 3, "conditionTypeKey": "heart.rate.greater.than","displayOrder": 3, "displayable": True}
_COND_REPS     = {"conditionTypeId": 7, "conditionTypeKey": "reps",                   "displayOrder": 7, "displayable": True}
_COND_OPEN     = {"conditionTypeId": 1, "conditionTypeKey": "lap.button",             "displayOrder": 7, "displayable": True}


_REPEAT_STEP_TYPE = {"stepTypeId": 6, "stepTypeKey": "repeat", "displayOrder": 6}


def to_garmin_connect(workout: WorkoutDefinition) -> dict:
    """Convert a WorkoutDefinition to the Garmin Connect upload API format."""
    sport = _SPORT_TYPE.get(workout.sport, _SPORT_TYPE["generic"])
    steps, _ = _build_items(workout.steps, start_order=1)

    result: dict = {
        "workoutName": workout.name,
        "sportType": sport,
        "estimatedDurationInSecs": 0,
        "workoutSegments": [
            {
                "segmentOrder": 1,
                "sportType": sport,
                "workoutSteps": steps,
            }
        ],
        "author": {},
    }
    if workout.description:
        result["description"] = workout.description
    return result


def _build_items(items, start_order: int) -> tuple[list[dict], int]:
    steps = []
    order = start_order
    for item in items:
        if isinstance(item, RepeatBlock):
            rep, order = _build_repeat_group(order, item)
            steps.append(rep)
        else:
            steps.append(_build_step(order, item))
            order += 1
    return steps, order


def _build_repeat_group(order: int, block: RepeatBlock) -> tuple[dict, int]:
    child_steps, next_order = _build_items(block.steps, start_order=order + 1)
    rep = {
        "type": "RepeatGroupDTO",
        "stepOrder": order,
        "stepType": _REPEAT_STEP_TYPE,
        "numberOfIterations": block.iterations,
        "childStepId": order,
        "workoutSteps": child_steps,
    }
    return rep, next_order


def _build_step(order: int, step: WorkoutStep) -> dict:
    step_type = _STEP_TYPE.get(step.intensity, _STEP_TYPE["interval"])
    end_cond, end_val = _end_condition(step.duration)
    target_type = _target_type(step.target)

    # Minimal set of fields — match exactly what garminconnect.workout produces.
    # Extra fields (strokeType, equipmentType, childStepId) cause Jackson to throw
    # InvalidTypeIdException when no type discriminator key is present on them.
    result: dict = {
        "type": "ExecutableStepDTO",
        "stepOrder": order,
        "stepType": step_type,
        "endCondition": end_cond,
        "targetType": target_type,
    }

    if end_val is not None:
        result["endConditionValue"] = end_val

    _apply_target_values(result, step.target)

    if step.notes:
        result["notes"] = step.notes

    return result


def _end_condition(dur) -> tuple[dict, float | None]:
    if isinstance(dur, DurationTime):
        return _COND_TIME, dur.value_s
    if isinstance(dur, DurationDistance):
        return _COND_DISTANCE, dur.value_m
    if isinstance(dur, DurationCalories):
        return _COND_CALORIES, float(dur.value_kcal)
    if isinstance(dur, DurationReps):
        return _COND_REPS, float(dur.value_reps)
    if isinstance(dur, DurationHrLessThan):
        return _COND_HR_LT, float(dur.value_bpm)
    if isinstance(dur, DurationHrGreaterThan):
        return _COND_HR_GT, float(dur.value_bpm)
    return _COND_OPEN, None  # DurationOpen


def _target_type(tgt) -> dict:
    if tgt is None or isinstance(tgt, TargetOpen):
        return _NO_TARGET
    if isinstance(tgt, (TargetHeartRateZone, TargetHeartRateCustom)):
        return {"workoutTargetTypeId": 4, "workoutTargetTypeKey": "heart.rate.zone", "displayOrder": 4}
    if isinstance(tgt, (TargetPowerZone, TargetPowerCustom)):
        return {"workoutTargetTypeId": 2, "workoutTargetTypeKey": "power.zone", "displayOrder": 2}
    if isinstance(tgt, TargetCadence):
        return {"workoutTargetTypeId": 3, "workoutTargetTypeKey": "cadence", "displayOrder": 3}
    if isinstance(tgt, TargetPace):
        # pace.zone (ID 6) is what Garmin Connect uses natively; values are in sec/km.
        return {"workoutTargetTypeId": 6, "workoutTargetTypeKey": "pace.zone", "displayOrder": 6}
    if isinstance(tgt, TargetSpeed):
        return {"workoutTargetTypeId": 5, "workoutTargetTypeKey": "speed.zone", "displayOrder": 5}
    return _NO_TARGET


def _apply_target_values(step: dict, tgt) -> None:
    if isinstance(tgt, TargetHeartRateZone):
        step["targetValue"] = tgt.zone
    elif isinstance(tgt, TargetHeartRateCustom):
        step["targetValueOne"] = float(tgt.low_bpm)
        step["targetValueTwo"] = float(tgt.high_bpm)
    elif isinstance(tgt, TargetPowerZone):
        step["targetValue"] = tgt.zone
    elif isinstance(tgt, TargetPowerCustom):
        step["targetValueOne"] = float(tgt.low_watts)
        step["targetValueTwo"] = float(tgt.high_watts)
    elif isinstance(tgt, TargetCadence):
        step["targetValueOne"] = float(tgt.low_rpm)
        step["targetValueTwo"] = float(tgt.high_rpm)
    elif isinstance(tgt, TargetPace):
        # pace.zone values are m/s; targetValueOne = faster (higher m/s), targetValueTwo = slower (lower m/s)
        step["targetValueOne"] = round(tgt.high_ms, 7)
        step["targetValueTwo"] = round(tgt.low_ms, 7)
    elif isinstance(tgt, TargetSpeed):
        # speed.zone values are in m/hr.
        step["targetValueOne"] = round(tgt.low_ms * 3600)
        step["targetValueTwo"] = round(tgt.high_ms * 3600)
