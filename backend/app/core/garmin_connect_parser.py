from __future__ import annotations

from collections import Counter

_SPORT_MAP: dict[str, str] = {
    "running": "running",
    "cycling": "cycling",
    "swimming": "swimming",
    "walking": "walking",
    "generic": "generic",
    "fitness_equipment": "generic",
    "training": "generic",
    "cardio": "generic",
}

_INTENSITY_MAP: dict[str, str] = {
    "warmup": "warmup",
    "cooldown": "cooldown",
    "interval": "interval",
    "recovery": "recovery",
    "rest": "recovery",
    "active": "active",
    "threshold": "threshold",
    "work": "work",
    "other": "active",
    "easy": "easy",
}

_INTENSITY_NAME_MAP: dict[str, str] = {
    "warmup": "Warm Up",
    "cooldown": "Cool Down",
    "interval": "Interval",
    "recovery": "Recovery",
    "active": "Active",
    "threshold": "Threshold",
    "work": "Work",
    "easy": "Easy",
    "hard_interval": "Hard Interval",
}

_DURATION_KEY_MAP: dict[str, str] = {
    "time": "time",
    "distance": "distance",
    "calories": "calories",
    "lap.button": "open",
    "open": "open",
    "reps": "reps",
    "heart.rate.less.than": "hr_less_than",
    "heart.rate.greater.than": "hr_greater_than",
    "fixed.rest": "time",
}

_TOP_LEVEL_STEP_TYPES = {"warmup", "cooldown"}


def is_garmin_connect_format(data: dict) -> bool:
    """True if the payload looks like a Garmin Connect REST API workout."""
    return "workoutName" in data or "workoutSegments" in data


def parse_garmin_connect(data: dict) -> dict:
    """Convert a Garmin Connect REST API workout payload to a Connect Buddy schema dict."""
    name = str(data.get("workoutName") or "Workout")[:16]

    sport = "generic"
    for seg in data.get("workoutSegments") or []:
        sport_key = ((seg.get("sportType") or {}).get("sportTypeKey") or "").lower()
        if sport_key:
            sport = _SPORT_MAP.get(sport_key, "generic")
            break
    if sport == "generic" and "sport" in data:
        sport = _SPORT_MAP.get(str(data["sport"]).lower(), "generic")

    raw_steps: list[dict] = []
    for seg in data.get("workoutSegments") or []:
        raw_steps.extend(seg.get("workoutSteps") or [])

    items = _collect_steps(raw_steps)
    named_items = _assign_names(items)

    result: dict = {"name": name, "sport": sport, "steps": named_items}
    notes = data.get("notes")
    if notes:
        result["description"] = str(notes)[:254]
    return result


# ── Step collection ─────────────────────────────────────────────────────────────

def _collect_steps(raw_steps: list[dict]) -> list[dict]:
    """Resolve repeat groups and return a list of step/repeat-block dicts (no names)."""
    if not raw_steps:
        return []

    sorted_steps = sorted(raw_steps, key=lambda s: s.get("stepOrder", 0))

    child_orders: set[int] = set()
    # Maps rep_order → {"iterations": int, "children": list[dict]}
    repeat_info: dict[int, dict] = {}

    repeat_step_list = [
        s for s in sorted_steps
        if (s.get("stepType") or {}).get("stepTypeKey") == "repeat"
    ]

    for rep in repeat_step_list:
        rep_order = rep.get("stepOrder", 0)
        iterations = int(rep.get("numberOfIterations") or 1)

        # Nested format: children are embedded directly inside the repeat step.
        # Their stepOrder values are local to the block, not global, so they cannot
        # be found via flat-list position or childStepId matching.
        nested = rep.get("workoutSteps")
        if nested:
            repeat_info[rep_order] = {
                "iterations": iterations,
                "children": [s for s in nested if (s.get("stepType") or {}).get("stepTypeKey") != "repeat"],
            }
            continue

        group_id = rep.get("childStepId")

        if group_id is not None:
            # Canonical Garmin format: child steps carry the same childStepId value.
            canonical = [
                s for s in sorted_steps
                if s.get("childStepId") == group_id
                and (s.get("stepType") or {}).get("stepTypeKey") != "repeat"
            ]
            if canonical:
                repeat_info[rep_order] = {"iterations": iterations, "children": canonical}
                child_orders.update(s.get("stepOrder", -1) for s in canonical)
                continue

            # Claude's format: childStepId equals the stepOrder of the first child.
            children = _positional_children(sorted_steps, rep_order, int(group_id))
        else:
            children = _positional_children(sorted_steps, rep_order, None)

        repeat_info[rep_order] = {"iterations": iterations, "children": children}
        child_orders.update(s.get("stepOrder", -1) for s in children)

    result: list[dict] = []
    for step in sorted_steps:
        order = step.get("stepOrder", 0)
        if order in child_orders:
            continue

        step_type_key = (step.get("stepType") or {}).get("stepTypeKey", "")
        if step_type_key == "repeat":
            info = repeat_info.get(order, {"iterations": 1, "children": []})
            converted_children = [c for c in (_convert_step(ch) for ch in info["children"]) if c is not None]
            if converted_children:
                result.append({"type": "repeat", "iterations": info["iterations"], "steps": converted_children})
        else:
            converted = _convert_step(step)
            if converted is not None:
                result.append(converted)

    return result


def _positional_children(
    sorted_steps: list[dict],
    rep_order: int,
    first_child_order: int | None,
) -> list[dict]:
    """
    Collect child steps by position when childStepId links between steps are absent.
    Starts at `first_child_order` (or the step immediately after `rep_order` if None)
    and stops before the next warmup / cooldown / repeat step.
    """
    children: list[dict] = []
    started = first_child_order is None

    for step in sorted_steps:
        order = step.get("stepOrder", 0)
        if order <= rep_order:
            continue

        step_type_key = (step.get("stepType") or {}).get("stepTypeKey", "")

        if not started:
            if order == first_child_order:
                started = True
            else:
                continue

        if step_type_key in _TOP_LEVEL_STEP_TYPES or step_type_key == "repeat":
            break
        children.append(step)

    return children


def _convert_step(step: dict) -> dict | None:
    """Convert one Garmin Connect step dict to a partial Connect Buddy step dict (no name yet)."""
    step_type_key = (step.get("stepType") or {}).get("stepTypeKey", "active")
    if step_type_key == "repeat":
        return None

    intensity = _INTENSITY_MAP.get(step_type_key, "active")

    dur_key = (step.get("durationType") or {}).get("durationTypeKey", "open")
    dur_type = _DURATION_KEY_MAP.get(dur_key, "open")
    dur_val = step.get("durationValue")

    if dur_type == "time":
        duration: dict = {"type": "time", "value_s": float(dur_val or 0)}
    elif dur_type == "distance":
        duration = {"type": "distance", "value_m": float(dur_val or 0)}
    elif dur_type == "calories":
        duration = {"type": "calories", "value_kcal": int(dur_val or 0)}
    elif dur_type == "reps":
        duration = {"type": "reps", "value_reps": int(dur_val or 0)}
    elif dur_type == "hr_less_than":
        duration = {"type": "hr_less_than", "value_bpm": int(dur_val or 0)}
    elif dur_type == "hr_greater_than":
        duration = {"type": "hr_greater_than", "value_bpm": int(dur_val or 0)}
    else:
        duration = {"type": "open"}

    result: dict = {"intensity": intensity, "duration": duration}

    target_key = ((step.get("targetType") or {}).get("workoutTargetTypeKey") or "no.target")
    val1 = step.get("targetValueOne")
    val2 = step.get("targetValueTwo")
    target = _convert_target(target_key, val1, val2)
    if target:
        result["target"] = target

    notes = step.get("notes")
    if notes:
        result["notes"] = str(notes)[:254]

    return result


def _convert_target(type_key: str, val1, val2) -> dict | None:
    if not type_key or type_key == "no.target":
        return None

    if type_key == "pace.zone":
        if val1 and val2:
            v1, v2 = float(val1), float(val2)
            if v1 < 20:
                # Native Garmin format: values are already m/s
                lo_ms = round(min(v1, v2), 7)
                hi_ms = round(max(v1, v2), 7)
            else:
                # Shorthand format: values are sec/km
                lo_ms = round(1000 / max(v1, v2), 7)
                hi_ms = round(1000 / min(v1, v2), 7)
            return {"type": "pace", "low_ms": lo_ms, "high_ms": hi_ms}

    elif type_key == "heart.rate.zone":
        if val1:
            return {"type": "heart_rate", "zone": int(val1)}

    elif type_key == "power.zone":
        if val1:
            return {"type": "power", "zone": int(val1)}

    elif type_key in ("heart.rate", "heart.rate.custom"):
        if val1 and val2:
            return {
                "type": "heart_rate_custom",
                "low_bpm": int(min(float(val1), float(val2))),
                "high_bpm": int(max(float(val1), float(val2))),
            }

    elif type_key in ("power", "power.custom"):
        if val1 and val2:
            return {
                "type": "power_custom",
                "low_watts": int(min(float(val1), float(val2))),
                "high_watts": int(max(float(val1), float(val2))),
            }

    elif type_key == "cadence":
        if val1 and val2:
            return {
                "type": "cadence",
                "low_rpm": int(min(float(val1), float(val2))),
                "high_rpm": int(max(float(val1), float(val2))),
            }

    elif type_key == "speed":
        if val1 and val2:
            return {
                "type": "speed",
                "low_ms": float(min(float(val1), float(val2))),
                "high_ms": float(max(float(val1), float(val2))),
            }

    return None


# ── Name assignment ────────────────────────────────────────────────────────────

def _assign_names(items: list[dict]) -> list[dict]:
    """
    Add a `name` field to each step based on its intensity.
    Unique-intensity steps get a plain label ("Warm Up");
    duplicates are numbered ("Interval 1", "Interval 2", …).
    Repeat block children are named independently within their block.
    """
    counts: Counter[str] = Counter()
    bases: list[str | None] = []
    for item in items:
        if item.get("type") == "repeat":
            bases.append(None)
        else:
            base = _INTENSITY_NAME_MAP.get(item.get("intensity", "active"), "Step")
            counts[base] += 1
            bases.append(base)

    seen: Counter[str] = Counter()
    result = []
    for item, base in zip(items, bases):
        if item.get("type") == "repeat":
            result.append({**item, "steps": _assign_names(item["steps"])})
        else:
            if counts[base] > 1:
                seen[base] += 1
                name = f"{base} {seen[base]}"
            else:
                name = base
            result.append({"name": name[:16], **item})
    return result
